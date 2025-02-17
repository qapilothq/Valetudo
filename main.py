from utils import encode_image, extract_popup_details, annotate_image
from llm import initialize_llm
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from prompts import image_prompt, xml_prompt, combined_prompt
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
        encoded_image = None
        messages = []

        # Process image if provided
        if request.image:
            if not validate_base64(request.image):
                raise HTTPException(status_code=400, detail="Invalid base64 image data")
            encoded_image = request.image
        elif request.image_url:
            logger.info(f"Image URL: {request.image_url}")
            encoded_image = encode_image(request.image_url)

        # Process XML if provided
        if request.xml:
            processed_xml = extract_popup_details(request.xml)
        elif request.xml_url:
            logger.info(f"XML URL: {request.xml_url}")
            processed_xml = extract_popup_details(request.xml_url)

        # Case 1: Both image and XML provided
        if encoded_image and processed_xml:
            annotated_image = annotate_image(encoded_image, processed_xml)
            messages = [
                ("system", combined_prompt),
                ("human", f"Test case description: {request.testcase_desc}"),
                ("human", [
                    {"type": "text", "text": "Screenshot of current screen with annotated element IDs"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{annotated_image}"}}
                ])
            ]
        # Case 2: Only XML provided
        elif processed_xml:
            messages = [
                ("system", xml_prompt),
                ("human", f"Test case description: {request.testcase_desc}"),
                ("human", f"Pop-up detector output: {processed_xml}")
            ]
        # Case 3: Only image provided
        elif encoded_image:
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
        logger.info(f"AI message: {str(ai_msg.content)}")

        # Clean and parse the AI response
        cleaned_content = str(ai_msg.content).strip("```json\n").strip("\n```")
        try:
            parsed_output = json.loads(cleaned_content)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse AI message content as JSON. Content: {ai_msg.content}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to parse AI message content as JSON. Content: {ai_msg.content}"
            )
        logger.info(f"Parsed output: {parsed_output}")

        # Handle response based on inputs and AI output
        if processed_xml and encoded_image:
            # Combined case: Trust LLM's popup detection from image analysis
            if parsed_output.get("popup_detection", "True") == "False":
                final_response = {"status": "success", "message": "Popup detected and closed."}
            else:
                # Map primary method
                primary_method_ai = parsed_output.get("primary_method", {})
                primary_id = primary_method_ai.get("_id", "")
                primary_selection_reason = primary_method_ai.get("selection_reason", "")
                primary_metadata = processed_xml.get("interactable_elements", {}).get(primary_id, {})
                
                # Map alternative methods
                alternative_methods_ai = parsed_output.get("alternate_methods", [])
                alternative_methods_mapped = []
                for method in alternative_methods_ai:
                    alt_id = method.get("_id", "")
                    alt_dismissal_reason = method.get("dismissal_reason", "")
                    alt_metadata = processed_xml.get("interactable_elements", {}).get(alt_id, {})
                    if alt_metadata:
                        alternative_methods_mapped.append({
                            "element_metadata": alt_metadata,
                            "dismissal_reason": alt_dismissal_reason
                        })
                    else:
                        alternative_methods_mapped.append(method)
                
                final_response = {
                    "status": "success",
                    "agent_response": {
                        "popup_detection": "True",
                        "suggested_action": parsed_output.get("suggested_action", ""),
                        "primary_method": {
                            "selection_reason": primary_selection_reason,
                            "element_metadata": primary_metadata or {}
                        },
                        "alternative_methods": alternative_methods_mapped
                    }
                }
        elif processed_xml:
            # XML-only case: Check processed_xml for popup detection
            if not processed_xml.get("is_popup", False):
                final_response = {"status": "success", "agent_response": {"popup_detection": "False"}}
            else:
                try:
                    # Primary method mapping
                    primary_method_ai = parsed_output.get("primary_method", {})
                    primary_id = primary_method_ai.get("_id", "")
                    primary_selection_reason = primary_method_ai.get("selection_reason", "")
                    primary_metadata = processed_xml.get("interactable_elements", {}).get(primary_id, {})
                    
                    # Alternative methods mapping
                    alternative_methods_ai = parsed_output.get("alternate_methods", [])
                    alternative_methods_mapped = []
                    for method in alternative_methods_ai:
                        alt_id = method.get("_id", "")
                        alt_dismissal_reason = method.get("dismissal_reason", "")
                        alt_metadata = processed_xml.get("interactable_elements", {}).get(alt_id, {})
                        if alt_metadata:
                            alternative_methods_mapped.append({
                                "element_metadata": alt_metadata,
                                "dismissal_reason": alt_dismissal_reason
                            })
                        else:
                            alternative_methods_mapped.append(method)
                    
                    final_response = {
                        "status": "success",
                        "agent_response": {
                            "popup_detection": parsed_output.get("popup_detection", "True"),
                            "suggested_action": parsed_output.get("suggested_action", ""),
                            "primary_method": {
                                "selection_reason": primary_selection_reason,
                                "element_metadata": primary_metadata or {}
                            },
                            "alternative_methods": alternative_methods_mapped
                        }
                    }
                except KeyError as e:
                    logger.error(f"Missing key in parsed output: {e}")
                    raise HTTPException(
                        status_code=500, 
                        detail=f"Incomplete response from LLM. Missing key: {e}"
                    )
        else:
            # Image-only case: Return parsed output directly
            final_response = {
                "status": "success",
                "agent_response": parsed_output
            }
        
        logger.info(f"Final response: {final_response}")
        return final_response
    
    except json.JSONDecodeError as json_exc:
        logger.error(f"JSON decode error: {str(json_exc)}")
        return {"status": "error", "message": "Invalid JSON format.", "details": str(json_exc), "code": 400}
    
    except HTTPException as http_exc:
        logger.error(f"HTTP error: {str(http_exc.detail)}")
        return {"status": "error", "message": str(http_exc.detail), "code": http_exc.status_code}
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {"status": "error", "message": "An unexpected error occurred.", "details": str(e), "code": 500}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)