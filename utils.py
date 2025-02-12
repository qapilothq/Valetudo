import xml.etree.ElementTree as ET
import base64
import os
import requests
from io import BytesIO

def extract_popup_details(xml_input):
    """
    Determines if the given XML represents a popup and extracts its content, actions, and images.
    
    Args:
    xml_input (str): XML file path, URL, or XML content representing the screen hierarchy
    
    Returns:
    dict: A dictionary containing popup details with keys:
        - 'is_popup': Boolean indicating if the layout is a popup
        - 'content': List of text elements within the popup
        - 'actions': List of interactive elements (buttons, clickable items)
        - 'images': List of image details found in the popup
        - 'details': Additional metadata about the popup
    """
    try:
        # Parse XML input
        if isinstance(xml_input, str):
            if xml_input.startswith('http://') or xml_input.startswith('https://'):
                response = requests.get(xml_input)
                response.raise_for_status()  # Raise an error for bad responses
                xml_content = response.text
                root = ET.fromstring(xml_content)
            elif os.path.isfile(xml_input):
                tree = ET.parse(xml_input)
                root = tree.getroot()
            else:
                root = ET.fromstring(xml_input)
        else:
            raise ValueError("Invalid XML input type.")
        
        # ... existing code ...

    except requests.exceptions.RequestException as e:
        print(f"Error accessing XML URL: {e}")
        raise ValueError("Unable to access the XML URL provided.")
    except ET.ParseError as e:
        print(f"XML Parse Error: {e}")
        return {
            'is_popup': False,
            'content': [],
            'actions': [],
            'images': [],
            'details': {}
        }
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {
            'is_popup': False,
            'content': [],
            'actions': [],
            'images': [],
            'details': {}
        }

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