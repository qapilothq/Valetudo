from typing import Any
import xml.etree.ElementTree as ET
import base64
import os
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import uuid
from logger_config import logger
from typing import Any, Union, Dict, List

# import matplotlib.pyplot as plt

def extract_popup_details(xml_input) -> Dict[str, Union[bool, List[Any], Dict[Any, Any]]]:   
    """
    Determines if the given XML represents a popup and extracts its context (non-clickable text and images)
    as well as interactable (clickable) elements.
    
    Args:
        xml_input (str): XML file path, URL, or XML content representing the screen hierarchy
    
    """
    try:
        # Parse XML input.
        if isinstance(xml_input, str):
            if xml_input.startswith('http://') or xml_input.startswith('https://'):
                response = requests.get(xml_input)
                response.raise_for_status()
                xml_content = response.text
                root = ET.fromstring(xml_content)
            elif os.path.isfile(xml_input):
                tree = ET.parse(xml_input)
                root = tree.getroot()
            else:
                root = ET.fromstring(xml_input)
        else:
            raise ValueError("Invalid XML input type.")
        
        # Extract screen dimensions (default to 0 if not provided).
        screen_width = int(root.get('width', 0))
        screen_height = int(root.get('height', 0))
        
        # Result dictionary with context elements (non-clickable) and interactable elements.
        popup_result = {
            'is_popup': False,
            'content': [],               # Non-clickable context elements (text and images)
            'interactable_elements': {}, # Clickable elements (including clickable images) as a dictionary
            'details': {}
        }
        
        # Mutable counter for interactable element IDs.
        element_counter = [1]  # Using a list so inner functions can update it.

        # Helper functions to compute an element's absolute XPath.
        def find_path_to_target(current, target):
            if current is target:
                return [current]
            for child in list(current):
                subpath = find_path_to_target(child, target)
                if subpath is not None:
                    return [current] + subpath
            return None

        def compute_xpath_from_path(path):
            xpath = ''
            for i, node in enumerate(path):
                if i == 0:
                    xpath += f'/{node.tag}'
                else:
                    parent = path[i - 1]
                    # Calculate the position index among siblings with the same tag.
                    siblings = [c for c in list(parent) if c.tag == node.tag]
                    index = siblings.index(node) + 1
                    xpath += f'/{node.tag}[{index}]'
            return xpath

        def get_xpath(target):
            path = find_path_to_target(root, target)
            if path is not None:
                return compute_xpath_from_path(path)
            return ''

        # Find potential popup layouts using common XPath queries.
        popup_layouts = [
            './/android.widget.FrameLayout', 
            './/android.app.Dialog', 
            './/android.widget.PopupWindow',
            './/androidx.appcompat.app.AlertDialog'
        ]
        
        # Iterate through potential popup layouts.
        for layout_xpath in popup_layouts:
            first_component = root.find(layout_xpath)
            if first_component is None:
                continue
            
            # Extract bounds (expected format: "[x1,y1][x2,y2]").
            bounds = first_component.get('bounds', '')
            try:
                bounds_parts = bounds.strip('[]').split('][')
                x1, y1 = map(int, bounds_parts[0].split(','))
                x2, y2 = map(int, bounds_parts[1].split(','))
            except (ValueError, IndexError):
                continue
            
            # Calculate dimensions and center position.
            component_width = x2 - x1
            component_height = y2 - y1
            component_center_x = (x1 + x2) / 2
            component_center_y = (y1 + y2) / 2
            
            # Determine if the component qualifies as a popup.
            screen_area = screen_width * screen_height
            component_area = component_width * component_height
            area_ratio = component_area / screen_area if screen_area else 0
            
            if area_ratio < 1:
                popup_result['is_popup'] = True
                popup_result['details'] = {
                    'width': component_width,
                    'height': component_height,
                    'center_x': component_center_x,
                    'center_y': component_center_y
                }
            
            # Extraction functions.
            def extract_text(element):
                # Add non-clickable text elements as context (type "text").
                for elem in element.findall('.//*[@text]'):
                    text = elem.get('text', '')
                    clickable = elem.get('clickable', 'false') == 'true'
                    if text and not clickable:
                        popup_result['content'].append({
                            'xpath': get_xpath(elem),
                            'type': 'text',
                            'text': text
                        })
            
            def extract_actions(element):
                # Add clickable elements (all get an element_id).
                clickable_elements = element.findall('.//*[@clickable="true"]')
                for action_elem in clickable_elements:
                    element_id = str(element_counter[0]) 
                    action_details = {
                        '_id': element_id,
                        'text': action_elem.get('text', ''),
                        'resouce_id': action_elem.get('resource-id', ''),
                        'type': action_elem.tag.split('.')[-1],
                        'bounds': action_elem.get('bounds', ''),
                        'content_desc': action_elem.get('content-desc', ''),
                        'enabled': action_elem.get('enabled', 'true') == 'true',
                        'focused': action_elem.get('focused', 'false') == 'true',
                        'scrollable': action_elem.get('scrollable', 'false') == 'true',
                        'long_clickable': action_elem.get('long-clickable', 'false') == 'true',
                        'password': action_elem.get('password', 'false') == 'true',
                        'selected': action_elem.get('selected', 'false') == 'true',
                        'xpath': get_xpath(action_elem),
                    }
                    popup_result.get('interactable_elements', {})[element_id] = action_details
                    element_counter[0] += 1
            
            def extract_non_clickable_images(element):
                # Look for image-related tags and add non-clickable images as context (type "image").
                image_tags = [
                    './/android.widget.ImageView',
                    './/android.widget.ImageButton',
                    './/android.widget.Image'
                ]
                for tag in image_tags:
                    for img_elem in element.findall(tag):
                        if img_elem.get('clickable', 'false') == 'true':
                            continue  # Already captured as an interactable element.
                        img_context = {
                            'xpath': get_xpath(img_elem),
                            'type': 'image',
                            'resource_id': img_elem.get('resource-id', ''),
                            'content_desc': img_elem.get('content-desc', ''),
                            'bounds': img_elem.get('bounds', '')
                        }
                        drawable = img_elem.get('src', '')
                        if drawable or img_context['resource_id'] or img_context['content_desc']:
                            popup_result['content'].append(img_context)
            
            # Apply extraction functions on the found component, regardless of popup status.
            extract_text(first_component)
            extract_actions(first_component)
            extract_non_clickable_images(first_component)
        
        logger.info(f"XML parsing output to check for popups using rules: {popup_result}")
        return popup_result
    
    except ET.ParseError as e:
        logger.error(f"XML Parse Error: {e}")
        return {
            'is_popup': False,
            'content': [],
            'interactable_elements': {},
            'details': {}
        }
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {
            'is_popup': False,
            'content': [],
            'interactable_elements': {},
            'details': {}
        }

