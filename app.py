import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date, timedelta
import hashlib
import time
import re
import random
import itertools
import pytz

# --- CONFIGURATION ---
st.set_page_config(page_title="TerraTip CRM", layout="wide", page_icon="🏡")

# --- CUSTOM CSS (THE FLOAT FIX) ---
custom_css = """
    <style>
        header {visibility: hidden;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stAppDeployButton {display: none;}
        
        .block-container { padding-top: 0.5rem !important; }

        /* --- HEADER CONTAINER --- */
        .streamlit-expanderHeader {
            background-color: #262730 !important;
            border: 1px solid #444 !important;
            border-radius: 8px !important;
            padding: 10px 14px !important;
            margin-bottom: 6px !important;
            color: #eee !important;
            font-family: 'Roboto', sans-serif;
            font-size: 15px !important;
        }
        
        /* Ensure the paragraph takes full width */
        .streamlit-expanderHeader p {
            width: 100%;
            margin: 0;
            display: block; /* Block display allows floating */
        }

        /* 1. BADGE (Bold Text) */
        .streamlit-expanderHeader strong {
            display: inline-block;
            min-width: 80px;
            text-align: center;
            background: #333;
            color: #fff;
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 700;
            font-size: 12px;
            margin-right: 10px;
            border: 1px solid #555;
            vertical-align: middle;
        }

        /* 2. TAGS (Code Text) */
        .streamlit-expanderHeader code {
            font-family: sans-serif;
            font-size: 11px;
            background: #444;
            color: #ccc;
            padding: 2px 5px;
            border-radius: 3px;
            margin-left: 6px;
            border: none;
            vertical-align: middle;
        }

        /* 3. TIME (Italic Text) - THE FLOAT RIGHT FIX */
        .streamlit-expanderHeader em {
            float: right; /* <--- THIS IS THE KEY */
            font-style: normal;
            font-size: 12px;
            color: #aaa;
            background: #1e1e1e; /* Slight background for contrast */
            padding: 2px 6px;
            border-radius: 4px;
            margin-top: 2px; /* Slight alignment tweak */
        }

        /* ACTION BUTTONS */
        .big-btn {
            display: block;
            width: 100%;
            padding: 10px; 
            text-align: center;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 700;
            font-size: 14px;
            letter-spacing: 0.5px;
            margin-bottom: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        .call-btn { background-color: #28a745; color: white !important; }
        .wa-btn { background-color: #25D366; color: white !important; }
        
        .note-history {
            font-size: 12px;
            color: #bbb;
            background: #121212;
            padding: 10px;
            border-radius: 6px;
            max-height: 80px;
            overflow-y: auto;
            margin-bottom: 10px;
            border-left: 3px solid #555;
        }
        
        div[role="radiogroup"] > label {
            padding: 5px 10px;
            background: #1e1e1e;
            border: 1px solid #333;
            border-radius: 4px;
            font-size: 14px;
        }
        
        [data-testid="stCheckbox"] { margin-top: 12px; }
    </style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- TIMEZONE SETUP (IST) ---
IST = pytz.timezone('Asia/Kolkata')

def get_ist_time(): return datetime.now(IST).strftime("%Y-%m-%d %H:%M")
def get_ist_date(): return datetime.now(IST).date()

# --- FEEDBACK SYSTEM ---
def set_feedback(message, type="success"):
    st.session_state['feedback_msg'] = message
    st.session_state['feedback_type'] = type

def show_feedback():
    if 'feedback_msg' in st.session_state and st.session_state['feedback_msg']:
        msg = st.session_state['feedback_msg']
        typ = st.session_state.get('feedback_type', 'success')
        if typ == "success": st.toast(msg, icon="✅"); st.success(msg, icon="✅")
        elif typ == "error": st.toast(msg, icon="❌"); st.error(msg, icon="❌")
        elif typ == "warning": st.toast(msg, icon="⚠️"); st.warning(msg, icon="⚠️")
        st.session_state['feedback_msg'] = None

# --- DATABASE ---
@st.cache_resource
def connect_db():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" not in st.secrets: st.error("❌ Secrets missing."); st.stop()
    creds_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in creds_dict: creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    files = client.list_spreadsheet_files()
    if not files: st.error("❌ No Sheet found."); st.stop()
    return client.open_by_key(files[0]['id'])

def hash_pass(password): return hashlib.sha256(str.encode(password)).hexdigest()

def init_auth_system(sh):
    try: ws = sh.worksheet("Users")
    except:
        ws = sh.add_worksheet(title="Users", rows=100, cols=5)
        ws.append_row(["Username", "Password", "Role", "Name"])
        ws.append_row(["admin", hash_pass("admin123"), "Manager", "System Admin"])
    return ws

def robust_update(sheet, phone_number, col_index, value):
    try:
        cell = sheet.find(phone_number)
        if cell: sheet.update_cell(cell.row, col_index, value); return True, "Updated"
        return False, "Lead not found"
    except Exception as e: return False, str(e)

def generate_lead_id(prefix="L"):
    ts = str(int(time.time()))[-6:] 
    rand = str(random.randint(10, 99))
    return f"{prefix}-{ts}{rand}"

def get_time_ago(last_call_str):
    if not last_call_str or len(str(last_call_str)) < 5: return "New"
    try: last_dt = datetime.strptime(str(last_call_str).strip(), "%Y-%m-%d %H:%M")
    except:
        try: last_dt = datetime.strptime(str(last_call_str).strip(), "%Y-%m-%d")
        except: return "-"
    
    if last_dt.tzinfo is None: last_dt = IST.localize(last_dt)
    now = datetime.now(IST)
    diff = now - last_dt
    
    if diff.days == 0:
        hrs = diff.seconds // 3600
        if hrs == 0: return "Now"
        return f"{hrs}h"
    elif diff.days == 1: return "1d"
    else: return f"{diff.days}d"

# --- HELPER: DETECT HINDI/QUESTIONS ---
def is_likely_question(header_text):
    # Check for Devanagari (Hindi) Unicode Range
    if re.search(r'[\u0900-\u097F]', str(header_text)):
        return True
    # Check for keywords
    keywords = ["budget", "size", "plot", "location", "planning", "kab", "kahan", "kitna"]
    return any(k in str(header_text).lower() for k in keywords)

# --- INITIALIZATION ---
try:
    sh = connect_db()
    users_sheet = init_auth_system(sh)
    users_data = users_sheet.get_all_records()
    users_df = pd.DataFrame(users_data)
    found_sheet = None
    for ws in sh.worksheets():
        if "lead" in ws.title.lower(): found_sheet = ws; break
    leads_sheet = found_sheet if found_sheet else sh.get_worksheet(0)
except Exception as e: st.error(f"Connection Error: {e}"); st.stop()

# --- LOGIN ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if not st.session_state['logged_in']:
    qp = st.query_params
    if "u" in qp and "k" in qp:
        u_row = users_df[users_df['Username'] == qp["u"]]
        if not u_row.empty and u_row.iloc[0]['Password'] == qp["k"]:
            st.session_state.update({'logged_in':True, 'username':u_row.iloc[0]['Username'], 
                                     'role':u_row.iloc[0]['Role'], 'name':u_row.iloc[0]['Name']})
            st.rerun()

if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 TerraTip CRM")
        with st.form("login"):
            u = st.text_input("Username"); p = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                users_df = pd.DataFrame(users_sheet.get_all_records())
                u_row = users_df[users_df['Username'] == u]
                if not u_row.empty and u_row.iloc[0]['Password'] == hash_pass(p):
                    st.session_state.update({'logged_in':True, 'username':u, 
                                             '
