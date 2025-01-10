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
  "testcase_desc": "Login screen permission popup",
  "image": "string",  // Optional: File path or URL
  "xml": "string"     // Optional: File path or URL
}
```

**Note**: Either `image` or `xml` must be provided. When both are present, XML analysis takes precedence.

#### Response Format

```json
{
  "status": "success",
  "agent_response": {
    "popup_detection": "Yes/No",
    "suggested_action": "string",
    "element_metadata": {  // Only present with XML input
      "element_type": "string",
      "element_details": "string",
      "resource_id": "string",
      "bounds": "string",
      "clickable": "boolean",
      "class_name": "string",
      "text": "string",
      "xpath": "string"
    }
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
