import chromadb
from chromadb.utils import embedding_functions

# 1. Start the Local Vector Database (It will create a folder on your hard drive)
chroma_client = chromadb.PersistentClient(path="./crm_memory_db")

# 2. Download a free, local "meat grinder" (Embedding Model) from Hugging Face
# This model runs 100% on your computer. No API keys needed!
embedder = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

# 3. Create a new collection (like an SQL Table) inside Chroma
collection = chroma_client.get_or_create_collection(
    name="company_policies", 
    embedding_function=embedder
)

# 4. Read your policy.txt file
print("📄 Reading policy.txt...")
with open("policy.txt", "r") as file:
    text_content = file.read()

# 5. Split the document into chunks (Paragraphs)
chunks = text_content.split('\n')
chunks = [chunk.strip() for chunk in chunks if chunk.strip()] # Remove empty lines

# 6. Inject the chunks into the Vector Database
print("🧠 Grinding text into Vectors and saving to ChromaDB...")
for i, chunk in enumerate(chunks):
    collection.add(
        documents=[chunk],
        metadatas=[{"source": "policy.txt", "line": i}],
        ids=[f"policy_chunk_{i}"]
    )

print("✅ Success! Your company policies are now memorized in the vector database.")