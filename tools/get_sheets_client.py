import streamlit as st
import gspread
import os
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Fetch configs dynamically from .env
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

@st.cache_resource
def get_sheets_client():
    try:
        creds = Credentials.from_service_account_file("google_creds.json", scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        st.error("Credentials Error: Make sure your json file is named 'google_creds.json' and is stored right next to main.py.")
        return None