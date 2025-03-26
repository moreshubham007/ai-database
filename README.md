# Company Database Flask Application

A Flask web application for managing company data with MongoDB, featuring user authentication, admin panel, and CSV upload functionality.

## Features

- User authentication (register, login, logout)
- Company management (add, edit, delete)
- CSV upload for bulk company data import
- Admin panel for user management
- Responsive Material Design UI

## Tech Stack

- **Backend**: Flask (Python)
- **Database**: MongoDB
- **Authentication**: Flask-Login
- **Frontend**: Materialize CSS, JavaScript

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/company-database.git
   cd company-database
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   - Create a `.env` file in the project root
   - Add the following variables:
     ```
     MONGO_URI=mongodb+srv://wQO7zLNOVMMbbJOU:B9BYNLyVR4YgkOv3@vellichormedia.woofq.mongodb.net/company_database?retryWrites=true&w=majority&appName=vellichormedia
     SECRET_KEY=your_secret_key_here
     ```

5. Run the application:
   ```
   python app.py
   ```

6. Access the application at `http://localhost:5000`

## Initial Setup

When you first run the application, you'll need to create an admin user:

1. Navigate to `/admin/create_admin`
2. Fill in the admin user details
3. Login with the admin credentials

## CSV Upload Format

The CSV file for bulk company upload should have the following columns:
- `name` (required): Company name
- `website`: Company website URL
- `products`: Products offered by the company
- `services`: Services offered by the company
- `location`: Company location
- `keyword`: Keywords for search

Example: 


# admin 
username: admin
password: 123456 

## AWS Bedrock Integration

This application supports integration with Amazon Bedrock, AWS's fully managed service for foundation models. To use Bedrock in your application:

### Setup

1. Configure AWS Bedrock through the admin panel:
   - Navigate to Admin > AWS Bedrock
   - Enter your AWS Access Key, Secret Key, Region, and select a model
   - Save the configuration and test the connection

2. Required AWS Permissions:
   - Your AWS credentials need `AmazonBedrockFullAccess` policy
   - You must enable the models you want to use in the AWS Bedrock console

### Using Bedrock in Your Code

```python
# Import the LLM connector
from llm import LLMConnector

# Create an instance
llm = LLMConnector()

# Generate text with Bedrock
response = llm.generate_text(
    prompt="Generate a product description for a smart water bottle.",
    provider="bedrock",
    max_tokens=250
)

# Use Bedrock for chat
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Explain AWS Bedrock in simple terms."}
]
response = llm.chat(messages=messages, provider="bedrock")
print(response)
```

### Available Models

The following foundation models are available through Bedrock:

- Amazon Titan Text models (Lite, Express)
- Anthropic Claude models (v2, Instant, Claude 3 Sonnet, Claude 3 Haiku)
- Meta Llama 2 models (13B, 70B)

Note: Model availability depends on your AWS region and account permissions. 