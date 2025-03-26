#!/usr/bin/env python3
"""
Script to create default AI prompts for company database.
Run this script when setting up the application to initialize useful prompts.
"""

import os
import sys
from datetime import datetime
from pymongo import MongoClient
from bson.objectid import ObjectId

# Database connection string
MONGO_URI = 'mongodb+srv://wQO7zLNOVMMbbJOU:B9BYNLyVR4YgkOv3@vellichormedia.woofq.mongodb.net/company_database?retryWrites=true&w=majority&appName=vellichormedia'

def create_default_prompts():
    """Create default AI prompts in the database."""
    try:
        # Connect to MongoDB
        client = MongoClient(MONGO_URI)
        db = client.company_database
        
        # Check if prompts already exist
        existing_count = db.ai_prompts.count_documents({})
        if existing_count > 0:
            print(f"Found {existing_count} existing prompts. Do you want to add default prompts anyway? (y/n)")
            response = input().lower()
            if response != 'y':
                print("Operation cancelled.")
                return
        
        # Default prompts
        default_prompts = [
            {
                "name": "General Company Info (All Fields)",
                "description": "Extract general company information from the website.",
                "target_field": "general",
                "value": """Visit the website {company_website} and extract the following information about the company:

1. Company Name: What is the official name of the company? If you can't find it, use '{company_name}' as a fallback.
2. Products: What main products does the company offer?
3. Services: What services does the company provide?
4. Location: Where is the company based? Include city, state, country if available.
5. Industry: What industry does the company operate in?
6. Description: A brief 1-2 sentence description of the company.
7. Keywords: 3-5 relevant keywords for the company's business.

Format your response simply as:
name: [company name]
products: [products]
services: [services]
location: [location]
industry: [industry]
description: [description]
keyword: [keywords]

Only include fields you find information for. If you can't find information for a field, omit it."""
            },
            {
                "name": "Company Name Extraction",
                "description": "Extract just the company name from the website.",
                "target_field": "name",
                "value": """Visit the website {company_website} and determine the official name of the company.

Look for:
- The logo alt text
- About us page
- Copyright information in the footer
- Contact page
- Legal documents or Terms of Service

Return ONLY the company name using this format:
name: [full official company name]

If you cannot find a clear company name, return what you believe is the most likely name based on the website content. Do not include legal entities (LLC, Inc, etc.) unless they are clearly part of the official name."""
            },
            {
                "name": "Products Analysis",
                "description": "Extract the products offered by the company.",
                "target_field": "products",
                "value": """Visit the website {company_website} and analyze what products the company offers.

Look for:
- Product pages or catalogs
- Product lists or menus
- Product-related images with descriptions
- "Our Products" or similar sections

Return ONLY the products using this format:
products: [concise list of the main products offered by the company]

Keep your response concise but comprehensive, focusing on the primary products rather than every product variation."""
            },
            {
                "name": "Services Analysis",
                "description": "Extract the services offered by the company.",
                "target_field": "services",
                "value": """Visit the website {company_website} and analyze what services the company offers.

Look for:
- Services pages
- "What we do" sections
- Service lists or menus
- Case studies or portfolio examples

Return ONLY the services using this format:
services: [concise list of the main services offered by the company]

Keep your response concise but comprehensive, focusing on the primary service categories rather than every variation."""
            },
            {
                "name": "Location Extraction",
                "description": "Determine the company's location(s).",
                "target_field": "location",
                "value": """Visit the website {company_website} and determine the company's location.

Look for:
- Contact page
- Footer information
- Office/locations page
- Store locator
- About us section

Return ONLY the location information using this format:
location: [primary location of the company]

If the company has multiple locations, focus on the headquarters or main location. Include city, state/province, and country if available."""
            },
            {
                "name": "Keywords Generation",
                "description": "Generate relevant keywords for the company.",
                "target_field": "keyword",
                "value": """Visit the website {company_website} and analyze its content to generate 3-5 relevant keywords or tags that best describe the company's business.

Consider:
- The company's industry
- Products or services offered
- Target markets or customers
- Unique selling propositions
- Recurring themes or terminology

Return ONLY the keywords using this format:
keyword: [keyword1, keyword2, keyword3, ...]

Keep each keyword short (preferably 1-2 words) and highly relevant to the company's core business."""
            },
            {
                "name": "Bedrock Company Analysis",
                "description": "Amazon Bedrock optimized prompt for company analysis.",
                "target_field": "general",
                "value": """Analyze the website {company_website} and extract key business information.

Return ONLY the following fields if you can find information about them:
1. name: [Official company name]
2. products: [Main products offered]
3. services: [Main services provided] 
4. location: [Company headquarters or main location]
5. keyword: [3-5 relevant industry keywords]

Return your findings in a simple field:value format, only including fields you found information for. Do not include any explanations or analysis."""
            },
            {
                "name": "Bedrock Name Extraction",
                "description": "Amazon Bedrock optimized prompt for company name extraction.",
                "target_field": "name",
                "value": """Visit {company_website} and determine the official company name.

Return ONLY the company name in this exact format:
name: [company name]

Do not include any explanations or additional information."""
            },
            {
                "name": "Bedrock Products Extraction",
                "description": "Amazon Bedrock optimized prompt for product extraction.",
                "target_field": "products",
                "value": """Visit {company_website} and identify the main products offered by the company.

Return ONLY the products in this exact format:
products: [list of main products]

Do not include any explanations or additional information."""
            },
            {
                "name": "Bedrock Services Extraction",
                "description": "Amazon Bedrock optimized prompt for services extraction.",
                "target_field": "services",
                "value": """Visit {company_website} and identify the main services offered by the company.

Return ONLY the services in this exact format:
services: [list of main services]

Do not include any explanations or additional information."""
            },
            {
                "name": "Bedrock Location Extraction",
                "description": "Amazon Bedrock optimized prompt for location extraction.",
                "target_field": "location",
                "value": """Visit {company_website} and determine the company's primary location or headquarters.

Return ONLY the location in this exact format:
location: [company location]

Do not include any explanations or additional information."""
            },
            {
                "name": "Bedrock Keywords Generation",
                "description": "Amazon Bedrock optimized prompt for keywords generation.",
                "target_field": "keyword",
                "value": """Visit {company_website} and generate 3-5 relevant business keywords.

Return ONLY the keywords in this exact format:
keyword: [keyword1, keyword2, keyword3]

The keywords should be related to the company's industry, products, or services.
Do not include any explanations or additional information."""
            },
            {
                "name": "MCP Protocol Company Analysis",
                "description": "Advanced company analysis using the MCP protocol framework.",
                "target_field": "general",
                "value": """### TASK:
Using the MCP (Multi-Context Processing) protocol, analyze the website {company_website} for a company{' named ' + company_name if company_name else ''} and extract structured business information.

### CONTEXT:
You are performing standardized information extraction following the MCP protocol, which requires precise, structured output without commentary.

### REQUIRED INFORMATION:
Extract the following business information:
- name: The official company name
- products: All main products offered by the company
- services: All main services provided by the company
- location: Company headquarters and main office locations
- description: A concise description of what the company does
- industry: The industry or sector the company operates in
- keyword: Relevant keywords or tags for the company's business

### OUTPUT FORMAT:
Return ONLY a clean JSON object containing the requested fields:
```json
{
  "name": "Company Name Inc.",
  "products": ["Product 1", "Product 2"],
  "services": ["Service 1", "Service 2"],
  "location": ["City, State, Country"],
  "description": "Brief company description",
  "industry": "Industry name",
  "keyword": ["Keyword1", "Keyword2"]
}
```

### IMPORTANT RULES:
1. Return arrays for lists (products, services, location, keyword)
2. Return string values for single items (name, description, industry)
3. Use empty arrays [] or empty strings "" for missing information
4. Do not include explanatory text outside the JSON structure
5. Maintain MCP protocol compliance by avoiding personal opinions or commentary
"""
            },
            {
                "name": "MCP Protocol Name Extraction",
                "description": "Extract company name using the MCP protocol.",
                "target_field": "name",
                "value": """### TASK:
Using the MCP protocol, visit {company_website} and determine the official company name.

### CONTEXT:
You are performing precise information extraction according to MCP standards, which require standardized output without commentary.

### REQUIRED INFORMATION:
- The official, legal name of the company as it appears on the website
- Look in headers, footers, about pages, contact information, and copyright notices

### OUTPUT FORMAT:
Return ONLY a JSON object with the name field:
```json
{
  "name": "Company Name Inc."
}
```

### IMPORTANT RULES:
1. Return only the official company name
2. Do not include legal entity designations unless they are part of the official name
3. Include no text outside the JSON structure
4. MCP protocol requires exact extraction without personal commentary
"""
            },
            {
                "name": "MCP Protocol Products Extraction",
                "description": "Extract products using the MCP protocol.",
                "target_field": "products",
                "value": """### TASK:
Using the MCP protocol, visit {company_website} and extract all main products offered by the company.

### CONTEXT:
You are performing precise information extraction according to MCP standards, which require standardized output without commentary.

### REQUIRED INFORMATION:
- All main product offerings
- Look in product pages, catalogs, homepage features, and solution sections

### OUTPUT FORMAT:
Return ONLY a JSON object with the products field as an array:
```json
{
  "products": ["Product 1", "Product 2", "Product 3"]
}
```

### IMPORTANT RULES:
1. Return an array even if only one product is found
2. List each product separately in the array
3. Use consistent naming as shown on the website
4. Include no text outside the JSON structure
5. MCP protocol requires exact extraction without personal commentary
"""
            },
            {
                "name": "LinkedIn Enhanced Company Analysis",
                "description": "Extract company information from website and LinkedIn.",
                "target_field": "general",
                "value": """Visit the company website {company_website} and, if available, their LinkedIn company page to extract comprehensive business information.

PRIORITIZE LINKEDIN DATA for company name, industry, and location as it tends to be more accurate and standardized.

Extract the following information:
- Company name (official legal name)
- Products (main products offered)
- Services (main services provided)
- Location (headquarters and main office locations)
- Description (concise summary of what the company does)
- Industry (main industry or sector)
- Keywords (relevant business keywords)

Return ONLY the information with clear labels:

COMPANY NAME: [official company name]
PRODUCTS: [list of products, comma separated]
SERVICES: [list of services, comma separated]
LOCATION: [headquarters location, comma separated if multiple]
DESCRIPTION: [brief company description]
INDUSTRY: [main industry]
KEYWORDS: [relevant keywords, comma separated]

Only include fields where you can find information. Be concise and accurate.
"""
            },
        ]
        
        # Insert prompts
        now = datetime.now()
        for prompt in default_prompts:
            prompt["created_at"] = now
            prompt["updated_at"] = now
            existing = db.ai_prompts.find_one({"name": prompt["name"]})
            if not existing:
                result = db.ai_prompts.insert_one(prompt)
                print(f"Added prompt: {prompt['name']}")
            else:
                print(f"Skipped existing prompt: {prompt['name']}")
        
        print(f"Created {len(default_prompts)} default prompts.")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    create_default_prompts() 