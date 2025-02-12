from utils import encode_image, extract_popup_details
from llm import initialize_llm
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from prompts import image_prompt, xml_prompt
from typing import Optional
import base64
from io import BytesIO
from dotenv import load_dotenv
import os
import json
from logger_config import setup_logger
import time

logger = setup_logger()
load_dotenv()

app = FastAPI()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    logger.info(f"Incoming request: {request.method} {request.url}")
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"Completed request: {request.method} {request.url} in {process_time:.4f} seconds")
    logger.info(f"Response status: {response.status_code}")
    return response

class APIRequest(BaseModel):
    image: Optional[str] = None        # Base64 encoded image string
    xml: Optional[str] = None          # XML as string
    testcase_desc: str = 'close the pop up'
    xml_url: Optional[str] = None      # XML URL option
    image_url: Optional[str] = None    # Image URL option

def validate_base64(base64_string: str) -> bool:
    try:
        base64.b64decode(base64_string)
        return True
    except Exception:
        return False

@app.post("/invoke")
async def run_service(request: APIRequest):
    try:
        llm_key = os.getenv("OPENAI_API_KEY")
        if not llm_key:
            raise HTTPException(status_code=500, detail="API key not found. Please check your environment variables.")
        llm = initialize_llm(llm_key)

        processed_xml = None
        messages = []
        # Highest priority: XML input
        if request.xml:
            processed_xml = extract_popup_details(request.xml)
            messages = [
                ("system", xml_prompt),
                ("human", f"Test case description: {request.testcase_desc}"),
                ("human", f"Pop-up detector output: {processed_xml}")
            ]
        elif request.xml_url:
            logger.info(f"XML URL: {request.xml_url}")
            processed_xml = extract_popup_details(request.xml_url)
            messages = [
                ("system", xml_prompt),
                ("human", f"Test case description: {request.testcase_desc}"),
                ("human", f"Pop-up detector output: {processed_xml}")
            ]
        # Process image only if no XML is provided.
        elif request.image:
            if not validate_base64(request.image):
                raise HTTPException(status_code=400, detail="Invalid base64 image data")
            messages = [
                ("system", image_prompt),
                ("human", f"Test case description: {request.testcase_desc}"),
                ("human", [
                    {"type": "text", "text": "Screenshot of current screen"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{request.image}"}}
                ])
            ]
        elif request.image_url:
            logger.info(f"Image URL: {request.image_url}")
            encoded_image = encode_image(request.image_url)
            messages = [
                ("system", image_prompt),
                ("human", f"Test case description: {request.testcase_desc}"),
                ("human", [
                    {"type": "text", "text": "Screenshot of current screen"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}}
                ])
            ]
        else:
            raise HTTPException(
                status_code=400,
                detail="Either XML (string/URL) or image (base64/URL) must be provided."
            )

        ai_msg = llm.invoke(messages)
        logger.info(f"AI message: {ai_msg.content}")

        # Clean and parse the AI response
        cleaned_content = ai_msg.content.strip("```json\n").strip("\n```")
        try:
            parsed_output = json.loads(cleaned_content)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse AI message content as JSON. Content: {ai_msg.content}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to parse AI message content as JSON. Content: {ai_msg.content}"
            )
        logger.info(f"Parsed output: {parsed_output}")

        # If XML input was used, map the element ids from the AI output to our processed XML metadata.
        if request.xml or request.xml_url:
            # If no popup was detected by the detector, return a simple response.
            if not processed_xml or not processed_xml.get("is_popup", False):
                final_response = {"popup_detection": "False"}
            else:
                # Primary method mapping
                primary_method_ai = parsed_output["primary_method"]
                primary_id = primary_method_ai["_id"]
                primary_selection_reason = primary_method_ai["selection_reason"]
                primary_metadata = processed_xml["interactable_elements"].get(primary_id)
                # Alternative methods mapping
                alternative_methods_ai = parsed_output["alternate_methods"]
                alternative_methods_mapped = []
                for method in alternative_methods_ai:
                    alt_id = method["_id"]
                    alt_dismissal_reason = method["dismissal_reason"]
                    alt_metadata = processed_xml["interactable_elements"].get(alt_id)
                    if alt_metadata:
                        alt_metadata["dismissal_reason"] = alt_dismissal_reason
                        alternative_methods_mapped.append(alt_metadata)
                    else:
                        alternative_methods_mapped.append(method)
                
                final_response = {
                    "status": "success",
                    "agent_response": {
                                            "popup_detection": parsed_output.get("popup_detection", "True"),
                    "suggested_action": parsed_output.get("suggested_action", ""),
                    "primary_method": {
                        "selection_reason": primary_selection_reason,
                        "element_metadata": primary_metadata if primary_metadata else {}
                    },
                    "alternative_methods": alternative_methods_mapped
                    }
                }
            return final_response
        else:
            # For image inputs, return the parsed minimal output directly.
            return {
                "status": "success",
                "agent_response": parsed_output
            }
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
