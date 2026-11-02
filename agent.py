import os
import sqlite3
from google import genai
from google.genai import types

def get_db():
    conn = sqlite3.connect('crm_enterprise.db')
    conn.row_factory = sqlite3.Row 
    return conn

def get_leads_from_db(grade_filter: str = "ALL"):
    conn = get_db()
    if grade_filter == "ALL":
        results = conn.execute("SELECT name, phone, course, grade FROM leads").fetchall()
    else:
        results = conn.execute("SELECT name, phone, course, grade FROM leads WHERE grade LIKE ?", (f"%{grade_filter}%",)).fetchall()
    conn.close()
    if not results:
        return "No leads found for this criteria."
    return str([dict(row) for row in results])

# Initialize Google GenAI Client SECURELY
api_key = os.environ.get("GEMINI_API_KEY")
ai_client = genai.Client(api_key=api_key)

crm_agent = ai_client.chats.create(
    model="gemini-3.8-flash",
    config=types.GenerateContentConfig(
        tools=[get_leads_from_db],
        temperature=0.2
    )
)

print("🤖 CRM Agent Local Test Ready. Type 'exit' to quit.")
while True:
    user_input = input("\nYou: ")
    if user_input.lower() == 'exit':
        break
    try:
        response = crm_agent.send_message(user_input)
        print(f"AI: {response.text}")
    except Exception as e:
        print(f"Error: {e}. Check if GEMINI_API_KEY environment variable is set.")