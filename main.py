from request_processing_utils import process_request_with_image_and_actionable_elements, process_request_with_image_only, process_request_with_xml_only
from utils import encode_image, extract_popup_details, process_actionable_elements
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Any
import base64
import json
from logger_config import logger
import time
from fastapi.middleware.cors import CORSMiddleware
from langsmith import traceable


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],  
)

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
    actionable_elements : Optional[list[Any]] = []

def validate_base64(base64_string: str) -> bool:
    try:
        base64.b64decode(base64_string)
        return True
    except Exception:
        return False


@traceable
@app.post("/invoke")
async def run_service(request: APIRequest):
    try:

        processed_xml = None
        encoded_image = None
        actionable_element_dict = {}

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

        if request.actionable_elements:
            actionable_element_dict = process_actionable_elements(request.actionable_elements)
        elif processed_xml:
            actionable_element_dict = processed_xml.get("interactable_elements", {})

        # Case 1: Both image and XML or actionable elements provided
        if encoded_image:
            if actionable_element_dict:
                logger.info("Both image and actionable elements available")
                final_response = process_request_with_image_and_actionable_elements(request=request, encoded_image=encoded_image, actionable_element_dict=actionable_element_dict)
            # Case 3: Only image provided
            else:
                final_response = process_request_with_image_only(request=request, encoded_image=encoded_image)
        # Case 2: Only XML provided
        elif processed_xml:
            final_response = process_request_with_xml_only(request=request, processed_xml=processed_xml)
        else:
            raise HTTPException(
                status_code=400,
                detail="Either XML (string/URL) or image (base64/URL) must be provided."
            )

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
    uvicorn.run(app, host="0.0.0.0", port=8004)