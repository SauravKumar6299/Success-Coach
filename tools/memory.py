import os
from mem0 import MemoryClient

client = MemoryClient(api_key=os.getenv("MEM0_API_KEY"))

# Add memory
def add_memory(messages, user_id):
    client.add(messages, user_id=user_id)
    return {"status": "success", "message": "Memory added successfully."}

# Search memories
def search_memory(query, user_id):
    try:
        results = client.search(
            query,
            filters={'user_id': user_id}, 
            limit=20
        )
        return {"status": "success", "results": results}
    except Exception as e:
        return {"status": "error", "msg": str(e)}

# Get memory to begin with
def get_memory(user_id):
    return search_memory("What are the student's core learning styles, preferences, and background?", user_id)