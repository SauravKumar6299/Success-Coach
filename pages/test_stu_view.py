import os
import threading
import datetime
import json

os.environ["TOKENIZERS_PARALLELISM"] = "false"

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

# --- LangChain Imports for Multi-Agent Orchestration ---
from langchain_openai import ChatOpenAI
from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_community.callbacks.streamlit import StreamlitCallbackHandler
from langchain_core.messages import HumanMessage, AIMessage

# Pull credentials directly from environment variables for security
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHROMA_API_KEY = os.getenv("CHROMA_API_KEY")
CHROMA_TENANT = os.getenv("CHROMA_TENANT")
CHROMA_DATABASE = os.getenv("CHROMA_DATABASE")

# Tool & Agent Imports
from tools.query_rag import query_rag_system
from tools.memory import add_memory, get_memory
from tools.add_to_signal import add_to_signal
from tools.add_to_calender import add_to_calendar
from agents.get_student_info import student_info_agent_executor 
from agents.emotion_triage_agent import emotion_triage_agent_executor


# =====================================================================
# INITIALIZATION & MEMORY HELPERS
# =====================================================================
if "student_roll" not in st.session_state or "student_name" not in st.session_state:
    st.warning("Please sign in first.")
    st.switch_page("main.py")

try:
    client = OpenAI()
except Exception as e:
    st.error("OpenAI Client failed to initialize. Please check your .env file setup.")

HISTORY_FILE = "history.txt"

def load_student_history(roll_no):
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r") as f:
            all_records = json.load(f)
            return [record for record in all_records if record.get("roll_no") == roll_no]
    except Exception:
        return []

def save_chat_session(roll_no, thread_id, title, messages):
    all_records = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                all_records = json.load(f)
        except Exception:
            all_records = []
            
    all_records = [r for r in all_records if not (r.get("roll_no") == roll_no and r.get("id") == thread_id)]
    
    all_records.append({
        "roll_no": roll_no, "id": thread_id, "title": title,
        "date": datetime.date.today().strftime("%b %d, %Y"), "messages": messages
    })
    
    with open(HISTORY_FILE, "w") as f:
        json.dump(all_records, f, indent=4)

def summarize_and_store_memory(messages, user_id):
    if len(messages) <= 2: 
        return
    summary_system_prompt = """
    Extract and summarize important information, personal preferences, or learning patterns from this conversation.
    If purely transactional, output exactly: 'NO_SIGNIFICANT_MEMORY'.
    """
    chat_text = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in messages if m['role'] != 'system'])
    try:
        response = client.chat.completions.create(
            model="gpt-5.4-mini-2026-03-17",
            messages=[{"role": "system", "content": summary_system_prompt}, {"role": "user", "content": chat_text}]
        )
        summary = response.choices[0].message.content.strip()
        if summary != "NO_SIGNIFICANT_MEMORY":
            memory_payload = [{"role": "user", "content": f"Update my profile with these facts: {summary}"}]
            add_memory(messages=memory_payload, user_id=user_id)
    except Exception as e:
        print(f"Failed to summarize and store memory: {e}")

# =====================================================================
# DEFINE ORCHESTRATOR TOOLS
# =====================================================================
@tool
def student_data_assistant_tool(query: str, roll_no: str) -> str:
    """
    Useful when you need answers about student academic details including 
    attendance records, upcoming exam schedules, or historical exam scores. 
    Pass a detailed structural query containing the roll number.
    """
    response = student_info_agent_executor.invoke(
        {"input": query, "chat_history": [], "roll_no": roll_no},
        config={"callbacks": []} 
    )
    return response["output"]

@tool
def trigger_emotion_triage(roll_no: str, conversation_context: str) -> str:
    """
    Trigger this tool at the END of a chat session, OR if the student expresses academic/non-academic distress.
    It runs an emotional analysis and escalates to a human coach if needed. And conversation context = Chat Summary
    """
    response = emotion_triage_agent_executor.invoke(
        {
            "input": f"Analyze this context for student ID {roll_no}: {conversation_context}", 
            "chat_history": []
        },
        config={"callbacks": []} 
    )
    return response["output"]

@tool
def query_rag_system(user_query: str) -> str:
    """
    Query the secure RAG system for corporate policies, syllabus details, or course guidelines.
    """
    try:
        chroma_client = chromadb.CloudClient(tenant=CHROMA_TENANT, database=CHROMA_DATABASE, api_key=CHROMA_API_KEY)
        openai_ef = OpenAIEmbeddingFunction(api_key=OPENAI_API_KEY, model_name="text-embedding-3-small")
        collection = chroma_client.get_collection(name="knowledge_base", embedding_function=openai_ef)
        results = collection.query(query_texts=[user_query], n_results=3)
        matched_documents = results.get("documents", [[]])[0]
        
        if not matched_documents:
            return "No matching corporate policies or course guidelines found in the documentation."
        return "\n\n---\n\n".join(matched_documents)
    except Exception as e:
        return f"Error executing secure document semantic search: {str(e)}"

