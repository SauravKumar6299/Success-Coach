import os
import threading
import datetime
import json

# Prevent tokenizer parallelism warnings before loading transformers
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from transformers import pipeline

# Import all your updated tools
from tools.get_attendance import get_attendance
from tools.get_exam_score import get_exam_score
from tools.get_exam_schedule import get_exam_schedule
from tools.query_rag import query_rag_system
from tools.memory import add_memory
from tools.memory import get_memory
from tools.add_to_signal import add_to_signal

# Load environment variables from .env file
load_dotenv()

# =====================================================================
# GLOBAL AI EMOTION TRIAGE CONFIGURATION (NON-CELERY)
# =====================================================================
@st.cache_resource
def load_triage_model():
    """Loads the 28-emotion model once and keeps it cached in RAM."""
    return pipeline(
        "text-classification", 
        model="SamLowe/roberta-base-go_emotions", 
        top_k=None 
    )

try:
    emotion_classifier = load_triage_model()
except Exception as e:
    print(f"Failed to load emotion model: {e}")
    emotion_classifier = None

import json

def run_background_triage(student_id, student_message):
    """Analyzes text in a background thread and updates the coach queue."""
    if not emotion_classifier:
        return
    try:
        results = emotion_classifier(student_message)[0]
        
        # Define urgent emotions and filter results
        urgent_emotions = {'anger', 'fear', 'grief', 'nervousness', 'sadness', 'remorse', 'disappointment', 'embarrassment'}
        triggers = [e['label'] for e in results if e['score'] > 0.50 and e['label'] in urgent_emotions]
        
        if triggers:
            # Ask the LLM to decide IF intervention is needed, and extract data if it is.
            extraction_prompt = f"""
            Analyze the following student message and their detected emotions to triage for a human coach.
            Message: "{student_message}"
            Emotions Detected: {triggers}
            
            First, evaluate if this genuinely requires human coach intervention. Minor venting, typical study fatigue, or passing nervousness might not need escalation. However, severe distress, academic blockers, or explicit requests for help DO need a human coach.
            
            Return ONLY a JSON object with these exact keys:
            - "needs_intervention" (boolean: true or false)
            - "signal_type" (e.g., Academic Stress, Personal Crisis, Frustration - or "N/A" if false)
            - "severity" (Low, Medium, High, Critical - or "N/A" if false)
            - "urgency" (Immediate, Next 24 hours, Routine - or "N/A" if false)
            - "reason" (A concise 1-sentence explanation of why they need help - or "N/A" if false)
            - "timestamp" (The current timestamp)
            """
            
            response = client.chat.completions.create(
                model="gpt-5.4-mini-2026-03-17",
                messages=[{"role": "user", "content": extraction_prompt}],
                response_format={"type": "json_object"}
            )
            
            ai_extracted_data = json.loads(response.choices[0].message.content)
            
            # Check the LLM's decision before adding to the spreadsheet
            if ai_extracted_data.get("needs_intervention", False):
                
                # Append standard tracking data
                ai_extracted_data["student_id"] = student_id
                ai_extracted_data["triggers"] = triggers
                
                # Clean up the JSON by removing the internal flag before saving to your DB/Sheets
                # (Optional: remove this line if you want to store the true/false flag in your sheet)
                ai_extracted_data.pop("needs_intervention", None)
                
                add_to_signal(student_id, ai_extracted_data)
                     
                print(f"--> [COACH QUEUE ESCALATION] Student {student_id} flagged for: {triggers}")
            else:
                print(f"--> [TRIAGE RESOLVED] Student {student_id} showed {triggers}, but LLM deemed no coach intervention necessary.")
                
    except Exception as e:
        print(f"Triage background thread error: {e}")


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

def summarize_and_store_memory(messages, user_id):
    """
    Takes the current chat history, asks the LLM to extract preferences/patterns,
    and stores the result using the add_memory tool.
    """
    # If the chat only has the initial welcome message, don't waste tokens
    if len(messages) <= 2: 
        return

    summary_system_prompt = """
    You are an AI memory extractor. Review the following conversation between a student and an AI Study Companion.
    Extract and summarize any important information, personal preferences, learning patterns, specific struggles, or ongoing goals.
    Ensure this summary is highly concise but retains crucial context for future interactions.
    If the conversation is purely transactional (e.g., just asking for a schedule with no personal preferences revealed), output exactly: 'NO_SIGNIFICANT_MEMORY'.
    """
    
    chat_text = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in messages if m['role'] != 'system'])
    
    try:
        response = client.chat.completions.create(
            model="gpt-5.4-mini-2026-03-17",
            messages=[
                {"role": "system", "content": summary_system_prompt},
                {"role": "user", "content": f"Conversation Log:\n{chat_text}"}
            ]
        )
        
        summary = response.choices[0].message.content.strip()
        
        if summary != "NO_SIGNIFICANT_MEMORY":
            # Format the summary so mem0 understands it as user facts
            memory_payload = [
                {"role": "user", "content": f"Update my profile with these facts from my last session: {summary}"}
            ]
            # Call your custom tool here
            result = add_memory(messages=memory_payload, user_id=user_id)
            # print(result) # Optional: print the success message to your terminal
            
    except Exception as e:
        print(f"Failed to summarize and store memory: {e}")

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