def process_actionable_elements(actionable_elements) -> dict[Any, Any]:

    actionable_element_dict = {}

    for element in actionable_elements:

        element_description = (element.get('text', '') + " " + element.get('contentdesc', '')).strip()
        if not element_description:
            element_description = element.get('resourceid').strip()
        processed_attributes = {
                "xpath": element.get('xpath', ''),
                "customxpath": element.get('customxpath', ''),
                "content_desc": element.get('contentdesc', ''),
                "resource_id": element.get('resourceid', '')
            }
        
        attributes = element.get('attributes')
        for attribute in attributes:
            if "name" in attribute and "value" in attribute:
                processed_attributes[attribute['name']] = attribute['value']

        processed_element = {
            "node_id": element.get('elementId'),
            "description": element_description,
            "heuristic_score": 0,
            "attributes": processed_attributes
        }

        actionable_element_dict[str(element.get('elementId'))] = processed_element

    return actionable_element_dict

def annotate_image_using_actionable_elements(base64_image, actionable_element_dict):
    """
    Annotate the image with bounding boxes and element IDs for all interactable elements.
    
    Args:
        base64_image (str): Base64 encoded image string
        xml_data (dict): Processed XML data containing interactable elements
        
    Returns:
        str: Base64 encoded annotated image
    """


    # Decode base64 image

    # print(xml_data)
    image_data = base64.b64decode(base64_image)
    image = Image.open(BytesIO(image_data))

    if image.mode == 'RGBA':
        image = image.convert('RGB')
    draw = ImageDraw.Draw(image)
    
    # Try to load a font, use default if not available
    try:
        font = ImageFont.truetype("Arial.ttf", 50)
    except IOError:
        font = ImageFont.load_default()
    

    # Draw bounding boxes and element IDs for all interactable elements
    if actionable_element_dict:
        for element_id, element_data in actionable_element_dict.items():
            attributes = element_data.get('attributes', {})
            bounds = None
            if attributes and "bounds" in attributes:
                bounds = attributes.get("bounds")
            elif "bounds" in element_data:
                bounds = element_data.get("bounds")
            if isinstance(bounds, str):
                # Parse bounds string like "[0,0][100,100]"
                coords = bounds.replace("][", ",").strip("[]").split(",")
                if len(coords) == 4:
                    x1, y1, x2, y2 = map(int, coords)
                    # Draw rectangle
                    draw.rectangle([(x1, y1), (x2, y2)], outline="red", width=3)  # Increased outline width
                    # Draw element ID
                    draw.text((x1-30, y1-30), str(element_id), fill="red", font=font)  # Position text at top-left corner

    # plt.figure(figsize=(8, 8))
    # plt.imshow(image)
    # plt.axis('off')  # Hide the axis
    # plt.show()
    # Convert back to base64
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    annotated_base64 = base64.b64encode(buffered.getvalue()).decode()

    # Ensure the directory exists
    os.makedirs("screenshot_combined_debug", exist_ok=True)

    # Generate a unique filename using a timestamp and UUID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex
    filename = f"screenshot_combined_debug/annotated_image_{timestamp}_{unique_id}.jpg"

    # Save the annotated image
    try:
        image.save(filename)
        print(f"Annotated image saved as {filename}")
    except Exception as e:
        print(f"Error saving annotated image: {e}")

    return annotated_base64

