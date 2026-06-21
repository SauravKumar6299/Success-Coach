import streamlit as st
import time
import pandas as pd
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from requests.exceptions import ConnectionError

from tools.get_sheets_client import get_sheets_client
from tools.memory import search_memory, add_memory 
from tools.add_to_calender import add_to_calendar, remove_from_calendar, DURATION_MAP
from tools.add_to_signal import add_to_signal

st.set_page_config(page_title="Coach Console", page_icon="🎯", layout="wide")
IST = timezone(timedelta(hours=5, minutes=30))

def fetch_student_data(max_retries=3):
    """Fetches data and filters strictly for meets scheduled TODAY."""
    for attempt in range(max_retries):
        try:
            sheet = get_sheets_client().open_by_key(os.getenv("GOOGLE_SHEET_ID")).worksheet("signal_sheet")
            records = sheet.get_all_records()
            df = pd.DataFrame(records)
            
            if not df.empty:
                df['Sheet_Row'] = df.index + 2  
                today_date = datetime.now(IST).date()
                
                # Filter out meetings that aren't today
                def is_today(iso_str):
                    if not iso_str: return False
                    try:
                        # Parse ISO string and convert to IST to compare correctly
                        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00')).astimezone(IST)
                        return dt.date() == today_date
                    except:
                        return False
                        
                df = df[df['scheduled_on'].apply(is_today)]
                
            return df
        except ConnectionError:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                st.error("⚠️ Connection to Google Sheets failed. Please try again.")
                return pd.DataFrame()
    

def complete_task(sheet_row_index, student_id):
    """Deletes from BOTH Calendar and Sheets, logs to Mem0."""
    remove_from_calendar(student_id)
    sheet = get_sheets_client().open_by_key(os.getenv("GOOGLE_SHEET_ID")).worksheet("signal_sheet")
    sheet.delete_rows(sheet_row_index)
    
    today_str = datetime.now(IST).strftime("%B %d, %Y")
    try:
        add_memory(user_id=student_id, memory=f"Emergency sync meeting completed successfully on {today_str}.")
    except Exception as e:
        st.toast("Note: Could not save to mem0", icon="⚠️")
        
    st.toast(f"Successfully marked {student_id}'s meet as complete!", icon="✅")
    st.session_state.student_data = fetch_student_data()

