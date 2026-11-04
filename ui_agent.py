import streamlit as st
import chromadb
from chromadb.utils import embedding_functions
import sqlite3
import pandas as pd
from google import genai
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
                st.rerun() # Refresh the page to show the CRM
            else:
                st.error("❌ Invalid username or password.")
    
    # Stop the script here so unauthorized users see nothing else
    st.stop()

# --- LOGOUT SIDEBAR ---
with st.sidebar:
    st.markdown(f"👤 **Logged in as:** `{st.secrets['ADMIN_USER']}`")
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

# ==========================================
# CORE CRM APPLICATION (Only runs if logged in)
# ==========================================

# 2. Cached Database & AI Engine Initialization
@st.cache_resource
def load_engines():
    chroma_client = chromadb.PersistentClient(path="./crm_memory_db")
    embedder = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    collection = chroma_client.get_collection(name="company_policies", embedding_function=embedder)
    ai_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    return collection, ai_client

collection, ai_client = load_engines()

# 3. Database Helpers
def get_leads_df():
    try:
        conn = sqlite3.connect("crm_enterprise.db")
        df = pd.read_sql_query("SELECT * FROM leads", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Error reading SQLite database: {e}")
        return pd.DataFrame()

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

# 4. App Navigation Tabs
tab_chat, tab_analytics = st.tabs(["💬 AI Co-Pilot", "📊 Lead Analytics & BI"])

with tab_chat:
    st.subheader("AI Support & CRM Intelligence")
    st.caption("Ask questions about company refund/enrollment policies or request lead summaries.")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if user_input := st.chat_input("Ask a question..."):
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        with st.chat_message("assistant"):
            user_text = user_input.lower().strip()

            if user_text in ["hi", "hello", "hey", "how are you", "how are you?"]:
                hidden_context = "The user is saying hello. Greet them politely as the EDU-CRM AI Co-Pilot."
            elif "lead" in user_text or "customer" in user_text or "prospect" in user_text:
                raw_data = get_hot_leads()
                hidden_context = f"The user asked about leads. Here is the raw SQL data:\n{raw_data}\n\nSummarize this professionally."
            else:
                results = collection.query(query_texts=[user_input], n_results=1)
                raw_data = results['documents'][0][0]
                hidden_context = f"The user asked a policy question. Here is the exact policy text:\n{raw_data}\n\nAnswer using ONLY this policy."

            try:
                master_prompt = f"User Question: '{user_input}'\n\nInstructions: {hidden_context}"
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

        st.markdown("#### 📋 Lead Records Explorer")
        search_query = st.text_input("🔍 Filter by Name, Course, or Phone:")
        
        filtered_df = df_leads
        if search_query:
            filtered_df = df_leads[
                df_leads['name'].str.contains(search_query, case=False, na=False) |
                df_leads['course'].str.contains(search_query, case=False, na=False) |
                df_leads['phone'].astype(str).str.contains(search_query, case=False, na=False)
            ]

        st.dataframe(filtered_df, width="stretch")

        csv_data = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Filtered Leads to CSV",
            data=csv_data,
            file_name="crm_leads_export.csv",
            mime="text/csv"
        )
    else:
        st.warning("No data found in crm_enterprise.db.")