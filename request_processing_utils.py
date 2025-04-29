from typing import Any
from prompts import image_prompt, combined_prompt, xml_prompt
from logger_config import logger
from fastapi import HTTPException
import json
import os
from llm import initialize_llm
from utils import annotate_image_using_actionable_elements, process_actionable_elements
from dotenv import load_dotenv


load_dotenv()

llm_key = os.getenv("OPENAI_API_KEY")
if not llm_key:
    raise HTTPException(status_code=500, detail="API key not found. Please check your environment variables.")
llm = initialize_llm(llm_key)

def clean_markdown_json(content):
    if content.startswith("```json\n"):
        content = content[8:]
    elif content.startswith("```json"):
        content = content[7:]
    
    # Remove the closing fence
    if content.endswith("\n```"):
        content = content[:-4]
    elif content.endswith("```"):
        content = content[:-3]
    
    # Fix Python booleans to be JSON compatible
    content = content.replace("True", "true").replace("False", "false")
    
    return content


def trigger_llm(messages) -> dict[Any, Any]:
    ai_msg = llm.invoke(messages)
    logger.info(f"AI message: {str(ai_msg.content)}")

    # Clean and parse the AI response
    cleaned_content = clean_markdown_json(ai_msg.content)
    try:
        parsed_output = json.loads(cleaned_content)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse AI message content as JSON. Content: {ai_msg.content}")
        parsed_output = {}
    logger.info(f"Parsed output: {parsed_output}")

    return parsed_output


def process_request_with_image_only(request, encoded_image):
    messages = [
        ("system", image_prompt),
        ("human", f"Test case description: {request.testcase_desc}"),
        ("human", [
            {"type": "text", "text": "Screenshot of current screen"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}}
        ])
    ]

    parsed_output = trigger_llm(messages=messages)

    # Image-only case: Return parsed output directly
    final_response = {
        "status": "success",
        "message": "success",
        "agent_response": parsed_output
    }

    return final_response

def process_request_with_xml_only(request, processed_xml):
    messages = [
        ("system", xml_prompt),
        ("human", f"Test case description: {request.testcase_desc}"),
        ("human", f"Pop-up detector output: {processed_xml}")
    ]

    parsed_output = trigger_llm(messages=messages)

    # XML-only case: Check processed_xml for popup detection
    if not processed_xml.get("is_popup", False):
        final_response = {"status": "success", "message": "success", "agent_response": {"popup_detection": False}}
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
                "message": "success",
                "agent_response": {
                    "popup_detection": parsed_output.get("popup_detection", True),
                    "suggested_action": parsed_output.get("suggested_action", ""),
                    "primary_method": {
                        "selection_reason": primary_selection_reason,
                        "element_metadata": primary_metadata or {}
                    },
                    "alternative_methods": alternative_methods_mapped
                }
            }
        except Exception as e:
            logger.error(f"Error mapping LLM output to element metadata: {e}")
            final_response = {
                "status": "failed", 
                "message": "Error mapping LLM output to element metadata",
                "agent_response": {
                    "popup_detection": True,
                    "suggested_action": "",
                    "primary_method": {},
                    "alternative_methods": []
                }
            } 

    return final_response

def process_request_with_image_and_actionable_elements(request, actionable_element_dict, encoded_image):
    logger.info("Both image and actionable elements provided")
    logger.debug(f"Number of actionable elements: {len(request.actionable_elements)}")
    actionable_element_dict = process_actionable_elements(request.actionable_elements)
    annotated_image = annotate_image_using_actionable_elements(base64_image=encoded_image, actionable_element_dict=actionable_element_dict)
    messages = [
        ("system", combined_prompt),
        ("human", f"Test case description: {request.testcase_desc}"),
        ("human", [
            {"type": "text", "text": "Screenshot of current screen with annotated element IDs"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{annotated_image}"}}
        ])
    ]

    parsed_output = trigger_llm(messages=messages)

    # Combined case: Trust LLM's popup detection from image analysis
    if parsed_output.get("popup_detection", True) == False:
        final_response = {"status": "success", "message": "success", "agent_response": {"popup_detection": False}}
    else:
        try:
            # Map primary method
            primary_method_ai = parsed_output.get("primary_method", {})
            primary_id = primary_method_ai.get("_id", "")
            primary_selection_reason = primary_method_ai.get("selection_reason", "")
            primary_metadata = actionable_element_dict.get(primary_id, {})
            
            # Map alternative methods
            alternative_methods_ai = parsed_output.get("alternate_methods", [])
            alternative_methods_mapped = []
            for method in alternative_methods_ai:
                alt_id = method.get("_id", "")
                alt_dismissal_reason = method.get("dismissal_reason", "")
                alt_metadata = actionable_element_dict.get(alt_id, {})
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
                    "popup_detection": True,
                    "suggested_action": parsed_output.get("suggested_action", ""),
                    "primary_method": {
                        "selection_reason": primary_selection_reason,
                        "element_metadata": primary_metadata or {}
                    },
                    "alternative_methods": alternative_methods_mapped
                }
            }
        except Exception as e:
            logger.error(f"Error mapping LLM output to element metadata: {e}")
            final_response = {
                "status": "failed", 
                "message": "Error mapping LLM output to element metadata",
                "agent_response": {
                    "popup_detection": True,
                    "suggested_action": "",
                    "primary_method": {},
                    "alternative_methods": []
                }
            } 
    
    return final_response
