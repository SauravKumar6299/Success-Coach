import streamlit as st
import time

st.set_page_config(page_title="Coach Console", page_icon="🧠", layout="wide")

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
    </style>
    """
)

# Back to Navigation Router
if st.button("⬅ Switch Portal / Log out", type="secondary"):
    st.switch_page("main.py")

st.markdown("<div class='coach-header'><h2>🧠 Coach Dashboard</h2><p style='color:#64748B;'>Manage schedules, student priorities, and daily agendas</p></div>", unsafe_allow_html=True)

# 1. Initialize session state variables to track if the plan has been generated
if "plan_generated" not in st.session_state:
    st.session_state.plan_generated = False

if "pending_tasks" not in st.session_state:
    st.session_state.pending_tasks = [
        "Review Alex's neural network assignment submission",
        "Prepare slide deck for afternoon's Advanced SQL live session",
        "Follow up with Sarah regarding her missed mock interview slot",
        "Grade milestone projects for Cohort 4 (12 submissions pending)",
        "Update Notion resource hub with fresh documentation links"
    ]

# 2. Main Generation Layout (Split into action panel and results)
col1, col2 = st.columns([1, 2], gap="large")

with col1:
    st.subheader("Daily Action Center")
    st.write("Click below to compile all syncing student pipelines, calendar markers, and review items into a single workflow.")
    
    # Generate Button
    if st.button("🎯 Generate Today's Plan", type="primary", use_container_width=True):
        with st.spinner("Analyzing student metrics and assembling tasks..."):
            time.sleep(1.2) # Simulating processing time
            st.session_state.plan_generated = True
            st.toast("Today's routine generated perfectly!", icon="✅")
            st.rerun()

# 3. Conditional Rendering based on state
with col2:
    if st.session_state.plan_generated:
        st.subheader("Your Agenda Overview")
        
        # Simple analytic counters
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            st.markdown(f'<div class="metric-card"><div>Pending Action Tasks</div><div class="metric-value">{len(st.session_state.pending_tasks)}</div></div>', unsafe_allow_html=True)
        with m_col2:
            st.markdown('<div class="metric-card"><div>Estimated Focus Time</div><div class="metric-value" style="color:#3B82F6;">4.5 Hrs</div></div>', unsafe_allow_html=True)
            
        st.write("")
        st.write("")
        
        # Dropdown UI to view details of the tasks
        # Option A: A structured Dropdown selection box
        selected_task = st.selectbox(
            "📋 Quick Inspect Pending Tasks:",
            options=st.session_state.pending_tasks,
            index=0
        )
        st.info(f"👉 **Active Selection Context:** {selected_task}")
        
        st.write("---")
        
        # Option B: Expander dropdown checklist (often preferred for interactive tasks)
        with st.expander("🔍 View Complete Task Breakdown Checklist", expanded=True):
            for i, task in enumerate(st.session_state.pending_tasks):
                st.checkbox(task, key=f"task_{i}")
                
    else:
        # Placeholder view before clicking generate
        st.info("No active plan generated yet. Click 'Generate Today's Plan' on the left to review your pending items.")