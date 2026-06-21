import os
from typing import List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
import os
from dotenv import load_dotenv

from tools.get_sheets_client import get_sheets_client 

load_dotenv()

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]



llm = ChatOpenAI(model="gpt-5.4-mini-2026-03-17", temperature=0.2)


# =====================================================================
# PHASE 1: DEFINE SUBAGENT CORE DATA TOOLS
# =====================================================================

@tool
def get_attendance(roll_no):
    """Retrieve attendance records for a student based on their roll number."""
    gc = get_sheets_client()
    if not gc:
        return False, "Database connection failed"
    try:
        # 1. Switch to the correct worksheet tab based on your screenshot
        worksheet = gc.open_by_key(GOOGLE_SHEET_ID).worksheet("attendance")
        records = worksheet.get_all_records()
        
        attendance_records = []
        # 2. Loop through and find the match for BOTH student_i
        for row in records:
            # Match sheet string formatting with your function parameters
            if str(row.get("student_id")) == str(roll_no):
                attendance_records.append(row)

        # 3. Return the found attendance records or an error message
        if attendance_records:
            return True, attendance_records
        return False, f"No attendance record found for Student {roll_no}."
        
    except Exception as e:
        return False, f"Attendance retrieval error: {str(e)}"

@tool
def get_exam_schedule(roll_no):
    """Retrieve exam schedule for a student based on their roll number."""
    gc = get_sheets_client()
    if not gc:
        return False, "Database connection failed"
    try:
        # Access the specific 'roster' worksheet tab from your screenshot
        worksheet = gc.open_by_key(GOOGLE_SHEET_ID).worksheet("exam_schedule")
        records = worksheet.get_all_records()
        exam_schedule = []
        for row in records:
            if str(row.get("student_id")).strip().lower() == roll_no.strip().lower():
                exam_schedule.append(row)

        if exam_schedule:
            return True, exam_schedule  # Return all matching exam schedules
                
        return False, "Invalid Name or Roll Number. Profile not found in roster."
    except Exception as e:
        return False, f"Authentication error: {str(e)}"

@tool
def get_exam_score(roll_no):
    """Retrieve exam scores for a student based on their roll number."""
    gc = get_sheets_client()
    if not gc:
        return False, "Database connection failed"
    try:
        # Access the specific 'exam_scores' worksheet tab from your screenshot
        worksheet = gc.open_by_key(GOOGLE_SHEET_ID).worksheet("exam_scores")
        records = worksheet.get_all_records()
        exam_scores = []
        for row in records:
            if str(row.get("student_id")) == str(roll_no):
                exam_scores.append(row)

        if exam_scores:
            return True, exam_scores
        return False, "Invalid Name or Roll Number. Profile not found in roster."
    except Exception as e:
        return False, f"Authentication error: {str(e)}"


# Gather tools dedicated exclusively to student information parsing
student_info_tools = [get_attendance, get_exam_schedule, get_exam_score]

# =====================================================================
# PHASE 2: CONSTRUCT THE STUDENT INFO SUBAGENT
# =====================================================================

student_agent_prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "You are a specialized Student Information Subagent. Your sole responsibility is to lookup "
        "attendance, schedules, and scores. Combine data accurately before returning your response. "
        "Be factual and concise."
    )),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# Create the internal execution pipeline for the subagent
student_info_agent = create_openai_tools_agent(llm, student_info_tools, student_agent_prompt)
student_info_agent_executor = AgentExecutor(agent=student_info_agent, tools=student_info_tools, verbose=True)
