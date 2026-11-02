import os
from google import genai

print("🚀 Testing Gemini AI Connection...")

# Initialize Google GenAI Client SECURELY
api_key = os.environ.get("GEMINI_API_KEY")
ai_client = genai.Client(api_key=api_key)

try:
    response = ai_client.models.generate_content(
        model="gemini-3.8-flash",
        contents="Say hello to the AI CRM developer!"
    )
    print(f"✅ AI Response: {response.text}")
except Exception as e:
    print(f"❌ Error: Make sure your GEMINI_API_KEY environment variable is set. Details: {e}")