import os
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv

# Load keys from .env file
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHROMA_API_KEY = os.getenv("CHROMA_API_KEY")
CHROMA_TENANT = os.getenv("CHROMA_TENANT")
CHROMA_DATABASE = os.getenv("CHROMA_DATABASE")

def chunk_text(text, chunk_size=1000, overlap=200):
    """
    Splits long document text into smaller overlapping blocks
    so the AI doesn't lose context between chunks.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start += chunk_size - overlap
    return [c for c in chunks if c]

def upload_company_data(file_path, doc_id, category="General"):
    """
    Reads a document, chunks it, and pushes it to Chroma Cloud.
    """
    if not os.path.exists(file_path):
        print(f"❌ Error: File not found at {file_path}")
        return

    # 1. Read document content
    with open(file_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # 2. Break down into chunks
    text_chunks = chunk_text(raw_text)
    print(f"📖 Processed '{file_path}': Split into {len(text_chunks)} chunks.")

    try:
        # 3. Connect using the official Chroma Cloud Client
        # It automatically reads CHROMA_API_KEY, CHROMA_TENANT, and CHROMA_DATABASE from your .env
        client = chromadb.CloudClient(
            tenant=CHROMA_TENANT,
            database=CHROMA_DATABASE,
            api_key=CHROMA_API_KEY
        )

        # 4. Set up the embedding model
        openai_ef = OpenAIEmbeddingFunction(
            api_key=OPENAI_API_KEY,
            model_name="text-embedding-3-small"
        )

        # 5. Get your target collection
        collection = client.get_or_create_collection(
            name="knowledge_base", 
            embedding_function=openai_ef
        )

        # 6. Prepare payloads for bulk upload
        ids = [f"{doc_id}_chunk_{i}" for i in range(len(text_chunks))]
        metadatas = [{"source": file_path, "category": category} for _ in text_chunks]

        # 7. Push to Cloud Database
        collection.add(
            documents=text_chunks,
            ids=ids,
            metadatas=metadatas
        )
        print(f"🚀 Successfully uploaded all chunks for {doc_id} to Chroma Cloud collection 'knowledge_base'!")

    except Exception as e:
        print(f"❌ Upload failed: {str(e)}")

# =====================================================================
# Execution Loop
# =====================================================================
if __name__ == "__main__":
    # TARGETING YOUR ACTUAL SETUP_GUIDE.md FILE
    target_document = "SETUP_GUIDE.md"
        
    # Run upload pipeline for your setup guide documentation
    upload_company_data(
        file_path=target_document, 
        doc_id="setup_guide_docs", 
        category="Onboarding"
    )