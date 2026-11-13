import streamlit as st
import chromadb
from chromadb.utils import embedding_functions
import sqlite3
import pandas as pd
import uuid
import hashlib
from google import genai
from google.genai import types
from google.genai.errors import ServerError, APIError

# 1. Page Configuration
st.set_page_config(page_title="AI EDU-CRM Enterprise", page_icon="🎓", layout="wide")

# ==========================================
# 🔒 SECURITY GATEWAY
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔒 CRM Security Gateway")
    st.markdown("Please log in to access the Enterprise CRM.")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if username == st.secrets["ADMIN_USER"] and password == st.secrets["ADMIN_PASSWORD"]:
                st.session_state.logged_in = True
                st.session_state.current_user = username
                st.rerun()
            else:
                st.error("❌ Invalid username or password.")
    
    st.stop()

current_user = st.session_state.get("current_user", st.secrets["ADMIN_USER"])

# 2. Cached Database & AI Engine Initialization
@st.cache_resource
def load_engines():
    chroma_client = chromadb.PersistentClient(path="./crm_memory_db")
    embedder = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    collection = chroma_client.get_collection(name="company_policies", embedding_function=embedder)
    ai_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    return collection, ai_client

collection, ai_client = load_engines()

# 3. Database & Multimodal Helpers
def init_chat_db():
    """Creates the chat_history table in SQLite if it does not already exist."""
    try:
        conn = sqlite3.connect("crm_enterprise.db")
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
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Chat DB Init Error: {e}")