orchestrator_tools = [student_data_assistant_tool, query_rag_system, trigger_emotion_triage]

# =====================================================================
# UI CONFIGURATION & SESSION STATE
# =====================================================================
st.set_page_config(page_title="Student AI Workspace", page_icon="🎓", layout="wide", initial_sidebar_state="expanded")

# Cleaned up CSS: relying mostly on Streamlit native components for responsiveness
st.html("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    html, body, [data-testid="stAppViewContainer"] { 
        font-family: 'Inter', sans-serif; 
    }
    .stSidebar {
        background-color: #F8FAFC !important;
    }
    .profile-card {
        background: #FFFFFF; 
        border: 1px solid #E2E8F0; 
        border-radius: 12px; 
        padding: 1rem; 
        margin-bottom: 1.5rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    </style>
""")

student_roll = st.session_state["student_roll"]
student_name = st.session_state["student_name"]
student_program = st.session_state.get("student_program", "N/A")
student_cohort = st.session_state.get("student_cohort", "N/A")

# If the logged-in user changes, wipe the old chat history from the session state
if st.session_state.get("_current_session_user") != student_roll:
    for key in ["messages", "active_thread_id", "current_chat_title", "student_memories"]:
        st.session_state.pop(key, None)
    st.session_state["_current_session_user"] = student_roll
# --------------------------------------------------

if "active_thread_id" not in st.session_state:
    st.session_state.active_thread_id = str(int(datetime.datetime.now().timestamp()))
    st.session_state.current_chat_title = "Active Conversation"

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": f"Hello {student_name}! I am your AI Study Companion for {student_program} ({student_cohort}). How can I assist you today?"}
    ]

# Fetch Session Memories Once
if "student_memories" not in st.session_state:
    try:
        mem_response = get_memory(user_id=student_roll)
        facts = [item.get("memory", "").strip() for item in mem_response.get("results", {}).get("results", []) if isinstance(item, dict) and item.get("memory", "").strip()]
        st.session_state.student_memories = "\n".join(f"- {fact}" for fact in facts) if facts else "No specific preferences logged yet."
    except Exception as e:
        st.session_state.student_memories = "No specific preferences logged yet."

# =====================================================================
# SIDEBAR: NAVIGATION, PROFILE & CHAT HISTORY
# =====================================================================
with st.sidebar:
    st.markdown(f"""
        <div class="profile-card">
            <h3 style='margin:0; font-size: 1.1rem; color: #1E293B;'>🎓 {student_name}</h3>
            <p style='margin: 0.25rem 0 0 0; font-size: 0.85rem; color:#64748B;'>ID: {student_roll}</p>
            <p style='margin: 0; font-size: 0.85rem; color:#64748B;'>Program: {student_program}</p>
        </div>
    """, unsafe_allow_html=True)

    # Session Control Buttons
    if st.button("➕ New Chat", use_container_width=True, type="primary"):
        with st.spinner("Saving memories..."):
            summarize_and_store_memory(st.session_state.messages, student_roll)
        st.session_state.active_thread_id = str(int(datetime.datetime.now().timestamp()))
        st.session_state.current_chat_title = "Active Conversation"
        st.session_state.messages = [{"role": "assistant", "content": f"Starting a fresh session. How can I assist you now, {student_name}?"}]
        st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🛑 End Chat", use_container_width=True):
            with st.spinner("Wrapping up..."):
                summarize_and_store_memory(st.session_state.messages, student_roll)
            st.session_state.messages.append({"role": "assistant", "content": "This chat session has been concluded. Click 'New Chat' to start again!"})
            save_chat_session(student_roll, st.session_state.active_thread_id, st.session_state.get("current_chat_title", "Concluded Conversation"), st.session_state.messages)
            st.rerun()
    with col2:
        if st.button("⬅ Log out", use_container_width=True):
            with st.spinner("Logging out..."):
                summarize_and_store_memory(st.session_state.messages, student_roll)
                save_chat_session(student_roll, st.session_state.active_thread_id, st.session_state.get("current_chat_title", "Active Conversation"), st.session_state.messages)
            for key in ["messages", "active_thread_id", "current_chat_title", "student_memories", "student_roll", "student_name", "student_program", "student_cohort"]:
                st.session_state.pop(key, None)
            st.session_state.show_student_login = False
            st.switch_page("main.py")

    st.divider()
    
    # History Section
    st.markdown("<h4 style='color:#475569;'>🕒 Chat History</h4>", unsafe_allow_html=True)
    saved_threads = load_student_history(student_roll)
    
    if not saved_threads:
        st.caption("No logs found for your Roll Number yet.")
    else:
        for item in reversed(saved_threads): # Show newest first
            if st.button(f"💬 {item['title']}\n\n{item['date']}", key=f"hist_{item['id']}", use_container_width=True):
                st.session_state.active_thread_id = item['id']
                st.session_state.current_chat_title = item['title']
                st.session_state.messages = item['messages']
                st.rerun()

# =====================================================================
# MAIN CHAT INTERFACE
# =====================================================================
st.header(st.session_state.get("current_chat_title", "Active Conversation"))

# Render existing messages natively
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input Field
if prompt := st.chat_input("Ask a question..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Dynamic title generation for first user message
    if st.session_state.current_chat_title == "Active Conversation":
        st.session_state.current_chat_title = prompt[:35] + ("..." if len(prompt) > 35 else "")
    
    save_chat_session(student_roll, st.session_state.active_thread_id, st.session_state.current_chat_title, st.session_state.messages)
    
    with st.chat_message("user"):
        st.markdown(prompt)

    # Agent Execution
    with st.chat_message("assistant"):
        thought_container = st.container()
        st_callback = StreamlitCallbackHandler(thought_container)
        
        try:
            langchain_history = []
            for m in st.session_state.messages[:-1]:
                if m["role"] == "user":
                    langchain_history.append(HumanMessage(content=m["content"]))
                elif m["role"] == "assistant":
                    langchain_history.append(AIMessage(content=m["content"]))

            system_guidelines = f"""
            You are a highly intelligent and polite AI Study Companion for {student_name}.
            Your goal is to help them succeed in their {student_program} program.
            
            CORE STUDENT PROFILE & PREFERENCES:
            {st.session_state.student_memories}
            roll_no: {student_roll}, program: {student_program}, cohort: {student_cohort}
            
            Guidelines:
            0. Assist and comfort them when they are having a hard time. Be empathetic.
            1. Always be encouraging but strict about academic integrity.
            2. Do not write complete assignments for the student.
            3. Use the provided tools to check their schedule, attendance, grades, and RAG documents when needed.
            4. Keep your answers concise, well-formatted, and easy to read.
            5. Don't provide personal opinions outside of academic context.
            6. Don't entertain requests for unethical activities.
            7. Only discuss data pertaining to the current student roll number.
            8. TRIAGE POLICY:
                You are the gatekeeper. Call `trigger_emotion_triage` only when a student genuinely
                needs human emotional or academic support. Otherwise, keep helping normally. When in
                doubt, do not escalate.

                Escalate when:
                - Safety (always, even if subtle or joked about): self-harm, suicidal thoughts, or
                giving up on life/studies. Just escalate — don't probe or assess.
                - Emotional distress: hopelessness, panic, burnout, feeling alone or unable to cope,
                or asking for help with mental health or a personal issue affecting them.
                - Real academic struggle: persistently falling behind, overwhelmed, or talking about
                quitting — NOT ordinary subject questions.

                Do not escalate for: normal academic questions, mild passing frustration, casual
                chat, or sign-offs ("bye", "goodbye"). A goodbye triggers only if it carries real
                distress, not the word itself.

                If unsure: lean toward escalating on emotional/safety signals, away from it on
                academic ones. Escalate with one tool call and keep your reply warm — don't mention
                the tool.
            9. Dig deeper if you sense the student is struggling but hasn't explicitly said so. Always prioritize their well-being.
            """
            
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", system_guidelines),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ])
            
            llm = ChatOpenAI(model="gpt-5.4-mini-2026-03-17", temperature=0.2)
            orchestrator_agent = create_openai_tools_agent(llm, orchestrator_tools, prompt_template)
            orchestrator_executor = AgentExecutor(agent=orchestrator_agent, tools=orchestrator_tools, verbose=True)
            
            response = orchestrator_executor.invoke(
                {"input": prompt, "chat_history": langchain_history},
                {"callbacks": [st_callback]}
            )
            
            ai_response = response["output"]
            st.markdown(ai_response)
            st.session_state.messages.append({"role": "assistant", "content": ai_response})
            save_chat_session(student_roll, st.session_state.active_thread_id, st.session_state.current_chat_title, st.session_state.messages)
            
        except Exception as e:
            st.error(f"Orchestrator Execution Error: {str(e)}")