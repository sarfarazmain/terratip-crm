import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import hashlib
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="TerraTip CRM", layout="wide", page_icon="🏡")

# --- HIDE STREAMLIT BRANDING ---
hide_bar = """
    <style>
        header {visibility: hidden;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stAppDeployButton {display: none;}
        [data-testid="stElementToolbar"] {display: none;}
        [data-testid="stDecoration"] {display: none;}
    </style>
"""
st.markdown(hide_bar, unsafe_allow_html=True)

# --- GLOBAL MESSAGE RELAY ---
def set_feedback(message, type="success"):
    st.session_state['feedback_msg'] = message
    st.session_state['feedback_type'] = type

def show_feedback():
    if 'feedback_msg' in st.session_state and st.session_state['feedback_msg']:
        msg = st.session_state['feedback_msg']
        typ = st.session_state.get('feedback_type', 'success')
        if typ == "success": st.success(msg)
        elif typ == "error": st.error(msg)
        elif typ == "warning": st.warning(msg)
        st.session_state['feedback_msg'] = None

# --- DATABASE ---
@st.cache_resource
def connect_db():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" not in st.secrets:
        st.error("❌ Secrets missing.")
        st.stop()
    creds_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    files = client.list_spreadsheet_files()
    if not files:
        st.error("❌ No Sheet found.")
        st.stop()
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
        if cell:
            sheet.update_cell(cell.row, col_index, value)
            return True, "Updated"
        return False, "Lead not found"
    except gspread.exceptions.APIError:
        time.sleep(1)
        try:
            cell = sheet.find(phone_number)
            if cell:
                sheet.update_cell(cell.row, col_index, value)
                return True, "Updated"
        except: return False, "API Error"
    except Exception as e: return False, str(e)

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
except Exception as e:
    st.error(f"Connection Error: {e}")
    st.stop()

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
        st.title("🔐 TerraTip Login")
        with st.form("login"):
            u = st.text_input("Username"); p = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                users_df = pd.DataFrame(users_sheet.get_all_records())
                u_row = users_df[users_df['Username'] == u]
                if not u_row.empty and u_row.iloc[0]['Password'] == hash_pass(p):
                    st.session_state.update({'logged_in':True, 'username':u, 
                                             'role':u_row.iloc[0]['Role'], 'name':u_row.iloc[0]['Name']})
                    st.query_params["u"] = u; st.query_params["k"] = hash_pass(p)
                    st.rerun()
                else: st.error("❌ Invalid")
    st.stop()

# --- APP ---
st.sidebar.title("TerraTip CRM 🏡")
st.sidebar.write(f"👤 **{st.session_state['name']}**")
if st.sidebar.button("Logout"):
    st.session_state['logged_in'] = False; st.query_params.clear(); st.rerun()

def phone_btn(num): return f"""<a href="tel:{num}" style="display:inline-block;background-color:#28a745;color:white;padding:5px 12px;border-radius:4px;text-decoration:none;">📞 Call</a>"""

# --- REMINDER LOGIC ---
def show_reminders_section(df):
    if df.empty: return
    
    # Try to find the Follow-up column
    col_name = next((c for c in df.columns if "Follow" in c), None)
    if not col_name: return # No column found, skip feature
    
    today = date.today()
    reminders = []
    
    for i, row in df.iterrows():
        f_date_str = str(row[col_name]).strip()
        if f_date_str and len(f_date_str) > 5: # Simple check for valid string
            try:
                # Support multiple formats
                try: f_date = datetime.strptime(f_date_str, "%Y-%m-%d").date()
                except: f_date = datetime.strptime(f_date_str, "%d/%m/%Y").date()
                
                # Logic: Overdue OR Due Today
                if f_date <= today and "Sold" not in row['Status'] and "Faltu" not in row['Status']:
                    reminders.append({
                        "Name": row.get('Client Name', 'Unknown'),
                        "Phone": str(row.get('Phone', '')),
                        "Date": f_date,
                        "Status": row.get('Status', '-')
                    })
            except: pass # Ignore bad date formats

    if reminders:
        # Sort: Oldest date first (Overdue first)
        reminders.sort(key=lambda x: x['Date'])
        
        st.warning(f"🔔 **Action Plan: {len(reminders)} Calls Due Today!**")
        
        with st.expander("👀 Click to see who to call", expanded=True):
            for r in reminders:
                is_overdue = r['Date'] < today
                color = "🔴" if is_overdue else "🟡"
                msg = "OVERDUE (Missed Call)" if is_overdue else "Call Today"
                
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1: st.write(f"**{color} {r['Name']}** ({msg})")
                with c2: st.markdown(phone_btn(r['Phone']), unsafe_allow_html=True)
                with c3: st.link_button("WhatsApp", f"https://wa.me/91{r['Phone']}")
                st.divider()

@st.fragment(run_every=10)
def show_live_leads_list(users_df):
    try: data = leads_sheet.get_all_records(); df = pd.DataFrame(data)
    except: return

    # --- SEARCH & FILTER ---
    c_search, c_filter = st.columns([2, 1])
    search_query = c_search.text_input("🔍 Search", placeholder="Name or Phone...")
    status_filter = c_filter.multiselect("Filter", df['Status'].unique() if 'Status' in df.columns else [])

    # Role Filter
    if st.session_state['role'] == "Telecaller":
        c_match = [c for c in df.columns if "Assigned" in c]
        if c_