def load_chat_history(username):
    """Loads saved messages for the logged-in user from SQLite."""
    try:
        conn = sqlite3.connect("crm_enterprise.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content FROM chat_history WHERE username = ? ORDER BY id ASC",
            (username,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [{"role": row[0], "content": row[1]} for row in rows]
    except Exception as e:
        st.error(f"Failed to load chat history: {e}")
        return []

def save_chat_message(username, role, content):
    """Persists a single chat message into SQLite."""
    try:
        conn = sqlite3.connect("crm_enterprise.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_history (username, role, content) VALUES (?, ?, ?)",
            (username, role, content)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Failed to save chat message: {e}")

def clear_chat_history(username):
    """Deletes all saved messages for the logged-in user."""
    try:
        conn = sqlite3.connect("crm_enterprise.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_history WHERE username = ?", (username,))
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Failed to clear chat history: {e}")

init_chat_db()

def transcribe_audio(audio_bytes):
    """Transcribes WAV audio bytes into plain text using Gemini multimodal input."""
    try:
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                "Transcribe this spoken audio accurately into plain text. Return ONLY the transcribed words with no extra commentary.",
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")
            ]
        )
        return response.text.strip()
    except (ServerError, APIError):
        st.error("⚠️ Google AI transcription endpoint is currently busy. Please try again in a few seconds.")
        return None
    except Exception as e:
        st.error(f"⚠️ Audio transcription error: {e}")
        return None

def get_leads_df():
    try:
        conn = sqlite3.connect("crm_enterprise.db")
        df = pd.read_sql_query("SELECT * FROM leads", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Error reading SQLite database: {e}")
        return pd.DataFrame()

def update_leads_db(edited_df):
    """Overwrites the SQLite leads table with the updated dataframe from the UI."""
    try:
        conn = sqlite3.connect("crm_enterprise.db")
        clean_df = edited_df.drop(columns=["grade_clean"], errors="ignore")
        clean_df.to_sql("leads", conn, if_exists="replace", index=False)
        conn.close()
        return True
    except Exception as e:
        st.error(f"Failed to update database: {e}")
        return False

def get_hot_leads():
    try:
        conn = sqlite3.connect("crm_enterprise.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name, course FROM leads WHERE grade LIKE '%HOT%' LIMIT 5")
        results = cursor.fetchall()
        conn.close()
        if results:
            return "\n".join([f"- {r[0]} (Course: {r[1]})" for r in results])
        return "No HOT leads found at this time."
    except Exception as e:
        return f"Database error: {e}"

def add_new_lead(name, phone, course, grade):
    try:
        conn = sqlite3.connect("crm_enterprise.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO leads (name, phone, course, grade) VALUES (?, ?, ?, ?)",
            (name, phone, course, grade)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Failed to add lead: {e}")
        return False

def add_document_to_db(file_name, file_content):
    try:
        doc_id = str(uuid.uuid4())
        collection.add(
            documents=[file_content],
            metadatas=[{"source": file_name}],
            ids=[doc_id]
        )
        return True
    except Exception as e:
        st.error(f"Vector DB Error: {e}")
        return False

# ==========================================
# --- ADMIN SIDEBAR ---
# ==========================================
with st.sidebar:
    st.markdown(f"👤 **Logged in as:** `{current_user}`")
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.pop("messages", None)
        st.session_state.pop("last_audio_hash", None)
        st.rerun()
        
    st.divider()
    
    st.markdown("### 📄 Teach AI New Rules")
    uploaded_file = st.file_uploader("Upload a .txt policy file", type=["txt"])
    
    if uploaded_file is not None:
        if st.button("🧠 Memorize Document"):
            with st.spinner("Embedding document into vector space..."):
                content = uploaded_file.getvalue().decode("utf-8")
                if add_document_to_db(uploaded_file.name, content):
                    st.success(f"Successfully memorized {uploaded_file.name}!")

    st.divider()

    st.markdown("### 💬 Chat Memory")
    if st.button("🗑️ Clear Chat History"):
        clear_chat_history(current_user)
        st.session_state.messages = []
        st.rerun()

# ==========================================
# CORE CRM APPLICATION 
# ==========================================
tab_chat, tab_analytics = st.tabs(["💬 AI Co-Pilot", "📊 Lead Analytics & BI"])

with tab_chat:
    st.subheader("AI Support & CRM Intelligence")
    st.caption("Type or record a voice question about company policies or lead summaries.")
    
    if "messages" not in st.session_state:
        st.session_state.messages = load_chat_history(current_user)

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Unified Voice + Text Input
    audio_value = st.audio_input("🎙️ Speak your question")
    typed_input = st.chat_input("Ask a question...")

    prompt_to_process = None
    display_user_msg = None

    if audio_value is not None:
        audio_bytes = audio_value.getvalue()
        audio_hash = hashlib.md5(audio_bytes).hexdigest()
        if audio_hash != st.session_state.get("last_audio_hash"):
            st.session_state.last_audio_hash = audio_hash
            with st.spinner("Transcribing voice query..."):
                transcribed = transcribe_audio(audio_bytes)
            if transcribed:
                prompt_to_process = transcribed
                display_user_msg = f"🎙️ {transcribed}"

    if typed_input:
        prompt_to_process = typed_input
        display_user_msg = typed_input

    if prompt_to_process:
        with st.chat_message("user"):
            st.markdown(display_user_msg)
        st.session_state.messages.append({"role": "user", "content": display_user_msg})
        save_chat_message(current_user, "user", display_user_msg)

        with st.chat_message("assistant"):
            user_text = prompt_to_process.lower().strip()

            if user_text in ["hi", "hello", "hey", "how are you", "how are you?"]:
                hidden_context = "The user is saying hello. Greet them politely as the EDU-CRM AI Co-Pilot."
            elif "lead" in user_text or "customer" in user_text or "prospect" in user_text:
                raw_data = get_hot_leads()
                hidden_context = f"The user asked about leads. Here is the raw SQL data:\n{raw_data}\n\nSummarize this professionally."
            else:
                results = collection.query(query_texts=[prompt_to_process], n_results=1)
                raw_data = results['documents'][0][0]
                hidden_context = f"The user asked a policy question. Here is the exact policy text:\n{raw_data}\n\nAnswer using ONLY this policy."

            try:
                master_prompt = f"User Question: '{prompt_to_process}'\n\nInstructions: {hidden_context}"
                response = ai_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=master_prompt
                )
                final_answer = response.text
            except (ServerError, APIError):
                final_answer = f"⚠️ *AI generation endpoint busy. Showing direct database result:*\n\n{hidden_context}"
            except Exception as e:
                final_answer = f"⚠️ *Error generating response:* {e}"

            st.markdown(final_answer)
            st.session_state.messages.append({"role": "assistant", "content": final_answer})
            save_chat_message(current_user, "assistant", final_answer)

with tab_analytics:
    st.subheader("Live CRM Executive Dashboard")
    
    with st.expander("➕ Add New Prospect", expanded=False):
        with st.form("add_lead_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            new_name = col1.text_input("Full Name")
            new_phone = col2.text_input("Phone Number")
            new_course = col1.selectbox("Interested Course", ["SQL", "Python", "AI Engineering", "Data Science Bootcamp", "Python Mastery"])
            new_grade = col2.selectbox("Lead Grade", ["HOT", "WARM", "COLD"])
            
            if st.form_submit_button("💾 Save Lead"):
                if new_name and new_phone:
                    if add_new_lead(new_name, new_phone, new_course, new_grade):
                        st.success(f"Successfully added {new_name} to the CRM!")
                        st.rerun() 
                else:
                    st.error("Please fill in both Name and Phone.")
    
    df_leads = get_leads_df()

    if not df_leads.empty:
        df_leads['grade_clean'] = df_leads['grade'].str.upper().str.strip()

        total_leads = len(df_leads)
        hot_count = len(df_leads[df_leads['grade_clean'].str.contains("HOT", na=False)])
        warm_count = len(df_leads[df_leads['grade_clean'].str.contains("WARM", na=False)])
        cold_count = len(df_leads[df_leads['grade_clean'].str.contains("COLD", na=False)])

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Prospects", total_leads)
        col2.metric("🔥 Hot Leads", hot_count)
        col3.metric("⚡ Warm Leads", warm_count)
        col4.metric("❄️ Cold Leads", cold_count)

        st.divider()

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.markdown("#### 🎯 Leads by Temperature Grade")
            grade_summary = df_leads['grade_clean'].value_counts()
            st.bar_chart(grade_summary)

        with chart_col2:
            st.markdown("#### 📚 Demand by Course")
            course_summary = df_leads['course'].value_counts()
            st.bar_chart(course_summary)

        st.divider()

        st.markdown("#### 📋 Lead Records Explorer & Editor")
        search_query = st.text_input("🔍 Filter by Name, Course, or Phone:")
        
        display_df = df_leads.drop(columns=["grade_clean"])
        filtered_df = display_df
        if search_query:
            filtered_df = display_df[
                display_df['name'].str.contains(search_query, case=False, na=False) |
                display_df['course'].str.contains(search_query, case=False, na=False) |
                display_df['phone'].astype(str).str.contains(search_query, case=False, na=False)
            ]

        st.caption("💡 Double-click any cell to edit it, or select a row checkbox on the left and press Delete.")
        edited_df = st.data_editor(
            filtered_df,
            width="stretch",
            num_rows="dynamic"
        )

        if search_query:
            st.info("Clear the search filter above before saving edits to prevent overwriting hidden records.")
        else:
            if st.button("💾 Save Database Changes"):
                if update_leads_db(edited_df):
                    st.success("Database successfully updated!")
                    st.rerun()

        csv_data = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Filtered Leads to CSV",
            data=csv_data,
            file_name="crm_leads_export.csv",
            mime="text/csv"
        )
        
        st.divider()
        
        # --- AI EMAIL GENERATOR ---
        with st.expander("✉️ Generate AI Sales Email", expanded=False):
            st.markdown("Select a lead to automatically draft a personalized sales outreach email.")
            
            lead_names = df_leads['name'].tolist()
            selected_name = st.selectbox("Select a Lead to email:", lead_names)
            
            if st.button("🪄 Draft Email"):
                lead_row = df_leads[df_leads['name'] == selected_name].iloc[0]
                
                prompt = f"""
                Write a highly personalized, professional but friendly sales email to a prospect named {lead_row['name']}.
                They are interested in enrolling in our '{lead_row['course']}' course.
                Their current sales status is: '{lead_row['grade']}'.
                
                Instructions:
                - If their status is HOT, push strongly for an immediate enrollment phone call to secure their spot.
                - If WARM, offer them a detailed course syllabus and ask if they have questions.
                - If COLD, gently check in, mention a recent student success story, and offer a 10% discount.
                - Keep the email concise (under 150 words). 
                - Sign off as "The AI EDU-CRM Team".
                """
                
                with st.spinner("AI is drafting the email..."):
                    try:
                        response = ai_client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=prompt
                        )
                        st.text_area("Drafted Email (Ready to Copy):", value=response.text, height=250)
                    except (ServerError, APIError):
                        st.error("⚠️ Google AI is currently busy. Please wait a few seconds and click Draft again.")
                    except Exception as e:
                        st.error(f"Error generating email: {e}")

    else:
        st.warning("No data found in crm_enterprise.db.")