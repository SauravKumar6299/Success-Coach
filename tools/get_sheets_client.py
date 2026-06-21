import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/calendar' 
]


@st.cache_resource
def get_sheets_client():
    try:
        # st.secrets converts the TOML dictionary into what Google expects
        creds_info = dict(st.secrets["google_creds"])
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Credentials Error: {e}")
        return None