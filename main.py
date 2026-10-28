import os
import sqlite3
import random
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import errors

# --- AI EDU-CRM: Cloud Production Edition (Phase 17) ---

app = FastAPI(title="AI EDU-CRM Enterprise API")

# Configure CORS to allow your GitHub Pages frontend to talk to this Render backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all frontend origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini Client using Render Environment Variables
# IMPORTANT: This safely pulls your key from the cloud, keeping it off GitHub!
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("WARNING: GEMINI_API_KEY not found in environment variables!")
ai_client = genai.Client(api_key=api_key)

def get_db():
    conn = sqlite3.connect('crm_enterprise.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row 
    return conn

# --- IN-MEMORY CACHE ENGINE ---
cache = {
    "dashboard_kpis": {"data": None, "timestamp": 0},
    "leads_list": {"data": None, "timestamp": 0}
}
CACHE_DURATION = 15 # Seconds before cache expires

# --- BUSINESS LOGIC ---
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

# --- PYDANTIC MODELS (The Bouncers) ---
class LoginRequest(BaseModel):
    username: str
    password: str

class LeadCreate(BaseModel):
    name: str
    phone: str
    course: str
    source: str
    assigned_to: str

class PitchRequest(BaseModel):
    lead_id: str

class ChatRequest(BaseModel):
    message: str

# --- API ENDPOINTS ---

@app.get("/")
def read_root():
    return {"status": "online", "system": "AI EDU-CRM Cloud API is running."}

@app.post("/api/login")
def login(req: LoginRequest):
    # System Authentication
    if req.username == "admin" and req.password == "admin123":
        return {"username": req.username, "role": "admin"}
    elif req.username == "rahul" and req.password == "welcome123":
        return {"username": req.username, "role": "counselor"}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/dashboard")
def get_dashboard_kpis():
    current_time = time.time()
    
    # ⚡ Cache Check
    if cache["dashboard_kpis"]["data"] and (current_time - cache["dashboard_kpis"]["timestamp"] < CACHE_DURATION):
        print("⚡ [CACHE HIT] Serving Dashboard KPIs from high-speed memory!")
        return {"kpis": cache["dashboard_kpis"]["data"]}
        
    print("🐌 [CACHE MISS] Querying SQLite Database for KPIs...")
    conn = get_db()
    tot_leads = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    pipe_val = conn.execute("SELECT SUM(score) FROM leads").fetchone()[0] or 0 
    conn.close()
    
    data = {
        "total_leads": tot_leads,
        "enrolled_students": 0,
        "pipeline_value": pipe_val * 1000, 
        "revenue_collected": 0,
        "open_tickets": 0
    }
    
    # Save to Cache
    cache["dashboard_kpis"] = {"data": data, "timestamp": current_time}
    
    return {"kpis": data}

@app.get("/api/leads")
def get_leads():
    current_time = time.time()
    
    if cache["leads_list"]["data"] and (current_time - cache["leads_list"]["timestamp"] < CACHE_DURATION):
        return cache["leads_list"]["data"]
        
    conn = get_db()
    leads = conn.execute("SELECT * FROM leads ORDER BY lead_id DESC").fetchall()
    conn.close()
    
    data = [dict(lead) for lead in leads]
    cache["leads_list"] = {"data": data, "timestamp": current_time}
    return data

@app.post("/api/leads")
def create_new_lead(lead: LeadCreate):
    lead_id = f"L-{random.randint(10000, 99999)}"
    score = calculate_lead_score(lead.phone, lead.source, lead.course)
    grade = get_lead_grade(score)
    
    try:
        conn = get_db()
        # Create table if not exists just in case
        conn.execute('''CREATE TABLE IF NOT EXISTS leads 
                     (lead_id TEXT PRIMARY KEY, name TEXT, phone TEXT UNIQUE, 
                      course TEXT, source TEXT, assigned_to TEXT, status TEXT, 
                      score INTEGER, grade TEXT)''')
        
        conn.execute('''
            INSERT INTO leads (lead_id, name, phone, course, source, assigned_to, status, score, grade) 
            VALUES (?,?,?,?,?,?,?,?,?)
        ''', (lead_id, lead.name, lead.phone, lead.course, lead.source, lead.assigned_to, "NEW", score, grade))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Duplicate Phone Number Detected.")
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
        
    conn.close()
    
    # Invalidate cache so new lead shows up immediately on the dashboard
    cache["dashboard_kpis"]["timestamp"] = 0
    cache["leads_list"]["timestamp"] = 0
    
    return {"message": "Lead created successfully", "lead_id": lead_id, "score": score, "grade": grade}

# --- AI ENDPOINTS ---

def generate_counselor_pitch(name, course, grade):
    prompt = f"Write a short, engaging 2-sentence sales pitch for {name} who is interested in {course}. Their lead grade is {grade}."
    try:
        # ✅ FIXED: Using 2.5 Flash
        response = ai_client.models.generate_content(
            model="gemini-3.1-pro-preview",
            contents=prompt
        )
        return response.text
    except Exception:
        # Fallback if API fails so the frontend doesn't crash
        return f"Hi {name}, we see you're interested in {course}. Let's chat!"

@app.post("/api/pitch")
def generate_ai_pitch_endpoint(req: PitchRequest):
    conn = get_db()
    lead = conn.execute("SELECT * FROM leads WHERE lead_id = ?", (req.lead_id,)).fetchone()
    conn.close()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    pitch_text = generate_counselor_pitch(lead["name"], lead["course"], lead["grade"])
    return {"pitch": pitch_text}

def crm_agent(user_message):
    prompt = f"""You are an AI assistant for an education CRM. 
    A user just asked: "{user_message}"
    Answer them helpfully."""
    try:
        # ✅ FIXED: Using 2.5 Flash
        response = ai_client.models.generate_content(
            model="gemini-3.1-pro-preview",
            contents=prompt
        )
        return response.text
    except errors.ServerError as e:
        # This safely catches the Google API 503 Overloaded error
        raise e

@app.post("/api/chat")
def chat_with_ai(req: ChatRequest):
    try:
        reply_text = crm_agent(req.message)
        return {"reply": reply_text}
    except errors.ServerError:
        raise HTTPException(status_code=503, detail="AI Server is temporarily busy. Please try again.")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error: " + str(e))