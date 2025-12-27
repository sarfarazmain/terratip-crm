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
import pytz # TIMEZONE FIX

# --- CONFIGURATION ---
st.set_page_config(page_title="TerraTip CRM", layout="wide", page_icon="🏡")

# --- CUSTOM CSS ---
custom_css = """
    <style>
        header {visibility: hidden;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stAppDeployButton {display: none;}
        [data-testid="stElementToolbar"] {display: none;}
        [data-testid="stDecoration"] {display: none;}
        
        .block-container { padding-top: 1rem !important; }

        .streamlit-expanderHeader {
            font-size: 18px !important;
            font-weight: bold !important;
            padding: 20px !important; 
            background-color: #262730 !important;
            border: 1px solid #444 !important;
            border-radius: 10px !important;
            margin-bottom: 8px !important;
        }
        
        [data-testid="stExpander"] { border: None !important; box-shadow: None !important; }
        
        .big-btn {
            display: block;
            width: 100%;
            padding: 14px; 
            text-align: center;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 800;
            font-size: 16px;
            letter-spacing: 0.5px;
            margin-bottom: 5px;
        }
        .call-btn { background-color: #28a745; color: white !important; }
        .wa-btn { background-color: #25D366; color: white !important; }
        
        div[role="radiogroup"] > label {
            padding: 12px;
            background: #1e1e1e;
            border: 1px solid #333;
            border-radius: 6px;
            width: 100%;
            margin-bottom: 5px;
        }
        
        /* NOTE HISTORY BOX */
        .note-history {
            font-size: 12px;
            color: #aaa;
            background: #111;
            padding: 10px;
            border-radius: 5px;
            max-height: 100px;
            overflow-y: auto;
            margin-bottom: 10px;
            border: 1px solid #333;
        }
    </style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- TIMEZONE SETUP (IST) ---
IST = pytz.timezone('Asia/Kolkata')

def get_ist_time():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M")

def get_ist_date():
    return datetime.now(IST).date()

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

# --- APP LAYOUT ---
c_top_1, c_top_2 = st.columns([3, 1])
with c_top_1:
    st.markdown(f"### 🏡 TerraTip CRM\n👤 **{st.session_state['name']}** ({st.session_state['role']})")
with c_top_2:
    if st.button("🚪 Logout", key="logout_main", use_container_width=True):
        st.session_state['logged_in'] = False
        st.query_params.clear()
        st.rerun()
st.divider()

def big_call_btn(num): return f"""<a href="tel:{num}" class="big-btn call-btn">📞 CALL NOW</a>"""
def big_wa_btn(num, name): return f"""<a href="https://wa.me/91{num}?text=Namaste {name}" class="big-btn wa-btn" target="_blank">💬 WHATSAPP</a>"""

# --- LIVE FEED (FRAGMENT) ---
@st.fragment(run_every=30)
def show_live_leads_list(users_df, search_q, status_f):
    try: data = leads_sheet.get_all_records(); df = pd.DataFrame(data)
    except: return

    df.columns = df.columns.astype(str).str.strip()

    assign_col_name = next((c for c in df.columns if "assign" in c.lower()), None)

    if st.session_state['role'] == "Telecaller":
        if assign_col_name:
            df = df[(df[assign_col_name] == st.session_state['username']) | 
                    (df[assign_col_name] == st.session_state['name']) |
                    (df[assign_col_name] == "TC1")]

    if search_q: df = df[df.astype(str).apply(lambda x: x.str.contains(search_q, case=False)).any(axis=1)]
    if status_f: df = df[df['Status'].isin(status_f)]

    today = get_ist_date() # USE IST DATE
    
    def get_priority_data(row):
        status = row.get('Status', '')
        f_col = next((c for c in df.columns if "Follow" in c), None)
        f_date_str = str(row.get(f_col, '')).strip() if f_col else ""
        
        priority = 2
        alert_msg = ""
        
        if "Naya" in status: priority = 0; alert_msg = "⚡ NEW LEAD"
        elif "Negotiation" in status: priority = 0; alert_msg = "💰 CLOSING"
        elif f_date_str and len(f_date_str) > 5:
            try:
                f_date = datetime.strptime(f_date_str, "%Y-%m-%d").date()
                if f_date < today: priority = 0; alert_msg = "🔴 OVERDUE"
                elif f_date == today: priority = 1; alert_msg = "🟡 DUE TODAY"
            except: pass
        return priority, alert_msg

    if not df.empty:
        df[['Priority', 'Alert']] = df.apply(lambda row: pd.Series(get_priority_data(row)), axis=1)
        df = df.sort_values(by='Priority', ascending=True)

    if df.empty: st.info("📭 No leads found."); return

    st.caption(f"⚡ Live: {len(df)} Leads (IST Time: {get_ist_time()})")
    
    status_opts = [
        "Naya Lead", "Ringing / Busy / No Answer", "Asked to Call Later", 
        "Interested (Send Details)", "Site Visit Scheduled", "Visit Done (Negotiation)", 
        "Sale Closed / Booked", "Not Interested / Price / Location", "Junk / Invalid / Agent"
    ]
    all_telecallers = users_df['Username'].tolist()

    def get_smart_index(current_val):
        val = str(current_val).lower().strip()
        if val in [x.lower() for x in status_opts]:
            for i, x in enumerate(status_opts):
                if x.lower() == val: return i
        if "naya" in val or "new" in val: return 0
        if "ring" in val or "busy" in val or "uthaya" in val: return 1
        if "later" in val or "baad" in val or "call" in val: return 2
        if "interest" in val or "detail" in val or "bhej" in val: return 3
        if "schedule" in val or "site visit" in val or "visit confirmed" in val: return 4
        if "done" in val or "negotiat" in val or "visit done" in val or "soch" in val: return 5
        if "close" in val or "book" in val or "sold" in val: return 6
        if "not" in val or "price" in val or "location" in val or "mehenga" in val: return 7
        if "junk" in val or "invalid" in val or "agent" in val or "faltu" in val: return 8
        return 0

    # --- LOGIC FIX: Date Priority over Status ---
    def get_pipeline_action(status, f_date_str):
        # 1. Check Date FIRST
        if f_date_str and len(str(f_date_str)) > 5:
            try:
                f_date = datetime.strptime(f_date_str, "%Y-%m-%d").date()
                if f_date > today: return (f"📅 Scheduled: {f_date.strftime('%d-%b')}", "green")
                if f_date == today: return ("🟡 ACTION: Call Today!", "orange")
            except: pass

        # 2. Check Status SECOND
        s = status.lower()
        if "naya" in s: return ("⚡ ACTION: Call Immediately", "blue")
        if "ring" in s or "busy" in s: return ("⏰ ACTION: Retry in 4 hours", "orange")
        if "later" in s or "baad" in s: return ("📅 ACTION: Set Appointment", "orange")
        if "interest" in s: return ("💬 ACTION: WhatsApp Brochure", "green")
        if "schedule" in s: return ("📍 ACTION: Confirm Visit", "green")
        if "visit done" in s or "negotiat" in s: return ("💰 ACTION: Close Deal", "blue")
        if "closed" in s or "booked" in s: return ("🎉 ACTION: Party!", "green")
        if "junk" in s: return ("🗑️ ACTION: Ignore", "red")
        if "not" in s: return ("📉 ACTION: Ask for Referrals", "grey")
        return ("❓ ACTION: Update Status", "grey")

    for i, row in df.iterrows():
        name = row.get('Client Name', 'Unknown')
        status = str(row.get('Status', 'Naya Lead')).strip()
        phone = str(row.get('Phone', '')).replace(',', '').replace('.', '')
        assigned_to = row.get(assign_col_name, '-') if assign_col_name else '-'
        
        # Get Follow up column value
        f_col_name = next((c for c in df.columns if "Follow" in c), None)
        f_val = row.get(f_col_name, '') if f_col_name else ''
        
        icon = "⚪"
        if "Closed" in status: icon = "🟢"
        elif "Junk" in status or "Not Interest" in status: icon = "🔴"
        elif "Visit" in status: icon = "🚕"
        elif "Naya" in status: icon = "⚡"
        elif "Negotiation" in status: icon = "💰"
        
        alert_text = row.get('Alert', '')
        # Fix Action Logic Pass Date
        action_text, action_color = get_pipeline_action(status, str(f_val).strip())

        with st.expander(f"{icon} {alert_text} {name}"):
            if action_color == "blue": st.info(action_text)
            elif action_color == "green": st.success(action_text)
            elif action_color == "orange": st.warning(action_text)
            elif action_color == "red": st.error(action_text)
            else: st.info(action_text)
            
            b1, b2 = st.columns(2)
            with b1: st.markdown(big_call_btn(phone), unsafe_allow_html=True)
            with b2: st.markdown(big_wa_btn(phone, name), unsafe_allow_html=True)
            
            st.write("")
            st.markdown(f"**📞 {phone}** | 📌 {row.get('Source', '-')}")
            if st.session_state['role'] == "Manager": st.caption(f"Assigned: {assigned_to}")

            with st.form(f"u_{i}"):
                st.write("📝 **Status:**")
                default_idx = get_smart_index(status)
                ns = st.selectbox("Status", status_opts, key=f"s_{i}", index=default_idx, label_visibility="collapsed")
                
                # --- NOTE HISTORY LOGIC ---
                existing_notes = str(row.get('Notes', ''))
                if existing_notes and existing_notes != "nan":
                    st.markdown(f"<div class='note-history'>{existing_notes}</div>", unsafe_allow_html=True)
                
                c_u1, c_u2 = st.columns(2)
                new_note = c_u1.text_input("Add Note", key=f"n_{i}", placeholder="Type new note...")
                
                c_u2.write("📅 Follow-up:")
                # CUSTOM DATE PICKER LOGIC
                date_option = c_u2.radio("Follow-up", ["None", "Tom", "3 Days", "Custom"], horizontal=True, key=f"radio_{i}", label_visibility="collapsed")
                
                custom_date_val = None
                if date_option == "Custom":
                    custom_date_val = c_u2.date_input("Select Date", min_value=today, key=f"cd_{i}")
                
                final_date = None
                if date_option == "Tom": final_date = today + timedelta(days=1)
                elif date_option == "3 Days": final_date = today + timedelta(days=3)
                elif date_option == "Custom": final_date = custom_date_val
                
                new_assign = None
                if st.session_state['role'] == "Manager":
                    try: u_idx = all_telecallers.index(assigned_to)
                    except: u_idx = 0
                    new_assign = st.selectbox("Re-Assign:", all_telecallers, index=u_idx, key=f"a_{i}")

                st.write("")
                if st.form_submit_button("✅ UPDATE LEAD", type="primary", use_container_width=True):
                    try:
                        cell = leads_sheet.find(phone)
                        if not cell:
                            st.error("❌ Lead not found")
                        else:
                            r = cell.row
                            h = leads_sheet.row_values(1)
                            
                            def get_col(name):
                                try: return next(i for i,v in enumerate(h) if name.lower() in v.lower()) + 1
                                except: return None
                            
                            updates = []
                            s_idx = get_col("Status") or 8
                            updates.append({'range': gspread.utils.rowcol_to_a1(r, s_idx), 'values': [[ns]]})
                            
                            # APPEND NOTE LOGIC (IST TIME)
                            if new_note:
                                n_idx = get_col("Notes") or 12
                                timestamp_str = datetime.now(IST).strftime("%d/%m")
                                # If existing notes exist, prepend new note
                                updated_note = f"{timestamp_str}: {new_note} | {existing_notes}" if len(existing_notes) > 3 else f"{timestamp_str}: {new_note}"
                                updates.append({'range': gspread.utils.rowcol_to_a1(r, n_idx), 'values': [[updated_note]]})
                            
                            f_idx = get_col("Follow") or 15
                            if final_date: updates.append({'range': gspread.utils.rowcol_to_a1(r, f_idx), 'values': [[str(final_date)]]})
                            
                            t_idx = get_col("Last Call") or 10
                            updates.append({'range': gspread.utils.rowcol_to_a1(r, t_idx), 'values': [[get_ist_time()]]})
                            
                            if new_assign and new_assign != assigned_to:
                                a_idx = get_col("Assign") or 7
                                updates.append({'range': gspread.utils.rowcol_to_a1(r, a_idx), 'values': [[new_assign]]})
                            
                            c_idx = get_col("Count")
                            if c_idx:
                                curr = leads_sheet.cell(r, c_idx).value
                                val = int(curr) + 1 if curr and curr.isdigit() else 1
                                updates.append({'range': gspread.utils.rowcol_to_a1(r, c_idx), 'values': [[val]]})

                            leads_sheet.batch_update(updates)
                            set_feedback(f"✅ Updated {name}")
                            time.sleep(1)
                            st.rerun()
                    except Exception as e: st.error(f"Err: {e}")

def show_add_lead_form(users_df):
    with st.expander("➕ Naya Lead Jodein", expanded=False):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name"); phone = c2.text_input("Phone")
        c3, c4 = st.columns(2)
        src = c3.selectbox("Source", ["Meta Ads", "Canopy", "Agent", "Others"])
        ag = c4.text_input("Agent Name") if src == "Agent" else ""
        
        assign = st.session_state['username']
        if st.session_state['role'] == "Manager":
            all_u = users_df['Username'].tolist()
            assign = st.selectbox("Assign To", all_u, index=all_u.index(assign) if assign in all_u else 0)
        
        if st.button("Save Lead", use_container_width=True):
            if not name or not phone: st.error("⚠️ Required fields missing")
            else:
                try:
                    all_phones = leads_sheet.col_values(4)
                    clean_existing = {re.sub(r'\D', '', str(p))[-10:] for p in all_phones}
                    clean_new = re.sub(r'\D', '', phone)[-10:]
                    
                    if clean_new in clean_existing:
                        st.error(f"⚠️ Duplicate! {phone} already exists.")
                    else:
                        ts = get_ist_time()
                        new_id = generate_lead_id()
                        row_data = [new_id, ts, name, phone, src, ag, assign, "Naya Lead", "", ts, "", "", "", "", ""] 
                        leads_sheet.append_row(row_data)
                        set_feedback(f"✅ Saved {name}")
                        st.rerun()
                except Exception as e: st.error(f"Err: {e}")

def show_master_insights():
    st.header("📊 Analytics")
    try: df = pd.DataFrame(leads_sheet.get_all_records())
    except: 
        st.error("Could not load data.")
        return
    if df.empty: st.info("No data"); return

    df.columns = df.columns.astype(str).str.strip()

    st.subheader("1️⃣ Business Pulse")
    tot = len(df); sold = len(df[df['Status'].str.contains("Closed", na=False)])
    junk = len(df[df['Status'].str.contains("Junk|Not Interest", na=False)])
    m1,m2,m3 = st.columns(3)
    m1.metric("Total", tot); m2.metric("Sold", sold); m3.metric("Junk", junk)
    
    st.subheader("2️⃣ Team Activity")
    assign_col = next((c for c in df.columns if "assign" in c.lower()), None)
    
    if assign_col:
        stats = []
        for user, user_df in df.groupby(assign_col):
            pending = len(user_df[user_df['Status'] == 'Naya Lead'])
            working = len(user_df[user_df['Status'].str.contains("Busy|Interest|Visit", na=False)])
            sold_count = len(user_df[user_df['Status'].str.contains("Closed", na=False)])
            
            last_active = "-"
            lc_col = next((c for c in df.columns if "Last Call" in c), None)
            if lc_col:
                valid_dates = [str(d) for d in user_df[lc_col] if str(d).strip() != ""]
                if valid_dates: last_active = max(valid_dates)
            
            stats.append({
                "User": user,
                "Total": len(user_df
