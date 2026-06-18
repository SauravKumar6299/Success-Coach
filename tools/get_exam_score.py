import os
from dotenv import load_dotenv

from tools.get_sheets_client import get_sheets_client 


# Load environment variables from .env file
load_dotenv()

# Fetch configs dynamically from .env
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


# Auth Logic matching your exact sheet columns
def get_exam_score(roll_no):
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