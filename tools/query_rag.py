import os
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

# Pull credentials directly from environment variables for security
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHROMA_API_KEY = os.getenv("CHROMA_API_KEY")
CHROMA_TENANT = os.getenv("CHROMA_TENANT")
CHROMA_DATABASE = os.getenv("CHROMA_DATABASE")

def query_rag_system(user_query: str, num_results: int = 3) -> str:
    """
    Connects to the cloud-hosted Chroma instance using the official CloudClient,
    generates query embeddings via OpenAI, and returns matching text blocks.
    """
    try:
        # 1. Initialize using the official Chroma Cloud Client (Fixes Authentication)
        client = chromadb.CloudClient(
            tenant=CHROMA_TENANT,
            database=CHROMA_DATABASE,
            api_key=CHROMA_API_KEY
        )

        # 2. Instantiate OpenAI Embedding engine
        openai_ef = OpenAIEmbeddingFunction(
            api_key=OPENAI_API_KEY,
            model_name="text-embedding-3-small"
        )

        # 3. Pull the specific collection (Fixed name to match your upload)
        collection = client.get_collection(
            name="knowledge_base", 
            embedding_function=openai_ef
        )

        # 4. Execute semantic search
        results = collection.query(
            query_texts=[user_query],
            n_results=num_results
        )

        matched_documents = results.get("documents", [[]])[0]
        
        if not matched_documents:
            return "No matching corporate policies or course guidelines found in the documentation."

        return "\n\n---\n\n".join(matched_documents)

    except Exception as e:
        return f"Error executing secure document semantic search: {str(e)}"