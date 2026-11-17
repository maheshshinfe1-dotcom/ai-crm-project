import sqlite3
import pandas as pd
import streamlit as st

DB_NAME = "crm_enterprise.db"

def init_all_dbs():
    """Phase 16: Centralized database initialization."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS automation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_name TEXT NOT NULL,
                action_taken TEXT NOT NULL,
                timestamp DATE DEFAULT CURRENT_DATE
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"DB Init Error: {e}")

def load_chat_history(username):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT role, content FROM chat_history WHERE username = ? ORDER BY id ASC", (username,))
        rows = cursor.fetchall()
        conn.close()
        return [{"role": row[0], "content": row[1]} for row in rows]
    except Exception as e:
        st.error(f"Failed to load chat history: {e}")
        return []

def save_chat_message(username, role, content):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chat_history (username, role, content) VALUES (?, ?, ?)", (username, role, content))
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Failed to save chat message: {e}")

def clear_chat_history(username):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_history WHERE username = ?", (username,))
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Failed to clear chat history: {e}")

def get_leads_df():
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT * FROM leads", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Error reading SQLite database: {e}")
        return pd.DataFrame()

def update_leads_db(edited_df):
    try:
        conn = sqlite3.connect(DB_NAME)
        clean_df = edited_df.drop(columns=["grade_clean"], errors="ignore")
        clean_df.to_sql("leads", conn, if_exists="replace", index=False)
        conn.close()
        return True
    except Exception as e:
        st.error(f"Failed to update database: {e}")
        return False

def add_new_lead(name, phone, course, grade):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO leads (name, phone, course, grade) VALUES (?, ?, ?, ?)", (name, phone, course, grade))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Failed to add lead: {e}")
        return False

def run_automation_sweep():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM leads WHERE grade LIKE '%WARM%'")
    warm_leads = cursor.fetchall()
    actions_taken = []
    
    for (name,) in warm_leads:
        cursor.execute(
            "SELECT id FROM automation_logs WHERE lead_name = ? AND action_taken = 'FOLLOW_UP_QUEUED' AND timestamp = CURRENT_DATE",
            (name,)
        )
        if not cursor.fetchone():
            cursor.execute("INSERT INTO automation_logs (lead_name, action_taken) VALUES (?, ?)", (name, 'FOLLOW_UP_QUEUED'))
            actions_taken.append(name)
            
    conn.commit()
    conn.close()
    return actions_taken

# --- AGENT TOOLS ---
def search_leads_tool(course: str = "", grade: str = "") -> str:
    """Search CRM prospects in SQLite by optional course name and/or temperature grade (HOT, WARM, COLD). Leave parameters empty to retrieve all leads."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    query = "SELECT name, phone, course, grade FROM leads WHERE 1=1"
    params = []
    if course:
        query += " AND course LIKE ?"
        params.append(f"%{course.strip()}%")
    if grade:
        query += " AND grade LIKE ?"
        params.append(f"%{grade.strip()}%")
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        return "No matching leads found."
    return "\n".join([f"Name: {r[0]} | Phone: {r[1]} | Course: {r[2]} | Grade: {r[3]}" for r in rows])

def update_lead_grade_tool(lead_name: str, new_grade: str) -> str:
    """Update an existing lead's temperature grade in SQLite. new_grade must be HOT, WARM, or COLD."""
    clean_grade = new_grade.upper().strip()
    if clean_grade not in ["HOT", "WARM", "COLD"]:
        return f"Error: Invalid grade '{new_grade}'."
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE leads SET grade = ? WHERE name LIKE ?", (clean_grade, f"%{lead_name.strip()}%"))
    conn.commit()
    updated_count = cursor.rowcount
    conn.close()
    if updated_count == 0:
        return f"No lead found matching '{lead_name}'."
    return f"Successfully updated {updated_count} lead(s) matching '{lead_name}' to {clean_grade}."

def create_lead_record_tool(name: str, phone: str, course: str, grade: str = "WARM") -> str:
    """Create and save a brand-new prospect lead into the SQLite CRM database. grade defaults to WARM."""
    clean_grade = grade.upper().strip()
    if clean_grade not in ["HOT", "WARM", "COLD"]:
        clean_grade = "WARM"
    if add_new_lead(name.strip(), phone.strip(), course.strip(), clean_grade):
        return f"Created new lead: {name} | Phone: {phone} | Course: {course} | Grade: {clean_grade}."
    return f"Failed to create lead record for {name}."