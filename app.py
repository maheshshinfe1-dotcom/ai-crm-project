import streamlit as st
import chromadb
from chromadb.utils import embedding_functions
import hashlib
import uuid
from google import genai
from google.genai import types
from google.genai.errors import ServerError, APIError

# Import our custom database module (Phase 16 Architecture)
from db_ops import (
    init_all_dbs, load_chat_history, save_chat_message, clear_chat_history,
    get_leads_df, update_leads_db, add_new_lead, run_automation_sweep,
    search_leads_tool, update_lead_grade_tool, create_lead_record_tool
)

st.set_page_config(page_title="AI EDU-CRM Enterprise", page_icon="🎓", layout="wide")

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

@st.cache_resource
def load_engines():
    chroma_client = chromadb.PersistentClient(path="./crm_memory_db")
    embedder = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    collection = chroma_client.get_collection(name="company_policies", embedding_function=embedder)
    ai_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    return collection, ai_client

collection, ai_client = load_engines()
init_all_dbs()

@st.cache_data(ttl=3600)
def get_flash_models() -> list[str]:
    candidates = ["gemini-3.8-flash"]
    try:
        for m in ai_client.models.list():
            name = m.name.replace("models/", "")
            if "flash" in name and "image" not in name and "audio" not in name and name not in candidates:
                candidates.append(name)
    except Exception: pass
    return candidates[:3]

def add_document_to_db(file_name, file_content):
    try:
        doc_id = str(uuid.uuid4())
        collection.add(documents=[file_content], metadatas=[{"source": file_name}], ids=[doc_id])
        return True
    except Exception as e:
        st.error(f"Vector DB Error: {e}")
        return False

def search_company_policies(question: str) -> str:
    """Search company policies, refund rules, discounts, and extension terms in the ChromaDB vector store."""
    results = collection.query(query_texts=[question], n_results=2)
    docs = results["documents"][0]
    return "\n---\n".join(docs) if docs else "No relevant policy found."

def run_autonomous_agent(user_prompt: str) -> tuple[str, list[str]]:
    config = types.GenerateContentConfig(
        system_instruction=(
            "You are the EDU-CRM Autonomous Agent. You have tools to search leads, "
            "update lead grades, create new leads in SQLite, and search company policies in ChromaDB. "
            "Always use tools to verify facts—never guess."
        ),
        tools=[search_leads_tool, update_lead_grade_tool, create_lead_record_tool, search_company_policies],
        temperature=0.2,
    )
    for model_name in get_flash_models():
        try:
            chat = ai_client.chats.create(model=model_name, config=config)
            response = chat.send_message(user_prompt)
            tool_trace = []
            for step in chat.get_history():
                for part in (step.parts or []):
                    if part.function_call:
                        tool_trace.append(f"🔧 **Called:** `{part.function_call.name}({dict(part.function_call.args)})`")
                    elif part.function_response:
                        tool_trace.append(f"📦 **Returned:** `{part.function_response.response}`")
            return response.text, tool_trace
        except (ServerError, APIError): continue
        except Exception as e: return f"⚠️ *Agent execution error:* {e}", []
    return "⚠️ *All AI endpoints are temporarily busy.*", []

def transcribe_audio(audio_bytes):
    for model_name in get_flash_models():
        try:
            response = ai_client.models.generate_content(
                model=model_name,
                contents=[
                    "Transcribe this spoken audio accurately into plain text. Return ONLY the transcribed words.",
                    types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")
                ]
            )
            return response.text.strip()
        except (ServerError, APIError): continue
        except Exception as e: return None
    return None

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
    st.markdown("### ⚙️ CRM Automation")
    if st.button("⚡ Run Automation Sweep"):
        with st.spinner("Scanning database..."):
            queued = run_automation_sweep()
            if queued: st.success(f"Follow-ups queued for: {', '.join(queued)}")
            else: st.info("No new actions needed. (Idempotency check passed).")
        
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
tab_chat, tab_analytics = st.tabs(["💬 AI Autonomous Agent", "📊 Lead Analytics & BI"])

