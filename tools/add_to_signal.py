import os
from dotenv import load_dotenv

from tools.get_sheets_client import get_sheets_client 

# Load environment variables from .env file
load_dotenv()

# Fetch configs dynamically from .env
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Auth Logic matching your exact sheet columns
def add_to_signal(roll_no, ai_extracted_data):
    gc = get_sheets_client()
    if not gc:
        return False, "Database connection failed"
    try:
        sheet = gc.open_by_key(GOOGLE_SHEET_ID).worksheet("signal_sheet")
        
        # 1. Define the severity hierarchy (higher number = higher severity)
        severity_levels = {
            "Critical": 4,
            "High": 3,
            "Medium": 2,
            "Low": 1
        }
        
        # Get the new severity score (defaults to 0 if AI outputs something unexpected)
        new_severity_str = ai_extracted_data.get("severity", "")
        new_severity_score = severity_levels.get(new_severity_str, 0)
        
        # 2. Fetch all current data to check for existing entries
        all_records = sheet.get_all_values()
        
        existing_row_index = None
        current_severity_score = 0
        
        # Loop through existing records to find the student
        for i, row in enumerate(all_records):
            # row[0] is Column A (student_id)
            if row and row[0] == str(roll_no):
                existing_row_index = i + 1  # gspread uses 1-based indexing for rows
                # Column C (index 2) is severity
                current_severity_str = row[2] if len(row) > 2 else "" 
                current_severity_score = severity_levels.get(current_severity_str, 0)
                break
                
        # 3. Format the row data exactly matching your columns
        row_to_insert = [
            str(roll_no),
            ai_extracted_data.get("signal_type", ""),
            new_severity_str,
            ai_extracted_data.get("urgency", ""),
            ai_extracted_data.get("reason", ""),
            ai_extracted_data.get("timestamp", "")
        ]
        
        # 4. Apply the logic: Update, Discard, or Append
        if existing_row_index:
            if new_severity_score > current_severity_score:
                # Overwrite the existing row with the newly escalated data
                sheet.update(range_name=f"A{existing_row_index}:F{existing_row_index}", values=[row_to_insert])
                return True, f"Signal updated. Escalated to {new_severity_str} severity."
            else:
                # Discard the new entry because the coach already has a ticket of equal/higher severity
                return True, "Signal discarded. Existing entry has equal or higher severity."
        else:
            # Student not found, append a new row
            sheet.append_row(row_to_insert)
            return True, "New signal added successfully."
            
    except Exception as e:
        return False, f"Google Sheets error: {str(e)}"