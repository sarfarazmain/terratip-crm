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
st.set_page_config(page_title="TerraTip CRM", layout="wide", page_icon="🏡", initial_sidebar_state="collapsed")

# --- CUSTOM CSS (Clean Dark Mode) ---
custom_css = """
    <style>
        /* Force Dark Mode */
        .stApp {
            background-color: #0e1117 !important;
            color: white !important;
        }
        
        /* Hide Default Header & Sidebar Button completely */
        header {visibility: hidden;}
        [data-testid="stSidebarCollapsedControl"] {display: none;}
        
        /* Input Fields */
        .stTextInput input {
            background-color: #1a1a1d !important;
            color: white !important;
            border: 1px solid #444 !important;
        }
        
        /* Custom Menu Button Styling */
        div[data-testid="stForm"] {border: none; padding: 0;}
        
        /* Card Styling */
        .stButton button {
            width: 100%;
            text-align: left !important;
            padding: 16px 18px !important;
            border-radius: 12px !important;
            background-color: #1a1a1d !important;
            border: 1px solid #333;
            margin-bottom: 8px;
        }
        .stButton button p {
            font-family: 'Source Sans Pro', sans-serif;
            color: #ffffff !important;
            font-size: 15px;
            margin: 0;
            line-height: 1.5;
        }
        
        /* Action Buttons */
        .big-btn { display: block; width: 100%; padding: 14px; text-align: center; border-radius: 10px; font-weight: bold; margin-bottom: 10px; text-decoration: none;}
        .call-btn { background-color: #28a745; color: white !important; }
        .wa-btn { background-color: #25D366; color: white !important; }
        .note-history { font-size: 13px; color: #ccc; background: #121212; padding: 12px; border-radius: 8px; max-height: 150px; overflow-y: auto; margin-bottom: 15px; border-left: 4px solid #555; }
        
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] button { border-radius: 20px; padding: 6px 12px; font-size: 13px; }
    </style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- TIMEZONE & SESSION ---
IST = pytz.timezone('Asia/Kolkata')
def get_ist_time(): return datetime.now(IST).strftime("%Y-%m-%d %H:%M")
def get_ist_date(): return datetime.now(IST).date()

# Initialize Navigation State
if 'current_page' not in st.session_state: st.session_state['current_page'] = "CRM"

# --- DATABASE CONNECTION ---
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

def generate_lead_id(prefix="L"):
    ts = str(int(time.time()))[-6:] 
    rand = str(random.randint(10, 99))
    return f"{prefix}-{ts}{rand}"

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

# --- LOGIN SCREEN ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if not st.session_state['logged_in']:
    qp = st.query_params
    if "u" in qp and "k" in qp:
        u_row = users_df[users_df['Username'] == qp["u"]]
        if not u_row.empty and u_row.iloc[0]['Password'] == qp["k"]:
            st.session_state.update({'logged_in':True, 'username':u_row.iloc[0]['Username'], 
                                     'role':u_row.iloc[0]['Role'], 'name':u_row.iloc[0]['Name']})
            st.rerun()

    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 TerraTip CRM")
        with st.form("login"):
            u = st.text_input("Username"); p = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                u_row = users_df[users_df['Username'] == u]
                if not u_row.empty and u_row.iloc[0]['Password'] == hash_pass(p):
                    st.session_state.update({'logged_in':True, 'username':u, 
                                             'role':u_row.iloc[0]['Role'], 'name':u_row.iloc[0]['Name']})
                    st.query_params["u"] = u; st.query_params["k"] = hash_pass(p)
                    st.rerun()
                else: st.error("❌ Invalid")
    st.stop()

# --- CUSTOM MENU (THE ALTERNATIVE FIX) ---
@st.dialog("🍔 Menu")
def open_main_menu():
    st.markdown(f"**👤 {st.session_state['name']}** ({st.session_state['role']})")
    st.divider()
    
    # Navigation Buttons
    c1, c2, c3 = st.columns(3)
    if c1.button("🏠 CRM", use_container_width=True): 
        st.session_state['current_page'] = "CRM"; st.rerun()
    if c2.button("📊 Stats", use_container_width=True): 
        st.session_state['current_page'] = "Insights"; st.rerun()
    if c3.button("⚙️ Admin", use_container_width=True): 
        st.session_state['current_page'] = "Admin"; st.rerun()
        
    st.divider()
    
    # Quick Add Lead inside Menu
    with st.expander("➕ Add New Lead"):
        with st.form("menu_add_lead"):
            name = st.text_input("Name")
            phone = st.text_input("Phone")
            src = st.selectbox("Source", ["Meta Ads", "Canopy", "Agent"])
            if st.form_submit_button("Save"):
                try:
                    ts = get_ist_time(); new_id = generate_lead_id()
                    row = [new_id, ts, name, phone, src, "", st.session_state['username'], "Naya Lead", "", ts, "", "", "", "", ""]
                    leads_sheet.append_row(row)
                    st.success("Added!"); time.sleep(1); st.rerun()
                except Exception as e: st.error(str(e))

    if st.button("🚪 Logout", use_container_width=True):
        st.session_state['logged_in'] = False; st.rerun()

# --- HELPERS ---
def big_call_btn(num): return f"""<a href="tel:{num}" class="big-btn call-btn">📞 CALL NOW</a>"""
def big_wa_btn(num, name): return f"""<a href="https://wa.me/91{num}?text=Namaste {name}" class="big-btn wa-btn" target="_blank">💬 WHATSAPP</a>"""

PIPELINE_OPTS = ["Naya Lead", "Ringing / No Response", "Call Back Later", "Interested / Send Details", "Follow-up / Thinking", "Site Visit Scheduled", "Negotiation / Visit Done", "Sale Closed", "Lost (Price / Location)", "Junk / Invalid / Broker"]

def get_status_icon(status):
    s = str(status).lower()
    if "naya" in s: return "🆕"
    if "ring" in s: return "📞"
    if "visit" in s: return "🗓️"
    if "lost" in s or "price" in s: return "📉"
    return "⚪"

# --- LEAD MODAL ---
@st.dialog("📋 Lead Details")
def open_lead_modal(row_dict, users_df):
    phone = str(row_dict.get('Phone', '')).replace(',', '').replace('.', '')
    name = row_dict.get('Client Name', 'Unknown')
    status = row_dict.get('Status', 'Naya Lead')
    notes = row_dict.get('Notes', '')
    
    c1, c2 = st.columns(2)
    with c1: st.markdown(big_call_btn(phone), unsafe_allow_html=True)
    with c2: st.markdown(big_wa_btn(phone, name), unsafe_allow_html=True)
    
    st.caption(f"👤 **{name}** | 📞 {phone}")
    
    # Status
    curr_idx = next((i for i, x in enumerate(PIPELINE_OPTS) if x.lower() == status.lower()), 0)
    new_status = st.selectbox("Status", PIPELINE_OPTS, index=curr_idx)
    
    # Notes
    if len(str(notes)) > 2: st.markdown(f"<div class='note-history'>{notes}</div>", unsafe_allow_html=True)
    new_note = st.text_input("New Note")
    
    # Date
    today = get_ist_date()
    col_d1, col_d2 = st.columns([2, 1])
    date_opt = col_d1.radio("Next Follow-up", ["None", "Tomorrow", "3 Days", "Custom"], horizontal=True, label_visibility="collapsed")
    final_date = None
    if date_opt == "Custom": final_date = st.date_input("Date", min_value=today)
    elif date_opt == "Tomorrow": final_date = today + timedelta(days=1)
    elif date_opt == "3 Days": final_date = today + timedelta(days=3)

    if st.button("✅ SAVE", type="primary", use_container_width=True):
        try:
            cell = leads_sheet.find(phone)
            if not cell: st.error("Not found")
            else:
                r = cell.row; h = leads_sheet.row_values(1)
                def get_col(n): return next((i+1 for i,v in enumerate(h) if n.lower() in v.lower()), None)
                
                updates = []
                updates.append({'range': gspread.utils.rowcol_to_a1(r, get_col("Status") or 8), 'values': [[new_status]]})
                if new_note:
                    full_note = f"[{datetime.now(IST).strftime('%d-%b')}] {new_note}\n{notes}"
                    updates.append({'range': gspread.utils.rowcol_to_a1(r, get_col("Notes") or 12), 'values': [[full_note]]})
                if final_date:
                    updates.append({'range': gspread.utils.rowcol_to_a1(r, get_col("Follow") or 15), 'values': [[str(final_date)]]})
                
                leads_sheet.batch_update(updates)
                st.rerun()
        except Exception as e: st.error(str(e))

# --- RENDER LIST ---
def render_list(df, users_df, label_prefix="", is_bulk=False):
    if df.empty: st.info("✅ No leads here."); return
    for i, row in df.iterrows():
        name = str(row.get('Client Name', 'Unknown'))
        status = str(row.get('Status', ''))
        phone = str(row.get('Phone', '')).replace(',', '').replace('.', '')
        
        # Date Logic
        f_val = str(row.get(next((c for c in df.columns if "Follow" in c), 'Follow'), '')).strip()
        display_date = ""
        if len(f_val) > 5:
            try:
                d = datetime.strptime(f_val, "%Y-%m-%d").date()
                display_date = "Today" if d == datetime.now(IST).date() else d.strftime('%d %b')
            except: pass
            
        # UI Label
        icon = get_status_icon(status)
        display_status = "Lost" if "Lost" in status or "Price" in status else status
        if "Ringing" in status: display_status = "Ringing"
        
        short_name = name[:20] + ".." if len(name) > 20 else name
        label = f"**{short_name}**\n{icon} {display_status}  •  📅 {display_date}" if display_date else f"**{short_name}**\n{icon} {display_status}"
        
        if is_bulk:
            c1, c2 = st.columns([0.15, 0.85])
            c1.checkbox("", key=f"sel_{label_prefix}_{phone}")
            if c2.button(label, key=f"btn_{label_prefix}_{phone}", use_container_width=True): open_lead_modal(row.to_dict(), users_df)
        else:
            if st.button(label, key=f"btn_{label_prefix}_{phone}", use_container_width=True): open_lead_modal(row.to_dict(), users_df)

# --- LIVE FEED LOGIC ---
@st.fragment(run_every=30)
def show_crm(users_df, search_q):
    try: df = pd.DataFrame(leads_sheet.get_all_records()); df.columns = df.columns.astype(str).str.strip()
    except: return

    # Filter by User
    if st.session_state['role'] == "Telecaller":
        ac = next((c for c in df.columns if "assign" in c.lower()), None)
        if ac: df = df[(df[ac] == st.session_state['username']) | (df[ac] == st.session_state['name']) | (df[ac] == "TC1")]

    # Search
    if search_q:
        res = df[df.astype(str).apply(lambda x: x.str.contains(search_q, case=False)).any(axis=1)]
        st.info(f"🔍 Found {len(res)}"); render_list(res, users_df, "search"); return

    # Buckets
    today = get_ist_date()
    def parse_date(v):
        try: return datetime.strptime(str(v).strip(), "%Y-%m-%d").date()
        except: return None
    
    f_col = next((c for c in df.columns if "Follow" in c), None)
    df['PD'] = df[f_col].apply(parse_date) if f_col else None
    
    dead = df['Status'].str.contains("Closed|Booked|Junk|Invalid|Agent", case=False, na=False)
    recycle = df['Status'].str.contains("Lost|Price|Location|Not Interest", case=False, na=False)
    action_cond = (df['PD'].notna() & (df['PD'] <= today)) | df['Status'].str.contains("Naya|New", case=False, na=False)
    future_cond = (df['PD'].notna() & (df['PD'] > today))
    
    t1, t2, t3, t4 = st.tabs([f"🔥 Action", f"📅 Future", f"♻️ Recycle", f"❌ Closed"])
    
    # Bulk Mode
    is_bulk = False
    if st.session_state['role'] == "Manager":
        is_bulk = st.toggle("⚡ Bulk Mode")
        if is_bulk and st.button("🗑️ DELETE SELECTED"):
            phones = [k.split("_")[-1] for k,v in st.session_state.items() if k.startswith("sel_") and v]
            if phones:
                all_v = leads_sheet.get_all_values()
                to_del = [i+1 for i,r in enumerate(all_v) if str(r[3]).replace(',','').replace('.','') in phones]
                for r in sorted(to_del, reverse=True): leads_sheet.delete_rows(r)
                st.rerun()

    with t1: render_list(df[action_cond & ~dead & ~recycle], users_df, "act", is_bulk)
    with t2: render_list(df[future_cond & ~dead & ~recycle], users_df, "fut", is_bulk)
    with t3: render_list(df[recycle & ~dead], users_df, "rec", is_bulk)
    with t4: render_list(df[dead], users_df, "hist", is_bulk)

# --- MAIN APP FLOW ---
# TOP BAR: SEARCH (Left) | MENU (Right)
c_search, c_menu = st.columns([0.85, 0.15])
with c_search:
    search_query = st.text_input("Search", placeholder="Search Leads...", label_visibility="collapsed")
with c_menu:
    # THE MENU BUTTON (Alternative to Sidebar)
    if st.button("🍔"):
        open_main_menu()

st.divider()

# PAGE ROUTING
if st.session_state['current_page'] == "CRM":
    show_crm(users_df, search_query)
elif st.session_state['current_page'] == "Insights":
    st.title("📊 Insights"); st.info("Analytics here")
    if st.button("Back"): st.session_state['current_page'] = "CRM"; st.rerun()
elif st.session_state['current_page'] == "Admin":
    st.title("⚙️ Admin"); st.info("Admin Panel here")
    if st.button("Back"): st.session_state['current_page'] = "CRM"; st.rerun()