with tab_chat:
    st.subheader("Autonomous CRM & Policy Agent")
    st.caption("Ask multi-step questions, update lead grades, create prospects, or query company policies by text or voice.")
    
    if "messages" not in st.session_state:
        st.session_state.messages = load_chat_history(current_user)

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    audio_value = st.audio_input("🎙️ Speak your command")
    typed_input = st.chat_input("Ask or command the agent...")

    prompt_to_process, display_user_msg = None, None

    if audio_value is not None:
        audio_hash = hashlib.md5(audio_value.getvalue()).hexdigest()
        if audio_hash != st.session_state.get("last_audio_hash"):
            st.session_state.last_audio_hash = audio_hash
            with st.spinner("Transcribing voice query..."):
                transcribed = transcribe_audio(audio_value.getvalue())
            if transcribed:
                prompt_to_process = transcribed
                display_user_msg = f"🎙️ {transcribed}"

    if typed_input:
        prompt_to_process = typed_input
        display_user_msg = typed_input

    if prompt_to_process:
        with st.chat_message("user"): st.markdown(display_user_msg)
        st.session_state.messages.append({"role": "user", "content": display_user_msg})
        save_chat_message(current_user, "user", display_user_msg)

        with st.chat_message("assistant"):
            with st.spinner("Agent reasoning & executing tools..."):
                final_answer, tool_trace = run_autonomous_agent(prompt_to_process)

            if tool_trace:
                with st.expander("🧠 View Autonomous Tool Trace", expanded=False):
                    for line in tool_trace: st.markdown(line)

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
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Prospects", len(df_leads))
        col2.metric("🔥 Hot Leads", len(df_leads[df_leads['grade_clean'].str.contains("HOT", na=False)]))
        col3.metric("⚡ Warm Leads", len(df_leads[df_leads['grade_clean'].str.contains("WARM", na=False)]))
        col4.metric("❄️ Cold Leads", len(df_leads[df_leads['grade_clean'].str.contains("COLD", na=False)]))
        st.divider()

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown("#### 🎯 Leads by Temperature Grade")
            st.bar_chart(df_leads['grade_clean'].value_counts())
        with chart_col2:
            st.markdown("#### 📚 Demand by Course")
            st.bar_chart(df_leads['course'].value_counts())
        st.divider()

        st.markdown("#### 📋 Lead Records Explorer & Editor")
        search_query = st.text_input("🔍 Filter by Name, Course, or Phone:")
        display_df = df_leads.drop(columns=["grade_clean"])
        filtered_df = display_df[
            display_df['name'].str.contains(search_query, case=False, na=False) |
            display_df['course'].str.contains(search_query, case=False, na=False) |
            display_df['phone'].astype(str).str.contains(search_query, case=False, na=False)
        ] if search_query else display_df

        edited_df = st.data_editor(filtered_df, width="stretch", num_rows="dynamic")

        if search_query:
            st.info("Clear the search filter above before saving edits to prevent overwriting hidden records.")
        else:
            if st.button("💾 Save Database Changes"):
                if update_leads_db(edited_df):
                    st.success("Database successfully updated!")
                    st.rerun()

        st.download_button(
            label="📥 Export Filtered Leads to CSV",
            data=filtered_df.to_csv(index=False).encode('utf-8'),
            file_name="crm_leads_export.csv",
            mime="text/csv"
        )
        st.divider()
        
        with st.expander("✉️ Generate AI Sales Email", expanded=False):
            st.markdown("Select a lead to automatically draft a personalized sales outreach email.")
            selected_name = st.selectbox("Select a Lead to email:", df_leads['name'].tolist())
            if st.button("🪄 Draft Email"):
                lead_row = df_leads[df_leads['name'] == selected_name].iloc[0]
                prompt = f"Write a personalized, professional but friendly sales email (under 150 words) to {lead_row['name']} regarding the '{lead_row['course']}' course. Current status: '{lead_row['grade']}'. If HOT, push for a phone call. If WARM, offer syllabus. If COLD, offer 10% discount. Sign off as 'The AI EDU-CRM Team'."
                with st.spinner("AI is drafting the email..."):
                    draft_text = None
                    for model_name in get_flash_models():
                        try:
                            response = ai_client.models.generate_content(model=model_name, contents=prompt)
                            draft_text = response.text
                            break
                        except (ServerError, APIError): continue
                    if draft_text: st.text_area("Drafted Email (Ready to Copy):", value=draft_text, height=250)
                    else: st.error("⚠️ AI endpoints are busy. Please retry.")
    else:
        st.warning("No data found in crm_enterprise.db.")