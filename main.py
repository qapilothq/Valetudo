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
    image: Optional[str] = None  # Base64 encoded image string
    xml: Optional[str] = None    # XML as string
    testcase_desc: str = 'close the pop up'
    xml_url: Optional[str] = None       # Keep URL options for flexibility
    image_url: Optional[str] = None     # Keep URL options for flexibility

def validate_base64(base64_string: str) -> bool:
    """Validate if a string is properly base64 encoded."""
    try:
        # Try to decode the base64 string
        base64.b64decode(base64_string)
        return True
    except Exception:
        return False

@app.post("/invoke")
async def run_service(request: APIRequest):
    try:
        # logger.info(f"Request body: {request.json()}")
        llm_key = os.getenv("OPENAI_API_KEY")
        if not llm_key:
            raise HTTPException(status_code=500, detail="API key not found. Please check your environment variables.")
        llm = initialize_llm(llm_key)

        if request.xml:
            # Process XML string with highest priority
            processed_xml = extract_popup_details(request.xml)
            messages = [
                ("system", xml_prompt),
                ("human", f"test-case description: {request.testcase_dec}"),
                ("human", f'this is the output from the pop-detector: {processed_xml}')
            ]
        
        elif request.xml_url:
            # Process XML URL as second priority
            logger.info(f"XML url: {request.xml_url}")
            processed_xml = extract_popup_details(request.xml_url)
            messages = [
                ("system", xml_prompt),
                ("human", f"test-case description: {request.testcase_dec}"),
                ("human", f'this is the output from the pop-detector: {processed_xml}')
            ]

        # Only process image if no XML input is provided
        elif request.image:
            if not validate_base64(request.image):
                raise HTTPException(status_code=400, detail="Invalid base64 image data")

            messages = [
                ("system", image_prompt),
                ("human", f"test-case description: {request.testcase_dec}"),
                ("human", [
                    {"type": "text", "text": "this is the screenshot of the current screen"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{request.image}"},
                    },
                ]),
            ]

        elif request.image_url:
            logger.info(f"image url: {request.image_url}")
            encoded_image = encode_image(request.image_url)
            messages = [
                ("system", image_prompt),
                ("human", f"test-case description: {request.testcase_dec}"),
                ("human", [
                    {"type": "text", "text": "this is the screenshot of the current screen"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"},
                    },
                ]),
            ]

        else:
            raise HTTPException(
                status_code=400, 
                detail="Either XML (string/URL) or image (base64/URL) must be provided."
            )

        ai_msg = llm.invoke(messages)
        logger.info(f"AI message: {ai_msg.content}")

        cleaned_content = ai_msg.content.strip("```json\n").strip("\n```")

        try:
            parsed_output = json.loads(cleaned_content)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse AI message content as JSON. Content: {ai_msg.content}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to parse AI message content as JSON. Content: {ai_msg.content}"
            )
        
        resource_id = parsed_output.get("element_metadata", {}).get("resource_id")
        logger.info(f"Parsed output: {parsed_output}")

        return {
            "status": "success",
            "agent_response": parsed_output
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)