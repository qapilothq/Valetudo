# Valetudo: Intelligent Pop-up Handler for Mobile App Testing

## Overview

Valetudo is a powerful FastAPI-based application that automatically detects and analyzes pop-up dialog boxes on Android devices using screenshot analysis and XML parsing. Powered by OpenAI's GPT-4, it provides intelligent recommendations for handling these pop-ups during automated testing.

**Current Status**: Beta version supporting Android XML only. iOS support coming soon.

## Key Features

- Automated pop-up detection and analysis
- Dual input support: Screenshots and XML hierarchy files
- Intelligent handling suggestions powered by GPT-4
- RESTful API for seamless integration
- Detailed element metadata extraction from XML
- Priority-based element selection for close icons
- Multiple dismissal methods with reasoning
- Comprehensive API documentation

## Prerequisites

- Python 3.8 or higher
- OpenAI API key
- FastAPI
- uvicorn
- Pillow (for image processing)
- requests (for URL handling)

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/qapilotio/Valetudo.git
   cd Valetudo
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   - Create a `.env` file in the project root
   - Add your OpenAI API key:
     ```
     OPENAI_API_KEY=your_openai_api_key
     ```

## Quick Start

1. Start the server:

   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. Access the interactive API documentation:
   - OpenAPI UI: `http://localhost:8000/docs`
   - ReDoc UI: `http://localhost:8000/redoc`

## API Reference

### POST /invoke

Analyzes mobile screens for pop-ups and provides handling recommendations.

#### Request Body

```json
{
  "image": "string", // Optional: Base64 encoded image string
  "xml": "string", // Optional: XML as string
  "testcase_desc": "string", // Description of the test case
  "xml_url": "string", // Optional: XML URL
  "image_url": "string" // Optional: Image URL
}
```

**Note**: Either direct input (`image`/`xml`) or URL input (`image_url`/`xml_url`) must be provided.

#### Response Format

For XML input:

```json
{
  "status": "success",
  "agent_response": {
    "popup_detection": "True/False",
    "suggested_action": "string",
    "primary_method": {
      "selection_reason": "string",
      "element_metadata": {
        "id": "string",
        "type": "string",
        "bounds": "string",
        "enabled": "boolean",
        "xpath": "string"
        // ... other element properties
      }
    },
    "alternative_methods": [
      {
        "element_metadata": {
          // ... element properties
        },
        "dismissal_reason": "string"
      }
    ]
  }
}
```

For Image input:

```json
{
  "status": "success",
  "agent_response": {
    "popup_detection": "True/False",
    "suggested_action": "string",
    "primary_method": {
      "element_descriptor": "string", // Natural language description of the element
      "selection_reason": "string"
    },
    "alternate_methods": [
      {
        "element_descriptor": "string", // Natural language description of the element
        "dismissal_reason": "string"
      }
    ]
  }
}
```

### GET /health

Health check endpoint returning application status.

## Project Structure

```
valetudo/
├── main.py          # FastAPI application and endpoints
├── utils.py         # Helper functions and utilities
├── prompts.py       # GPT-4 prompt templates
├── llm.py           # OpenAI integration
├── requirements.txt # Project dependencies
└── .env            # Environment variables
```

## Error Handling

The API implements comprehensive error handling for:

- Invalid input formats
- Missing required fields
- Failed API calls
- Image processing errors
- XML parsing failures

## Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Contact

For questions or support, please contact **[contactus@qapilot.com](mailto:contactus@qapilot.com)**.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