def annotate_image_using_xml(base64_image, xml_data):
    """
    Annotate the image with bounding boxes and element IDs for all interactable elements.
    
    Args:
        base64_image (str): Base64 encoded image string
        xml_data (dict): Processed XML data containing interactable elements
        
    Returns:
        str: Base64 encoded annotated image
    """


    # Decode base64 image

    print(xml_data)
    image_data = base64.b64decode(base64_image)
    image = Image.open(BytesIO(image_data))

    if image.mode == 'RGBA':
        image = image.convert('RGB')
    draw = ImageDraw.Draw(image)
    
    # Try to load a font, use default if not available
    try:
        font = ImageFont.truetype("Arial.ttf", 50)
    except IOError:
        font = ImageFont.load_default()
    

    # Draw bounding boxes and element IDs for all interactable elements
    if xml_data and "interactable_elements" in xml_data:
        for element_id, element_data in xml_data["interactable_elements"].items():
            if "bounds" in element_data:
                bounds = element_data["bounds"]
                if isinstance(bounds, str):
                    # Parse bounds string like "[0,0][100,100]"
                    coords = bounds.replace("][", ",").strip("[]").split(",")
                    if len(coords) == 4:
                        x1, y1, x2, y2 = map(int, coords)
                        # Draw rectangle
                        draw.rectangle([(x1, y1), (x2, y2)], outline="red", width=3)  # Increased outline width
                        # Draw element ID
                        draw.text((x1-30, y1-30), element_id, fill="red", font=font)  # Position text at top-left corner


    
    # plt.figure(figsize=(8, 8))
    # plt.imshow(image)
    # plt.axis('off')  # Hide the axis
    # plt.show()
    # Convert back to base64
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    annotated_base64 = base64.b64encode(buffered.getvalue()).decode()

    # Ensure the directory exists
    os.makedirs("screenshot_combined_debug", exist_ok=True)

    # Generate a unique filename using a timestamp and UUID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex
    filename = f"screenshot_combined_debug/annotated_image_{timestamp}_{unique_id}.jpg"

    # Save the annotated image
    try:
        image.save(filename)
        print(f"Annotated image saved as {filename}")
    except Exception as e:
        print(f"Error saving annotated image: {e}")

    return annotated_base64

def encode_image(input_source):
    """
    Encodes an image from a file path, file object, or URL into a base64 string.

    Args:
    input_source (str or file-like object): The image file path, file object, or URL.

    Returns:
    str: Base64 encoded string of the image.
    """
    try:
        if isinstance(input_source, str):
            # Check if it's a URL
            if input_source.startswith('http://') or input_source.startswith('https://'):
                response = requests.get(input_source)
                response.raise_for_status()
                image_data = response.content
            # Check if it's a file path
            elif os.path.isfile(input_source):
                with open(input_source, 'rb') as image_file:
                    image_data = image_file.read()
            else:
                raise ValueError("Invalid file path or URL.")
        else:
            # Assume it's a file-like object
            image_data = input_source.read()

        # Encode the image data
        encoded_image = base64.b64encode(image_data).decode()
        return encoded_image

    except Exception as e:
        print(f"Error encoding image: {e}")
        return None