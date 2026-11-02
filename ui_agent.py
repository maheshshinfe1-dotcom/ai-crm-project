import streamlit as st
import chromadb
from chromadb.utils import embedding_functions
import sqlite3
from google import genai
from google.genai.errors import ServerError, APIError

# 1. Setup the Webpage
st.set_page_config(page_title="AI CRM Agent", page_icon="🤖")
st.title("🤖 AI EDU-CRM Co-Pilot")
st.markdown("Ask me about company policies or check our hottest leads!")

# 2. Setup Local Databases & Cloud AI
@st.cache_resource
def load_engines():
    chroma_client = chromadb.PersistentClient(path="./crm_memory_db")
    embedder = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    collection = chroma_client.get_collection(name="company_policies", embedding_function=embedder)
    
    # Use Streamlit Secrets (NO HARDCODED KEY!)
    ai_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    
    return collection, ai_client

collection, ai_client = load_engines()

# 3. Setup SQLite Helper
def get_hot_leads():
    try:
        conn = sqlite3.connect('crm_enterprise.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name, course FROM leads WHERE grade LIKE '%HOT%' LIMIT 5")
        results = cursor.fetchall()
        conn.close()
        
        if results:
            return "\n".join([f"- {r[0]} (Interested in: {r[1]})" for r in results])
        return "No HOT leads found in the database at this time."
    except Exception as e:
        return f"Database error: {e}"

# 4. Chat Memory
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 5. The Full AI-Powered RAG Pipeline
if user_input := st.chat_input("Ask a question..."):
    
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    with st.chat_message("assistant"):
        user_text = user_input.lower().strip()
        
        # --- PHASE 1: RETRIEVAL ---
        if user_text in ["hi", "hello", "hey", "how are you", "how are you?"]:
            hidden_context = "The user is just saying hello. Greet them as a friendly CRM AI Assistant."
            
        elif "lead" in user_text or "customer" in user_text:
            raw_data = get_hot_leads()
            hidden_context = f"The user asked about leads. Here is the raw SQL data:\n{raw_data}\n\nTurn this into a polite, professional summary."
            
        else:
            results = collection.query(query_texts=[user_input], n_results=1)
            raw_data = results['documents'][0][0]
            hidden_context = f"The user asked a policy question. Here is the exact policy from ChromaDB:\n{raw_data}\n\nAnswer their question politely using ONLY this policy."
        
        # --- PHASE 2: GENERATION ---
        try:
            master_prompt = f"User Question: '{user_input}'\n\nInstructions: {hidden_context}"
            
            response = ai_client.models.generate_content(
                model="gemini-3.8-flash",
                contents=master_prompt
            )
            final_answer = response.text
            
        except (ServerError, APIError) as e:
            final_answer = f"⚠️ *Google AI is currently busy. Displaying raw database results:* ⚠️\n\n{hidden_context}"
            
        st.markdown(final_answer)
        st.session_state.messages.append({"role": "assistant", "content": final_answer})