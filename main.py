import streamlit as st

from tools.get_sheets_client import get_sheets_client
from tools.verify_student import verify_student
import time

# Set page configuration
st.set_page_config(page_title="Welcome Portal", page_icon="👋", layout="wide")

# ==========================================
# CUSTOM UI STYLING
# ==========================================
st.html(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    /* Global Background and Font */
    .stApp {
        background-color: #F8FAFC;
        font-family: 'Inter', sans-serif;
    }
    
    /* Hero Section */
    .hero-container {
        text-align: center;
        padding: 4rem 0 3rem 0;
    }
    .hero-title {
        font-size: 3.5rem;
        font-weight: 800;
        color: #0F172A;
        letter-spacing: -0.03em;
        margin-bottom: 0.5rem;
    }
    .hero-subtitle {
        font-size: 1.2rem;
        color: #64748B;
        font-weight: 400;
    }

    /* Role Cards */
    .role-card-container {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 24px;
        padding: 2.5rem 2rem;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        height: 100%;
        margin-bottom: 1rem;
    }
    .role-card-container:hover {
        transform: translateY(-8px);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
        border-color: #CBD5E1;
    }
    .role-icon {
        font-size: 4rem;
        margin-bottom: 1rem;
        line-height: 1;
    }
    .role-title {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.5rem;
    }
    .role-desc {
        color: #64748B;
        font-size: 0.95rem;
        line-height: 1.5;
        margin-bottom: 2rem;
    }

    /* Auth/Login Container */
    .auth-wrapper {
        background: #FFFFFF;
        padding: 3rem 2.5rem;
        border-radius: 24px;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01);
        border: 1px solid #E2E8F0;
        text-align: center;
        margin-top: 2rem;
    }
    .auth-icon-wrapper {
        background: #EEF2FF;
        width: 80px;
        height: 80px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 1.5rem auto;
        font-size: 2.5rem;
    }
    .auth-title {
        font-size: 1.75rem;
        font-weight: 700;
        color: #0F172A;
        margin-bottom: 0.25rem;
    }
    .auth-subtitle {
        color: #64748B;
        font-size: 0.95rem;
        margin-bottom: 2rem;
    }
    
    /* Streamlit Button Overrides */
    div[data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        color: white !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 0.5rem 1rem !important;
        border-radius: 12px !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover {
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3) !important;
        transform: translateY(-1px) !important;
    }
    div[data-testid="stButton"] > button[kind="secondary"] {
        background: #F1F5F9 !important;
        color: #475569 !important;
        border: 1px solid #E2E8F0 !important;
        font-weight: 600 !important;
        border-radius: 12px !important;
    }
    div[data-testid="stButton"] > button[kind="secondary"]:hover {
        background: #E2E8F0 !important;
        color: #1E293B !important;
    }
    </style>
    """
)

# Initialize Session State
if "show_student_login" not in st.session_state:
    st.session_state.show_student_login = False

# ==========================================
# VIEW 1: STUDENT VERIFICATION LOGIN
# ==========================================
if st.session_state.show_student_login:
    # Use columns to center the login box perfectly
    _, center_col, _ = st.columns([1, 1.5, 1])
    
    with center_col:
        st.markdown(
            """
            <div class="auth-wrapper">
                <div class="auth-icon-wrapper">🎓</div>
                <div class="auth-title">Student Verification</div>
                <div class="auth-subtitle">Secure access via the central student roster.</div>
            </div>
            """, 
            unsafe_allow_html=True
        )
        
        # We place the inputs right below the markdown so Streamlit native fields work seamlessly
        st.write("")
        student_name = st.text_input("Full Name", placeholder="e.g. Arjun Kumar")
        student_roll = st.text_input("Roll Number", placeholder="e.g. STU001")
        
        st.write("")
        st.write("")
        
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("Cancel", type="secondary", use_container_width=True):
                st.session_state.show_student_login = False
                st.rerun()
        with btn_col2:
            if st.button("Verify & Enter", type="primary", use_container_width=True):
                if student_name.strip() and student_roll.strip():
                    with st.spinner("Authenticating..."):
                        is_valid, student_data = verify_student(student_name, student_roll)
                        
                    if is_valid:
                        # Set secure session state variables
                        st.session_state["student_name"] = student_data["name"]
                        st.session_state["student_roll"] = student_data["student_id"]
                        st.session_state["student_program"] = student_data["program"]
                        st.session_state["student_cohort"] = student_data["cohort"]
                        st.success("Verification successful! Redirecting...")
                        time.sleep(0.5) # Slight delay for smooth visual transition
                        st.switch_page("pages/test_stu_view.py")
                    else:
                        st.error(student_data)
                else:
                    st.warning("Please fill in all fields to continue.")

# ==========================================
# VIEW 2: ROLE SELECTION DASHBOARD
# ==========================================
else:
    st.markdown(
        """
        <div class="hero-container">
            <div class="hero-title">Welcome to the Portal</div>
            <div class="hero-subtitle">Select your access level to continue to your tailored workspace.</div>
        </div>
        """, 
        unsafe_allow_html=True
    )

    st.write("")
    
    # Perfectly center the two role cards
    _, stu_col, coach_col, _ = st.columns([1, 1.5, 1.5, 1], gap="large")

    with stu_col:
        st.markdown(
            """
            <div class="role-card-container">
                <div class="role-icon">🎓</div>
                <div class="role-title">Student</div>
                <div class="role-desc">Access your AI study companion, view your schedules, and manage your academic pipeline.</div>
            </div>
            """, 
            unsafe_allow_html=True
        )
        if st.button("Login as Student", type="primary", use_container_width=True, key="btn_stu"):
            st.session_state.show_student_login = True
            st.rerun()
            
    with coach_col:
        st.markdown(
            """
            <div class="role-card-container">
                <div class="role-icon">🧠</div>
                <div class="role-title">Coach</div>
                <div class="role-desc">Review student escalations, manage triage schedules, and address high-priority syncs.</div>
            </div>
            """, 
            unsafe_allow_html=True
        )
        if st.button("Enter Coach Console", type="primary", use_container_width=True, key="btn_coach"):
            st.switch_page("pages/coach_view.py")