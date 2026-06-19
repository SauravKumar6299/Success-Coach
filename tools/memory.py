import os
from mem0 import MemoryClient

# Set your API key (get one at https://app.mem0.ai)
client = MemoryClient(api_key=os.getenv("MEM0_API_KEY"))

# Add a memory
messages = [
    {"role": "user", "content": "I'm a vegetarian and allergic to nuts."},
    {"role": "assistant", "content": "Got it! I'll remember your dietary preferences."},
]
def add_memory(messages, user_id):
    client.add(messages, user_id=user_id)
    return {"status": "success", "message": "Memory added successfully."}

# Search memories
def search_memory(query, user_id):
    results = client.search(
        query,
        user_id=user_id,
    )
    return {"status": "success", "results": results}