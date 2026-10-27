from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import random
import uvicorn
import hashlib
import asyncio
import time
import os  # <-- NEW: Required for environment variables
from google import genai
from google.genai.errors import APIError
from google.genai import types

# --- AI EDU-CRM: Phase 16 (Architecture & Caching) ---

app = FastAPI(title="AI EDU-CRM Enterprise API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Google GenAI Client SECURELY using Environment Variables
api_key = os.environ.get("GEMINI_API_KEY")
ai_client = genai.Client(api_key=api_key)

def get_db():
    conn = sqlite3.connect('crm_enterprise.db')
    conn.row_factory = sqlite3.Row 
    return conn

# --- SECURITY LOGIC: PASSWORD HASHING ---
def hash_password(plain_text_password):
    password_bytes = plain_text_password.encode('utf-8')
    return hashlib.sha256(password_bytes).hexdigest()

# --- BUSINESS LOGIC: LEAD SCORING ---
def calculate_lead_score(phone, source, course):
    score = 20
    if len(phone) >= 10: score += 25
    if 'referral' in source.lower() or 'google' in source.lower(): score += 25
    elif 'instagram' in source.lower(): score += 15
    else: score += 10
    if course: score += 20
    return score

def get_lead_grade(score):
    if score >= 65: return "HOT 🔥"
    elif score >= 40: return "WARM ☀️"
    else: return "COLD ❄"

# --- RESILIENT AI HELPER (PHASE 6) ---
def generate_counselor_pitch(name: str, course: str, grade: str) -> str:
    prompt = f"""
You are an expert Admissions Counselor at 'AI EDU Institute'.
Write a personalized WhatsApp outreach message for a prospective student with these details:
- Student Name: {name}
- Course of Interest: {course}
- Lead Temperature: {grade}

Guidelines:
1. If the lead is 'HOT', emphasize urgency, upcoming cohort dates, and limited remaining seats.
2. If the lead is 'COLD', keep it helpful, zero-pressure, and offer a free curriculum brochure.
3. Keep the entire message under 50 words.
4. Include appropriate emojis and end with a clear question to encourage a reply.
"""
    try:
        response = ai_client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        return response.text.strip()

    except Exception as e:
        print(f"\n[AI Warning] External Gemini API issue: {e}")
        if "HOT" in grade:
            strategy = "We have only 2 seats remaining in our upcoming batch!"
        elif "WARM" in grade:
            strategy = "I would love to walk you through our syllabus and career outcomes."
        else:
            strategy = "Would you like me to send over our free introductory course brochure?"

        return (
            f"Hi {name}! 👋 Admissions team at AI EDU here.\n\n"
            f"I saw you are exploring our {course} program. {strategy}\n\n"
            f"Are you free for a quick 5-minute call today to discuss your goals?"
        )

# --- AI AGENT & TOOL CALLING (PHASE 13) ---
def get_leads_from_db(grade_filter: str = "ALL"):
    """Fetches leads from the CRM database. Can filter by HOT, WARM, or COLD."""
    conn = get_db()
    
    if grade_filter == "ALL":
        results = conn.execute("SELECT name, phone, course, grade FROM leads").fetchall()
    else:
        results = conn.execute("SELECT name, phone, course, grade FROM leads WHERE grade LIKE ?", (f"%{grade_filter}%",)).fetchall()
        
    conn.close()
    
    if not results:
        return "No leads found for this criteria."
    
    return str([dict(row) for row in results])

# Pre-configure the Agent with its Toolbelt
crm_agent = ai_client.chats.create(
    model="gemini-1.5-flash",
    config=types.GenerateContentConfig(
        tools=[get_leads_from_db],
        temperature=0.2
    )
)

# --- PHASE 14: AUTOMATION & BACKGROUND TASKS ---
async def automated_lead_followup():
    """A background worker that runs forever while the server is alive."""
    while True:
        await asyncio.sleep(20)  # Wait for 20 seconds
        
        try:
            conn = get_db()
            # Find ONE lead that hasn't been contacted yet
            uncontacted_lead = conn.execute("SELECT * FROM leads WHERE status = 'NEW' LIMIT 1").fetchone()
            
            if uncontacted_lead:
                lead_name = uncontacted_lead['name']
                lead_id = uncontacted_lead['lead_id']
                
                print(f"\n[⚡ AUTOMATION BOT] Waking up! Found neglected lead: {lead_name}")
                print(f"[⚡ AUTOMATION BOT] Simulating automated follow-up email to {lead_name}...")
                
                # Update the database so we don't email them again
                conn.execute("UPDATE leads SET status = 'CONTACTED' WHERE lead_id = ?", (lead_id,))
                conn.commit()
            
            conn.close()
        except Exception as e:
            print(f"[Automation Error] {e}")

# Trigger the background bot the moment the server boots up
@app.on_event("startup")
async def startup_event():
    print("⚙️ Starting background automation workflows...")
    asyncio.create_task(automated_lead_followup())

# --- PYDANTIC MODELS ---
class LeadCreate(BaseModel):
    name: str
    phone: str
    course: str
    source: str
    assigned_to: str

class PitchRequest(BaseModel):
    lead_id: str

class LoginRequest(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    message: str

# --- GLOBAL CACHE STATE (PHASE 16) ---
DASHBOARD_CACHE = {
    "data": None,
    "last_updated": 0
}

# --- API ENDPOINTS ---
@app.get("/")
def read_root():
    return {"status": "online", "system": "AI EDU-CRM API Server is running."}

@app.post("/api/login")
def login_endpoint(req: LoginRequest):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (req.username,)).fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    attempt_hash = hash_password(req.password)
    if attempt_hash != user["password_hash"]:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    return {
        "message": "Login successful",
        "username": user["username"],
        "role": user["role"]
    }

@app.get("/api/dashboard")
def get_dashboard_kpis():
    current_time = time.time()
    
    if DASHBOARD_CACHE["data"] and (current_time - DASHBOARD_CACHE["last_updated"] < 60):
        print("⚡ [CACHE HIT] Serving Dashboard KPIs from high-speed memory!")
        return DASHBOARD_CACHE["data"]
        
    print("🐌 [CACHE MISS] Querying SQLite Database for KPIs...")
    conn = get_db()
    tot_leads = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    tot_stu = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    pipe_val = conn.execute("SELECT SUM(deal_value) FROM opportunities").fetchone()[0] or 0
    rev = conn.execute("SELECT SUM(amount_paid) FROM students").fetchone()[0] or 0
    open_tcks = conn.execute("SELECT COUNT(*) FROM tickets WHERE status != 'CLOSED'").fetchone()[0]
    conn.close()
    
    fresh_data = {
        "kpis": {
            "total_leads": tot_leads,
            "enrolled_students": tot_stu,
            "pipeline_value": pipe_val,
            "revenue_collected": rev,
            "open_tickets": open_tcks
        }
    }
    
    DASHBOARD_CACHE["data"] = fresh_data
    DASHBOARD_CACHE["last_updated"] = current_time
    
    return fresh_data

@app.get("/api/leads")
def get_leads():
    conn = get_db()
    leads = conn.execute("SELECT * FROM leads").fetchall()
    conn.close()
    return [dict(lead) for lead in leads]

@app.post("/api/leads")
def create_new_lead(lead: LeadCreate):
    lead_id = f"L-{random.randint(10000, 99999)}"
    score = calculate_lead_score(lead.phone, lead.source, lead.course)
    grade = get_lead_grade(score)
    
    try:
        conn = get_db()
        conn.execute('''
            INSERT INTO leads (lead_id, name, phone, course, source, assigned_to, status, score, grade) 
            VALUES (?,?,?,?,?,?,?,?,?)
        ''', (lead_id, lead.name, lead.phone, lead.course, lead.source, lead.assigned_to, "NEW", score, grade))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Duplicate Phone Number Detected.")
    
    conn.close()
    return {"message": "Lead created successfully", "lead_id": lead_id, "score": score, "grade": grade}

@app.post("/api/pitch")
def generate_ai_pitch_endpoint(req: PitchRequest):
    conn = get_db()
    lead = conn.execute("SELECT * FROM leads WHERE lead_id = ?", (req.lead_id,)).fetchone()
    conn.close()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found in Database.")

    pitch_text = generate_counselor_pitch(
        name=lead["name"],
        course=lead["course"],
        grade=lead["grade"]
    )

    return {"pitch": pitch_text}

@app.post("/api/chat")
def chat_with_agent(req: ChatRequest):
    try:
        response = crm_agent.send_message(req.message)
        return {"reply": response.text}
    except Exception as e:
        raise HTTPException(status_code=503, detail="AI Server is temporarily busy. Please try again.")

if __name__ == "__main__":
    print("🚀 Booting Phase 16 API Server (with Caching & Automation) on PORT 8082...")
    uvicorn.run(app, host="127.0.0.1", port=8082)