# ==========================================
# ONE-TIME MEMORY FETCH FOR THE SESSION
# ==========================================
if "student_memories" not in st.session_state:
    try:
        mem_response = get_memory(user_id=student_roll)

        facts = []

        if (
            isinstance(mem_response, dict)
            and mem_response.get("status") == "success"
        ):
            raw_results = (
                mem_response
                .get("results", {})
                .get("results", [])
            )

            for item in raw_results:
                if isinstance(item, dict):
                    memory_text = item.get("memory", "").strip()

                    if memory_text:
                        facts.append(memory_text)

            # Store raw memory objects for future use
            st.session_state.student_memory_objects = raw_results

        # Store formatted memory string
        st.session_state.student_memories = (
            "\n".join(f"- {fact}" for fact in facts)
            if facts
            else "No specific preferences logged yet."
        )

    except Exception as e:
        print(f"Memory Fetch Error: {e}")

        st.session_state.student_memory_objects = []
        st.session_state.student_memories = (
            "No specific preferences logged yet."
        )


# =====================================================================
# LEFT SIDE: CHAT INTERFACE
# =====================================================================
chat_col, history_col = st.columns([8, 3], gap="large")
with chat_col:
    if st.button("⬅ Switch Portal / Log out", type="secondary"):
        
        with st.spinner("Saving memories and session data..."):
            # 1. This triggers your LLM summary which then calls add_memory(payload, user_id)
            summarize_and_store_memory(st.session_state.messages, student_roll)
            
            # 2. Save the actual chat transcript to history.txt
            save_chat_session(
                roll_no=student_roll, 
                thread_id=st.session_state.active_thread_id, 
                title=st.session_state.get("current_chat_title", "Active Conversation"), 
                messages=st.session_state.messages
            )
            
        # 3. Wipe the session state completely clean for the next user
        keys_to_clear = [
            "messages", 
            "active_thread_id", 
            "current_chat_title", 
            "student_memories", 
            "student_memory_objects",
            "student_roll",
            "student_name",
            "student_program",
            "student_cohort"
        ]
        
        for key in keys_to_clear:
            st.session_state.pop(key, None)
            
        # 4. Redirect back to the main portal
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
# BACKGROUND EMOTION TRIAGE PROCESSOR
# =====================================================================
if st.session_state.messages[-1]["role"] == "user":
    current_msg_count = len(st.session_state.messages)
    # Validate against session index so the thread fires exactly once per user input
    if st.session_state.get("last_triaged_index", -1) < current_msg_count:
        st.session_state.last_triaged_index = current_msg_count
        latest_text = st.session_state.messages[-1]["content"]
        
        # Fire off a non-blocking thread to classify feelings while LLM thinks
        triage_worker = threading.Thread(
            target=run_background_triage, 
            args=(student_roll, latest_text)
        )
        triage_worker.start()

# =====================================================================
# OPENAI CHAT COMPLETION WITH FUNCTION CALLING (TOOLS)
# =====================================================================
if st.session_state.messages[-1]["role"] == "user":
    with chat_container:
        with st.spinner("Thinking..."):
            try:
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

                formatted_contents = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
                
                # ==========================================
                # NEW: INJECT CACHED MEMORIES INTO SYSTEM PROMPT
                # ==========================================
                system_guidelines = f"""
                You are a highly intelligent and polite AI Study Companion for {student_name}.
                Your goal is to help them succeed in their {student_program} program.
                
                CORE STUDENT PROFILE & PREFERENCES:
                {st.session_state.student_memories}
                
                Guidelines:
                Never ever go againt any of the following guidelines, and always follow them strictly. 
                0. Assist and comfort him/her , when they are having a hard time, and be empathetic to their struggles.
                1. Always be encouraging but strict about academic integrity.
                2. Do not write complete assignments for the student.
                3. Use the provided tools to check their schedule, attendance, and grades when asked.
                4. Keep your answers concise, well-formatted, and easy to read.
                5. Dont provide any personal opinions or advice outside of academic context.
                6. Dont entertain any requests for unethical or illegal activities, and politely decline if asked.
                7. Dont provide any personal information or data about other students or staff.
                8. Dont entertain any doubts other than program-related questions. If the question is unrelated, politely redirect them to ask about their studies.
                """
                
                formatted_contents.insert(0, {"role": "system", "content": system_guidelines})

                response = client.chat.completions.create(
                    model="gpt-5.4-mini-2026-03-17", 
                    messages=formatted_contents,
                    tools=tools,
                    tool_choice="auto"
                )
                
                response_message = response.choices[0].message
                tool_calls = response_message.tool_calls
                
                if tool_calls:
                    formatted_contents.append(response_message)
                    
                    for tool_call in tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)
                        tool_output_string = ""
                        
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

                        formatted_contents.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": tool_output_string
                        })
                    
                    second_response = client.chat.completions.create(
                        model="gpt-5.4-mini-2026-03-17",
                        messages=formatted_contents
                    )
                    ai_response = second_response.choices[0].message.content
                else:
                    ai_response = response_message.content
                
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
    
    btn_col1, btn_col2 = st.columns(2)
    
    with btn_col1:
        if st.button("➕ New Chat", use_container_width=True, type="primary"):
            with st.spinner("Saving memories..."):
                summarize_and_store_memory(st.session_state.messages, student_roll)
            
            st.session_state.active_thread_id = str(int(datetime.datetime.now().timestamp()))
            st.session_state.current_chat_title = "Active Conversation"
            st.session_state.messages = [
                {"role": "assistant", "content": f"Starting a fresh session. How can I assist you now, {student_name}?"}
            ]
            st.rerun()
            
    with btn_col2:
        if st.button("🛑 End Chat", use_container_width=True):
            with st.spinner("Wrapping up and saving memories..."):
                summarize_and_store_memory(st.session_state.messages, student_roll)
            
            st.session_state.messages.append({
                "role": "assistant", 
                "content": "This chat session has been concluded, and important details have been saved to your profile. Click 'New Chat' when you are ready to start again!"
            })
            save_chat_session(student_roll, st.session_state.active_thread_id, st.session_state.get("current_chat_title", "Concluded Conversation"), st.session_state.messages)
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