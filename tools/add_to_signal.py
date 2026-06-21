import os
from dotenv import load_dotenv
from tools.get_sheets_client import get_sheets_client 

load_dotenv()
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

def add_to_signal(roll_no, ai_extracted_data, schedule_updates):
    """
    Updates the main student row AND synchronizes the 'scheduled_on' 
    column for any other students bumped by the calendar algorithm.
    """
    gc = get_sheets_client()
    if not gc:
        return False, "Database connection failed"
        
    try:
        sheet = gc.open_by_key(GOOGLE_SHEET_ID).worksheet("signal_sheet")
        all_records = sheet.get_all_values()
        
        # Map existing roll numbers to their row index (1-based for gspread)
        row_map = {row[0]: i+1 for i, row in enumerate(all_records) if row}
        
        # 1. Update dates for any students that were bumped around by the algorithm
        for student_id, new_date in schedule_updates.items():
            if student_id == roll_no:
                continue 
            if student_id in row_map:
                row_idx = row_map[student_id]
                sheet.update_cell(row_idx, 7, new_date) # Col G is index 7
                
        # 2. Insert or completely overwrite the primary student row
        target_date = schedule_updates.get(roll_no, "")
        
        row_to_insert = [
            str(roll_no),                                # A: student_id
            ai_extracted_data.get("signal_type", ""),    # B: signal_type
            ai_extracted_data.get("severity", ""),       # C: severity
            ai_extracted_data.get("urgency", ""),        # D: urgency
            ai_extracted_data.get("reason", ""),         # E: reason
            ai_extracted_data.get("timestamp", ""),      # F: timestamp
            target_date                                  # G: scheduled_on
        ]
        
        if str(roll_no) in row_map:
            row_idx = row_map[str(roll_no)]
            # Overwrite A through G
            sheet.update(range_name=f"A{row_idx}:G{row_idx}", values=[row_to_insert])
            return True, f"Signal updated. Assigned to {target_date}."
        else:
            sheet.append_row(row_to_insert)
            return True, f"New signal added. Assigned to {target_date}."
            
    except Exception as e:
        return False, f"Google Sheets error: {str(e)}"