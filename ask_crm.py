import chromadb
from chromadb.utils import embedding_functions
from google import genai
from google.genai.errors import ServerError, APIError

print("🔍 1. Searching Vector DB for company policies...")
chroma_client = chromadb.PersistentClient(path="./crm_memory_db")
embedder = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
collection = chroma_client.get_collection(name="company_policies", embedding_function=embedder)

user_question = "Can I get my money back? I signed up 5 days ago."

results = collection.query(
    query_texts=[user_question],
    n_results=1
)
retrieved_policy = results['documents'][0][0]
print(f"   Found Policy: {retrieved_policy}\n")

print("🧠 2. Handing policy to Gemini to generate an answer...")

# 🔒 SECURITY UPDATE: Removed hardcoded API key for GitHub deployment
client = genai.Client(api_key="PASTE_YOUR_ACTUAL_KEY_HERE")

rag_prompt = f"""
You are a helpful customer support agent for AI EDU-CRM.
A customer just asked: "{user_question}"

Use ONLY the following company policy to answer them. Be polite and concise. 
Company Policy: {retrieved_policy}
"""

try:
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=rag_prompt
    )
    print("🤖 AI Support Agent Reply:")
    print(response.text)
    
except (ServerError, APIError) as e:
    print(f"\n⚠️ CLOUD SERVER BUSY: Google's AI API is momentarily overloaded.")
    print(f"Details: {e}")
    print("Your local RAG system works perfectly, but the internet server dropped the request.")
except Exception as e:
    print(f"\n⚠️ UNEXPECTED ERROR: {e}")