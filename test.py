'''import google.generativeai as genai

# Test your API key
api_key = "AIzaSyCBJenx0u3MBHtHTaQro484kugbUbX_Uco"
genai.configure(api_key=api_key)

# List available models
models = genai.list_models()
for model in models:
    print(f"Model: {model.name}")
    if 'generateContent' in model.supported_generation_methods:
        print(f"  ✅ Supports generateContent")'''

import google.generativeai as genai
import os
from dotenv import load_dotenv
import sys

print(f"--- Starting API Test ---")
print(f"Python version: {sys.version.split()[0]}")
print(f"google.genai version: {genai.__version__}")

# 1. Load the .env file
try:
    load_dotenv()
    print("Loaded .env file.")
except Exception as e:
    print(f"ERROR: Could not load .env file: {e}")
    exit()

# 2. Get the API key
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("ERROR: GOOGLE_API_KEY not found in .env file.")
    print("Please check your .env file is in the same directory and the variable name is correct.")
    exit()

if len(api_key) < 40:
     print(f"WARNING: API key seems short. Key: {api_key[:4]}...")
else:
     print("API key loaded successfully.")

# 3. Configure and Test the API
try:
    genai.configure(api_key=api_key)
    
    print("Configured genai. Attempting to create model...")
    # We use 'gemini-pro' as it's the standard, most compatible model
    model = genai.GenerativeModel('models/gemini-flash-latest')
    
    print("Model created. Sending test message...")
    response = model.generate_content("This is a test.")
    
    print("\n--- TEST SUCCESSFUL! ---")
    print(response.text)
    print("--------------------------")

except Exception as e:
    print("\n--- API TEST FAILED ---")
    print("An error occurred. Here is the full error message:")
    print("-------------------------------------------------")
    print(e)
    print("-------------------------------------------------")