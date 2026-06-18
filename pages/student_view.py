import streamlit as st
import datetime
import os
import json
from dotenv import load_dotenv
from openai import OpenAI

# Import all your updated tools
from tools.get_attendance import get_attendance
from tools.get_exam_score import get_exam_score
from tools.get_exam_schedule import get_exam_schedule
from tools.query_rag import query_rag_system

# Load environment variables from .env file
load_dotenv()

# Guard clause: Redirect back to login if name/roll missing
if "student_roll" not in st.session_state or "student_name" not in st.session_state:
    st.warning("Please sign in first.")
    st.switch_page("main.py")

# Initialize OpenAI Client
try:
    client = OpenAI()  # Automatically picks up OPENAI_API_KEY from .env
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
        "roll_no": roll_no,
        "id": thread_id,
        "title": title,
        "date": datetime.date.today().strftime("%b %d, %Y"),
        "messages": messages
    })
    
    with open(HISTORY_FILE, "w") as f:
        json.dump(all_records, f, indent=4)

# 1. Page Configuration
st.set_page_config(
    page_title="Student AI Workspace", 
    page_icon="🎓", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# 2. Modern UI Styling
st.html(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', sans-serif;
        background-color: #F8FAFC !important;
    }
    
    .chat-bubble {
        padding: 1rem 1.25rem;
        border-radius: 16px;
        margin-bottom: 1rem;
        max-width: 85%;
        line-height: 1.5;
    }
    .user-bubble {
        background-color: #E2E8F0;
        color: #1E293B;
        margin-left: auto;
        border-bottom-right-radius: 4px;
    }
    .ai-bubble {
        background-color: #FFFFFF;
        color: #0F172A;
        margin-right: auto;
        border-bottom-left-radius: 4px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        border: 1px solid #E2E8F0;
    }
    
    .history-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .history-card:hover {
        background: #F1F5F9;
        border-color: #CBD5E1;
    }
    .history-title {
        font-size: 0.9rem;
        font-weight: 500;
        color: #334155;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .history-date {
        font-size: 0.75rem;
        color: #94A3B8;
        margin-top: 0.25rem;
    }
    </style>
    """
)

student_roll = st.session_state["student_roll"]
student_name = st.session_state["student_name"]
student_program = st.session_state.get("student_program", "N/A")
student_cohort = st.session_state.get("student_cohort", "N/A")

saved_threads = load_student_history(student_roll)

if "active_thread_id" not in st.session_state:
    st.session_state.active_thread_id = str(int(datetime.datetime.now().timestamp()))

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": f"Hello {student_name}! I am your AI Study Companion for {student_program} ({student_cohort}). How can I assist you today?"}
    ]

chat_col, history_col = st.columns([8, 3], gap="large")

# =====================================================================
# LEFT SIDE: CHAT INTERFACE
# =====================================================================
with chat_col:
    if st.button("⬅ Switch Portal / Log out", type="secondary"):
        st.session_state.show_student_login = False
        st.switch_page("main.py")
        
    st.markdown(f"<h2 style='margin-bottom:0px;'>🎓 Welcome, {student_name}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#64748B; margin-bottom:2rem;'>ID: {student_roll} | Program: {student_program} | Cohort: {student_cohort}</p>", unsafe_allow_html=True)
    
    chat_container = st.container(height=500, border=False)
    
    with chat_container:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(f'<div class="chat-bubble user-bubble">{msg["content"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="chat-bubble ai-bubble">{msg["content"]}</div>', unsafe_allow_html=True)

    if prompt := st.chat_input("Ask a question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        current_title = st.session_state.get("current_chat_title", prompt[:35] + "...")
        st.session_state.current_chat_title = current_title
        save_chat_session(student_roll, st.session_state.active_thread_id, current_title, st.session_state.messages)
        st.rerun()

# =====================================================================
# OPENAI CHAT COMPLETION WITH FUNCTION CALLING (TOOLS)
# =====================================================================
if st.session_state.messages[-1]["role"] == "user":
    with chat_container:
        with st.spinner("Thinking..."):
            try:
                # 1. Define JSON schemas for OpenAI tools
                tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": "get_attendance",
                            "description": "Retrieves all logged weekly attendance logs, scheduled classes, and attendance percentages for the current student.",
                            "parameters": {"type": "object", "properties": {}}
                        }
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "get_exam_score",
                            "description": "Retrieves the student's exam or test marks across subjects.",
                            "parameters": {"type": "object", "properties": {}}
                        }
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "get_exam_schedule",
                            "description": "Retrieves all upcoming exam timetables, dates, and schedule details for the current student.",
                            "parameters": {"type": "object", "properties": {}}
                        }
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "query_company_documents",
                            "description": "Searches company internal documents, course descriptions, policies, and program specifications.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "search_query": {
                                        "type": "string",
                                        "description": "The specific query text used to find descriptive information from corporate manuals."
                                    }
                                },
                                "required": ["search_query"]
                            }
                        }
                    }
                ]

               # Format logs into basic OpenAI API message objects
                formatted_contents = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
                
                # --- NEW CODE: INJECT YOUR SYSTEM PROMPT HERE ---
                system_guidelines = f"""
                You are a highly intelligent and polite AI Study Companion for {student_name}.
                Your goal is to help them succeed in their {student_program} program.
                
                Guidelines:
                1. Always be encouraging but strict about academic integrity.
                2. Do not write complete assignments for the student.
                3. Use the provided tools to check their schedule, attendance, and grades when asked.
                4. Keep your answers concise, well-formatted, and easy to read.
                5. Dont provide any personal opinions or advice outside of academic context.
                6. Dont entertain any requests for unethical or illegal activities, and politely decline if asked.
                7. Dont provide any personal information or data about other students or staff.
                8. Dont entertain any doubts other than program-related questions. If the question is unrelated, politely redirect them to ask about their studies.
                """
                
                # Insert the system prompt at index 0 (the very beginning)
                formatted_contents.insert(0, {"role": "system", "content": system_guidelines})

                # First Call out to OpenAI to analyze intent
                response = client.chat.completions.create(
                    model="gpt-5.4-mini-2026-03-17", 
                    messages=formatted_contents,
                    tools=tools,
                    tool_choice="auto"
                )
                
                response_message = response.choices[0].message
                tool_calls = response_message.tool_calls
                
                # 2. Process tool requests if made by OpenAI
                if tool_calls:
                    # Append the assistant response message that requested tool execution
                    formatted_contents.append(response_message)
                    
                    for tool_call in tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)
                        tool_output_string = ""
                        
                        # Route dynamically to your tool functions
                        if function_name == "get_attendance":
                            success, result = get_attendance(roll_no=student_roll)
                            tool_output_string = json.dumps(result) if success else str(result)
                            
                        elif function_name == "get_exam_score":
                            success, result = get_exam_score(roll_no=student_roll)
                            tool_output_string = json.dumps(result) if success else str(result)
                            
                        elif function_name == "get_exam_schedule":
                            success, result = get_exam_schedule(roll_no=student_roll)
                            tool_output_string = json.dumps(result) if success else str(result)
                            
                        elif function_name == "query_company_documents":
                            query_text = function_args.get("search_query", prompt)
                            tool_output_string = query_rag_system(user_query=query_text)

                        # Append each separate tool call response structural packet 
                        formatted_contents.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": tool_output_string
                        })
                    
                    # Second Call: Processes context with tool results injected
                    second_response = client.chat.completions.create(
                        model="gpt-5.4-mini-2026-03-17",
                        messages=formatted_contents
                    )
                    ai_response = second_response.choices[0].message.content
                else:
                    ai_response = response_message.content
                
                # 3. Update Streamlit message state and save
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
                save_chat_session(student_roll, st.session_state.active_thread_id, st.session_state.get("current_chat_title", "Active Conversation"), st.session_state.messages)
                st.rerun()
                
            except Exception as e:
                st.error(f"OpenAI Workspace Error: {str(e)}")

# =====================================================================
# RIGHT SIDE: CHAT HISTORY SIDE-PANEL
# =====================================================================
with history_col:
    st.markdown("<h4 style='margin-top:10px; margin-bottom: 1.5rem; color:#475569;'>🕒 Your Saved History</h4>", unsafe_allow_html=True)
    
    if st.button("➕ Start New Chat", use_container_width=True, type="primary"):
        st.session_state.active_thread_id = str(int(datetime.datetime.now().timestamp()))
        st.session_state.current_chat_title = "Active Conversation"
        st.session_state.messages = [
            {"role": "assistant", "content": f"Starting a fresh session. How can I assist you now, {student_name}?"}
        ]
        st.rerun()
        
    st.write("---")
    
    if not saved_threads:
        st.caption("No logs found for your Roll Number yet.")
        
    for item in saved_threads:
        with st.container():
            st.markdown(
                f"""
                <div class="history-card">
                    <div class="history-title">💬 {item['title']}</div>
                    <div class="history-date">{item['date']}</div>
                </div>
                """, 
                unsafe_allow_html=True
            )
            if st.button("Open Thread", key=f"hist_{item['id']}", use_container_width=True):
                st.session_state.active_thread_id = item['id']
                st.session_state.current_chat_title = item['title']
                st.session_state.messages = item['messages']
                st.rerun()