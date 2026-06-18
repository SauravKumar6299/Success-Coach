import os
from dotenv import load_dotenv

from tools.get_sheets_client import get_sheets_client 


# Load environment variables from .env file
load_dotenv()

# Fetch configs dynamically from .env
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


# Auth Logic matching your exact sheet columns
def get_attendance(roll_no):
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