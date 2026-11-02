import chromadb
from chromadb.utils import embedding_functions

# 1. Connect to your local Vector Database
chroma_client = chromadb.PersistentClient(path="./crm_memory_db")

# 2. Load the EXACT SAME "meat grinder" model so the math matches
embedder = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

# 3. Open our specific collection (the policy folder)
collection = chroma_client.get_collection(
    name="company_policies", 
    embedding_function=embedder
)

# 4. Ask a natural language question!
user_question = "How many days do I have to ask for my money back?"

print(f"👤 Question: {user_question}")
print("🔍 Searching the Vector Database for the closest math match...\n")

# 5. Search the database (Ask it for the top 1 most relevant chunk)
results = collection.query(
    query_texts=[user_question],
    n_results=1
)

# 6. Display the retrieved knowledge
print("🤖 The Database Found This Relevant Policy:")
print(f"👉 {results['documents'][0][0]}")