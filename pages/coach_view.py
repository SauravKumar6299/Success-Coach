import streamlit as st
import time
import pandas as pd
import os
from dotenv import load_dotenv
from requests.exceptions import ConnectionError

from tools.get_sheets_client import get_sheets_client
from tools.memory import search_memory  # Imported the mem0 search function

st.set_page_config(page_title="Coach Console", page_icon="🧠", layout="wide")

def fetch_student_data(max_retries=3):
    """Fetches data from the spreadsheet with automatic retries for network drops."""
    for attempt in range(max_retries):
        try:
            sheet = get_sheets_client().open_by_key(os.getenv("GOOGLE_SHEET_ID")).worksheet("signal_sheet")
            records = sheet.get_all_records()
            df = pd.DataFrame(records)
            if not df.empty:
                df['Sheet_Row'] = df.index + 2  # Keep track of actual row number (header is row 1)
            return df
        except ConnectionError:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                st.error("⚠️ Connection to Google Sheets failed. Please try again.")
                return pd.DataFrame()
    

def complete_task(sheet_row_index, student_id):
    """Callback function to delete the row from Google Sheets and update session state."""
    sheet = get_sheets_client().open_by_key(os.getenv("GOOGLE_SHEET_ID")).worksheet("signal_sheet")
    
    sheet.delete_rows(sheet_row_index)
    
    st.toast(f"Successfully removed {student_id}'s entry from the spreadsheet!", icon="✅")
    
    # Re-fetch the data to ensure the UI stays perfectly synced with the spreadsheet
    st.session_state.student_data = fetch_student_data()

# Custom styling for a clean, professional dashboard
st.html(
    """
    <style>
    .coach-header {
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #FFFFFF;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        text-align: center;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #10B981;
    }
    .student-card {
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #E2E8F0;
        margin-bottom: 0.5rem;
        background-color: #F8FAFC;
    }
    </style>
    """
)

# Back to Navigation Router
if st.button("⬅ Switch Portal / Log out", type="secondary"):
    st.switch_page("main.py")

st.markdown("<div class='coach-header'><h2>🧠 Coach Dashboard</h2><p style='color:#64748B;'>Manage schedules, student priorities, and daily agendas</p></div>", unsafe_allow_html=True)

# 1. Initialize session state variables
if "plan_generated" not in st.session_state:
    st.session_state.plan_generated = False

if "student_data" not in st.session_state:
    st.session_state.student_data = pd.DataFrame()

# Track fetched memories so we don't re-fetch constantly on rerun
if "student_contexts" not in st.session_state:
    st.session_state.student_contexts = {}

# 2. Main Generation Layout (Split into action panel and results)
col1, col2 = st.columns([1, 2], gap="large")

with col1:
    st.subheader("Daily Action Center")
    st.write("Click below to compile all syncing student pipelines, calendar markers, and review items into a single workflow.")
    
    # Generate Button
    if st.button("🎯 Generate Today's Plan", type="primary", use_container_width=True):
        with st.spinner("Fetching student metrics from Google Sheets..."):
            st.session_state.student_data = fetch_student_data()
            st.session_state.plan_generated = True
            st.toast("Today's routine generated perfectly!", icon="✅")
            st.rerun()

# 3. Conditional Rendering based on state
with col2:
    if st.session_state.plan_generated:
        st.subheader("Your Agenda Overview")
        
        pending_count = len(st.session_state.student_data) if not st.session_state.student_data.empty else 0
        
        # Simple analytic counters
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            st.markdown(f'<div class="metric-card"><div>Pending Students</div><div class="metric-value">{pending_count}</div></div>', unsafe_allow_html=True)
        with m_col2:
            st.markdown('<div class="metric-card"><div>Estimated Focus Time</div><div class="metric-value" style="color:#3B82F6;">4.5 Hrs</div></div>', unsafe_allow_html=True)
            
        st.write("")
        st.write("---")
        st.write("### 📋 Active Student Workflows")
        
        if pending_count == 0:
            st.success("All student tasks are complete for today! Great job.")
        else:
            # Iterate through the dataframe and create a custom row for each student
            for index, row in st.session_state.student_data.iterrows():
                
                # Fetch exact lowercase columns from the Google Sheet
                student_id = row.get("student_id", "Unknown ID")
                signal_type = row.get("signal_type", "N/A")
                severity = row.get("severity", "N/A")
                urgency = row.get("urgency", "N/A")
                reason = row.get("reason", "No reason provided")
                timestamp = row.get("timestamp", "")
                sheet_row = row.get("Sheet_Row")
                
                with st.container():
                    st.markdown("<div class='student-card'>", unsafe_allow_html=True)
                    data_col, btn_col = st.columns([5, 1]) 
                    
                    with data_col:
                        # Primary info
                        st.markdown(f"**{student_id}** | Signal Type: `{signal_type}`")
                        
                        # Secondary info (Severity & Urgency)
                        st.caption(f"**Severity:** {severity} &nbsp;|&nbsp; **Urgency:** {urgency}")
                        
                        # Tertiary info (Reason & Timestamp)
                        st.markdown(f"<span style='font-size: 0.9em; color: #475569;'>*Reason: {reason}*</span>", unsafe_allow_html=True)
                        if timestamp:
                            st.markdown(f"<div style='font-size: 0.75em; color: #94A3B8; margin-top: 4px;'>Logged: {timestamp}</div>", unsafe_allow_html=True)
                        
                        # --- MEMORY SEARCH INTEGRATION ---
                        with st.expander("🔍 View Relevant Student Context"):
                            context_key = f"context_{sheet_row}_{student_id}"
                            
                            # Check if we already fetched memory for this entry
                            if context_key in st.session_state.student_contexts:
                                st.markdown("**Relevant Memories & Context:**")
                                st.markdown(st.session_state.student_contexts[context_key])
                            else:
                                if st.button("Fetch Context via Mem0", key=f"fetch_btn_{sheet_row}_{index}"):
                                    with st.spinner("Searching student memories..."):
                                        mem_response = search_memory(query=reason, user_id=student_id)
                                        facts = []
                                        
                                        if isinstance(mem_response, dict) and mem_response.get("status") == "success":
                                            # Safely extract results whether it's a list directly or nested in a dict
                                            raw_results_data = mem_response.get("results", [])
                                            
                                            if isinstance(raw_results_data, dict):
                                                raw_results = raw_results_data.get("results", [])
                                            else:
                                                raw_results = raw_results_data

                                            for item in raw_results:
                                                if isinstance(item, dict):
                                                    memory_text = item.get("memory", "").strip()
                                                    if memory_text:
                                                        facts.append(memory_text)
                                            
                                            # Build the final summary string based on gathered facts
                                            if facts:
                                                summary_text = "\n".join([f"- {f}" for f in facts])
                                            else:
                                                summary_text = "*No prior relevant memory found for this specific issue.*"
                                                
                                            # Save to state and rerun to update the expander UI
                                            st.session_state.student_contexts[context_key] = summary_text
                                            st.rerun()
                                        
                                        else:
                                            summary_text = f"*Error fetching memory:* {mem_response.get('msg', 'Unknown error')}"
                                            st.session_state.student_contexts[context_key] = summary_text
                                            st.rerun()
                        # ----------------------------------

                    with btn_col:
                        st.write("") 
                        st.button(
                            "Complete ✅", 
                            key=f"btn_complete_{sheet_row}_{index}", 
                            on_click=complete_task, 
                            args=(sheet_row, student_id),
                            use_container_width=True
                        )
                    st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("No active plan generated yet. Click 'Generate Today's Plan' on the left to review your pending items.")