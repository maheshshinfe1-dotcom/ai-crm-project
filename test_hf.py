from huggingface_hub import InferenceClient

# 🔒 SECURITY UPDATE: Removed hardcoded API key
# The free tier is exhausted (402 Payment Required). 
# If you ever purchase credits, paste the new key here:
client = InferenceClient(api_key="PASTE_YOUR_HF_KEY_HERE")

messages = [
    {"role": "user", "content": "Explain what a CRM is in one short sentence."}
]

print("🔌 Connecting to Hugging Face servers...")
try:
    response = client.chat_completion(
        model="Qwen/Qwen2.5-72B-Instruct",
        messages=messages,
        max_tokens=150
    )
    print("🤖 Qwen 2.5 Reply:")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"⚠️ Hugging Face API Error: {e}")