def escalate_to_human_coach(roll_no: str, signal_type: str, severity: str, urgency: str, reason: str, start_day_offset: int = 0) -> str:
    ai_extracted_data = {
        "signal_type": signal_type,
        "severity": severity,
        "urgency": urgency,
        "reason": reason,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    cal_success, schedule_updates_or_msg = add_to_calendar(roll_no, ai_extracted_data, start_day_offset)
    if not cal_success:
        return f"Failed to escalate. Calendar Error: {schedule_updates_or_msg}"
        
    sig_success, sig_msg = add_to_signal(roll_no, ai_extracted_data, schedule_updates_or_msg)
    return f"Escalation Results -> {sig_msg} | Calendar completely synchronized."

def address_later_task(sheet_row_index, student_id, severity, signal_type, reason):
    remove_from_calendar(student_id)
    sheet = get_sheets_client().open_by_key(os.getenv("GOOGLE_SHEET_ID")).worksheet("signal_sheet")
    sheet.delete_rows(sheet_row_index)
    
    result_msg = escalate_to_human_coach(
        roll_no=student_id, 
        signal_type=signal_type, 
        severity=severity, 
        urgency="Deferred", 
        reason=reason,
        start_day_offset=1
    )
    st.toast(f"Cascade Triggered: {student_id} bumped to tomorrow. ({result_msg})", icon="🕒")
    st.session_state.student_data = fetch_student_data()

# ==========================================
# CUSTOM UI STYLING
# ==========================================
st.html(
    """
    <style>
    /* Global background adjustments */
    .stApp {
        background-color: #F3F4F6;
    }
    
    /* Header Styling */
    .coach-header {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        color: white;
        padding: 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        box-shadow: 0 10px 25px -5px rgba(59, 130, 246, 0.5);
    }
    .coach-header h2 { margin: 0; color: white; font-weight: 800; font-size: 2.5rem; }
    .coach-header p { margin: 0; color: #DBEAFE; font-size: 1.1rem; opacity: 0.9; margin-top: 0.5rem; }

    /* Metric Cards */
    .metric-container { display: flex; gap: 1rem; margin-bottom: 1.5rem; }
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 16px;
        border: 1px solid #E5E7EB;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        text-align: center;
        flex: 1;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    .metric-title { font-size: 0.9rem; color: #6B7280; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
    .metric-value { font-size: 2.5rem; font-weight: 800; color: #111827; margin-top: 0.5rem; line-height: 1; }
    .metric-highlight { color: #8B5CF6; } /* Purple for time */
    .metric-success { color: #10B981; } /* Green for count */

    /* Student Cards */
    .student-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
        margin-bottom: 1rem;
        border: 1px solid #F3F4F6;
        border-left: 6px solid #D1D5DB; /* Default border */
        transition: all 0.2s ease;
    }
    .student-card:hover {
        box-shadow: 0 8px 16px rgba(0,0,0,0.08);
        border-color: #E5E7EB;
    }
    
    /* Severity Colors */
    .sev-high { border-left-color: #EF4444; } /* Red */
    .sev-medium { border-left-color: #F59E0B; } /* Amber */
    .sev-low { border-left-color: #10B981; } /* Green */
    
    /* Badges */
    .badge {
        padding: 4px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase;
    }
    .badge-high { background-color: #FEE2E2; color: #B91C1C; }
    .badge-medium { background-color: #FEF3C7; color: #B45309; }
    .badge-low { background-color: #D1FAE5; color: #047857; }
    .badge-signal { background-color: #E0E7FF; color: #4338CA; margin-left: 8px; }
    
    .time-chip {
        display: inline-flex; align-items: center; background-color: #F3F4F6; color: #374151;
        padding: 4px 12px; border-radius: 8px; font-weight: 600; font-size: 0.9rem; margin-right: 12px;
    }
    </style>
    """
)

if st.button("⬅ Switch Portal / Log out", type="secondary"):
    st.switch_page("main.py")

st.markdown(
    """
    <div class='coach-header'>
        <h2>🎯 Coach Action Center</h2>
        <p>Manage today's high-priority student interactions and syncs.</p>
    </div>
    """, 
    unsafe_allow_html=True
)

if "plan_generated" not in st.session_state:
    st.session_state.plan_generated = False
if "student_data" not in st.session_state:
    st.session_state.student_data = pd.DataFrame()
if "student_contexts" not in st.session_state:
    st.session_state.student_contexts = {}

col1, col2 = st.columns([1, 2.5], gap="large")

with col1:
    st.subheader("⚡ Quick Actions")
    st.write("Fetch the latest synchronized pipeline data for today's schedule.")
    
    if st.button("🔄 Generate Today's Plan", type="primary", use_container_width=True):
        with st.spinner("Synchronizing with Calendar & Database..."):
            st.session_state.student_data = fetch_student_data()
            st.session_state.plan_generated = True
            st.toast("Today's routine generated perfectly!", icon="✅")
            st.rerun()

with col2:
    if st.session_state.plan_generated:
        pending_count = len(st.session_state.student_data) if not st.session_state.student_data.empty else 0
        
        # Calculate Dynamic Focus Time by summing each meeting's real block length.
        # DURATION_MAP is imported from the scheduler so this total always matches the
        # actual calendar durations (Critical 75 / High 60 / Medium 45 / Low 35).
        total_focus_minutes = 0
        if pending_count > 0:
            for _, row in st.session_state.student_data.iterrows():
                sev = str(row.get("severity", "Medium")).strip().title()
                total_focus_minutes += DURATION_MAP.get(sev, 30)
                    
        hours = total_focus_minutes // 60
        mins = total_focus_minutes % 60
        focus_time_display = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
        
        # Render Metric Dashboards
        st.markdown(
            f"""
            <div class="metric-container">
                <div class="metric-card">
                    <div class="metric-title">Today's Meets</div>
                    <div class="metric-value metric-success">{pending_count}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Est. Focus Time</div>
                    <div class="metric-value metric-highlight">⏱️ {focus_time_display}</div>
                </div>
            </div>
            """, 
            unsafe_allow_html=True
        )
        
        st.write("### 📋 Active Student Workflows")
        
        if pending_count == 0:
            st.success("🎉 Your schedule is completely clear for today! Great job catching up.")
        else:
            for index, row in st.session_state.student_data.iterrows():
                student_id = row.get("student_id", "Unknown ID")
                signal_type = row.get("signal_type", "N/A")
                severity = row.get("severity", "Medium")
                urgency = row.get("urgency", "N/A")
                reason = row.get("reason", "No reason provided")
                sheet_row = row.get("Sheet_Row")
                scheduled_time_raw = row.get("scheduled_on", "")
                
                # Format time
                nice_time = "Unknown"
                if scheduled_time_raw:
                    try:
                        nice_time = datetime.fromisoformat(scheduled_time_raw.replace('Z', '+00:00')).astimezone(IST).strftime("%I:%M %p")
                    except: pass

                # Map CSS classes based on severity
                sev_lower = str(severity).lower()
                border_class = "sev-high" if sev_lower in ["high", "critical"] else "sev-medium" if sev_lower == "medium" else "sev-low"
                badge_class = "badge-high" if sev_lower in ["high", "critical"] else "badge-medium" if sev_lower == "medium" else "badge-low"

                with st.container():
                    # Render custom card wrapper
                    st.markdown(f"<div class='student-card {border_class}'>", unsafe_allow_html=True)
                    
                    data_col, btn_col = st.columns([3.5, 1.5]) 
                    
                    with data_col:
                        # Top Row: Time, ID, Tags
                        st.markdown(
                            f"""
                            <div style="margin-bottom: 8px;">
                                <span class="time-chip">🕒 {nice_time}</span>
                                <strong style="font-size: 1.2rem; color: #111827;">{student_id}</strong>
                                <span class="badge {badge_class}" style="margin-left: 12px;">{severity}</span>
                                <span class="badge badge-signal">{signal_type}</span>
                            </div>
                            """, 
                            unsafe_allow_html=True
                        )
                        
                        # Body Row: Reason
                        st.markdown(f"<div style='color: #4B5563; font-size: 0.95rem; margin-bottom: 12px;'><strong>Reason:</strong> {reason}</div>", unsafe_allow_html=True)
                        
                        # Context Expander
                        with st.expander("🔍 View Prior Interactions (Mem0)"):
                            context_key = f"context_{sheet_row}_{student_id}"
                            if context_key in st.session_state.student_contexts:
                                st.markdown(st.session_state.student_contexts[context_key])
                            else:
                                if st.button("Fetch Context", key=f"fetch_btn_{sheet_row}_{index}", icon="🧠"):
                                    with st.spinner("Searching student memories..."):
                                        mem_response = search_memory(query=reason, user_id=student_id)
                                        facts = []
                                        if isinstance(mem_response, dict) and mem_response.get("status") == "success":
                                            raw_results_data = mem_response.get("results", [])
                                            raw_results = raw_results_data.get("results", []) if isinstance(raw_results_data, dict) else raw_results_data
                                            for item in raw_results:
                                                if isinstance(item, dict) and item.get("memory", "").strip():
                                                    facts.append(item.get("memory").strip())
                                            
                                            summary_text = "\n".join([f"- {f}" for f in facts]) if facts else "*No prior relevant memory found.*"
                                            st.session_state.student_contexts[context_key] = summary_text
                                            st.rerun()

                    with btn_col:
                        st.write("") # Spacer
                        # Action Buttons
                        st.button(
                            "Mark Complete", 
                            key=f"btn_complete_{sheet_row}_{index}", 
                            on_click=complete_task, 
                            args=(sheet_row, student_id),
                            type="primary",
                            use_container_width=True,
                            icon="✅"
                        )
                        
                        if pending_count > 2:
                            st.button(
                                "Address Later", 
                                key=f"btn_defer_{sheet_row}_{index}", 
                                on_click=address_later_task, 
                                args=(sheet_row, student_id, severity, signal_type, reason),
                                use_container_width=True,
                                icon="🕒"
                            )
                            
                    st.markdown("</div>", unsafe_allow_html=True) # End Card Wrapper
    else:
        # Empty state graphic/message
        st.info("No active plan generated yet. Click **Generate Today's Plan** on the left to review your pending items.")