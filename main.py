import streamlit as st

from tools.get_sheets_client import get_sheets_client
from tools.verify_student import verify_student

# Set page configuration
st.set_page_config(page_title="Role Selection", page_icon="🎓", layout="wide")

# Custom CSS for styling
st.html(
    """
    <style>
    .main-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 70vh;
        text-align: center;
    }
    div.stButton > button {
        width: 100%;
        height: 60px;
        font-size: 20px !important;
        font-weight: 600 !important;
        color: white !important;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border: none !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 15px rgba(118, 75, 162, 0.3) !important;
        transition: all 0.3s ease !important;
    }
    div.stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(118, 75, 162, 0.5) !important;
        background: linear-gradient(135deg, #764ba2 0%, #667eea 100%) !important;
    }
    .login-box {
        background: white;
        padding: 2.5rem;
        border-radius: 16px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        border: 1px solid #E2E8F0;
        max-width: 500px;
        margin: 0 auto;
    }
    </style>
    """
)



if "show_student_login" not in st.session_state:
    st.session_state.show_student_login = False

# Student Verification View
if st.session_state.show_student_login:
    st.write("")
    st.write("")
    with st.container():
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.subheader("🎓 Student Verification")
        st.write("Verifying access using the central student roster sheet.")
        
        student_name = st.text_input("Full Name (as in sheet)", placeholder="Arjun Kumar")
        student_roll = st.text_input("Roll Number (student_id)", placeholder="STU001")
        
        col_back, col_sub = st.columns(2)
        with col_back:
            if st.button("Cancel", type="secondary"):
                st.session_state.show_student_login = False
                st.rerun()
        with col_sub:
            if st.button("Verify & Enter", type="primary"):
                if student_name.strip() and student_roll.strip():
                    with st.spinner("Checking roster..."):
                        is_valid, student_data = verify_student(student_name, student_roll)
                        
                    if is_valid:
                        st.session_state["student_name"] = student_data["name"]
                        st.session_state["student_roll"] = student_data["student_id"]
                        st.session_state["student_program"] = student_data["program"]
                        st.session_state["student_cohort"] = student_data["cohort"]
                        st.switch_page("pages/student_view.py")
                    else:
                        st.error(student_data)
                else:
                    st.error("Please fill in all fields.")
        st.markdown('</div>', unsafe_allow_html=True)

else:
    # Main Dashboard Menu
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    st.title("Welcome! Please Select Your Role")
    st.markdown("<p style='color: #666; font-size: 18px;'>Choose how you want to continue today</p>", unsafe_allow_html=True)

    st.write("")
    st.write("")

    col1, col2, col3, col4, col5 = st.columns([2, 2, 0.5, 2, 2])

    with col2:
        if st.button("🎓 Student"):
            st.session_state.show_student_login = True
            st.rerun()
            
    with col4:
        if st.button("🧠 Coach"):
            st.switch_page("pages/coach_view.py")
        
    st.markdown('</div>', unsafe_allow_html=True)