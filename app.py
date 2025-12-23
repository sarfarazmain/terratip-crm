import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
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

# --- 1. DATABASE CONNECTION ---
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

def hash_pass(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def init_auth_system(sh):
    try: ws = sh.worksheet("Users")
    except:
        ws = sh.add_worksheet(title="Users", rows=100, cols=5)
        ws.append_row(["Username", "Password", "Role", "Name"])
        ws.append_row(["admin", hash_pass("admin123"), "Manager", "System Admin"])
    return ws

def check_credentials(username, password, users_df):
    hashed = hash_pass(password)
    user_row = users_df[users_df['Username'] == username]
    if not user_row.empty:
        if user_row.iloc[0]['Password'] == hashed: return user_row.iloc[0]
    return None

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

# --- 2. INITIALIZATION ---
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

# --- 3. SESSION & LOGIN ---
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
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Login Karein"):
                users_df = pd.DataFrame(users_sheet.get_all_records())
                info = check_credentials(u, p, users_df)
                if info is not None:
                    st.session_state.update({'logged_in':True, 'username':info['Username'], 
                                             'role':info['Role'], 'name':info['Name']})
                    st.query_params["u"] = info['Username']; st.query_params["k"] = info['Password']
                    st.rerun()
                else: st.error("❌ Galat login")
    st.stop()

# --- 4. CRM DASHBOARD ---
st.sidebar.title("TerraTip CRM 🏡")
st.sidebar.write(f"👤 **{st.session_state['name']}**")
if st.sidebar.button("Logout"):
    st.session_state['logged_in'] = False
    st.query_params.clear()
    st.rerun()

def phone_btn(num): return f"""<a href="tel:{num}" style="display:inline-block;background-color:#28a745;color:white;padding:5px 12px;border-radius:4px;text-decoration:none;">📞 Call</a>"""

@st.fragment(run_every=10)
def show_live_leads_list(users_df):
    try:
        data = leads_sheet.get_all_records()
        df = pd.DataFrame(data)
    except: return
    
    if st.session_state['role'] == "Telecaller":
        c_match = [c for c in df.columns if "Assigned" in c]
        if c_match:
            df = df[(df[c_match[0]] == st.session_state['username']) | 
                    (df[c_match[0]] == st.session_state['name']) |
                    (df[c_match[0]] == "TC1")]

    if not df.empty and 'Client Name' in df.columns: df = df[df['Client Name'] != ""]
    if df.empty:
        st.info("📭 Abhi koi leads nahi hain.")
        return

    st.caption(f"⚡ Live Updates On (Auto-refresh every 10s)")
    status_opts = ["Naya Lead", "Call Uthaya Nahi / Busy", "Baat Hui - Interested", "Site Visit Scheduled", "Visit Done - Soch Raha Hai", "Faltu / Agent / Spam", "Not Interested (Mehenga Hai)", "Sold (Plot Bik Gaya)"]
    all_telecallers = users_df['Username'].tolist()

    for i, row in df.iterrows():
        name = row.get('Client Name', 'Unknown')
        status = row.get('Status', 'Naya Lead')
        phone = str(row.get('Phone', '')).replace(',', '').replace('.', '')
        assigned_to = row.get('Assigned', '-')
        
        icon = "⚪"
        if "Sold" in status: icon = "🟢"
        elif "Faltu" in status or "Not" in status: icon = "🔴"
        elif "Visit" in status: icon = "🚕"
        elif "Naya" in status: icon = "⚡"
        
        with st.expander(f"{icon} {name} | {status}"):
            instr = "❓ Update Status"
            if "Naya" in status: instr = "⚡ ACTION: Abhi call karein."
            elif "Busy" in status: instr = "⏰ ACTION: 4 ghante baad try karein."
            elif "Interested" in status: instr = "💬 ACTION: WhatsApp par brochure bhejein."
            elif "Visit" in status: instr = "📍 ACTION: Visit confirm karein."
            elif "Sold" in status: instr = "🎉 ACTION: Party!"
            elif "Faltu" in status: instr = "🗑️ ACTION: Ignore."
            
            if "🗑️" in instr or "❌" in instr: st.error(instr)
            elif "🎉" in instr: st.success(instr)
            else: st.info(instr)
            
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                st.write(f"📞 **{phone}**")
                st.write(f"📌 {row.get('Source', '-')}")
                st.caption(f"Assigned: {assigned_to}")
            with c2: st.markdown(phone_btn(phone), unsafe_allow_html=True)
            with c3: st.link_button("💬 WhatsApp", f"https://wa.me/91{phone}")
            
            with st.form(f"u_{i}"):
                c_up_1, c_up_2 = st.columns(2)
                with c_up_1: ns = st.selectbox("Status", status_opts, key=f"s_{i}", index=status_opts.index(status) if status in status_opts else 0)
                with c_up_2: note = st.text_input("Note", key=f"n_{i}")
                
                new_assign = None
                if st.session_state['role'] == "Manager":
                    try: curr_idx = all_telecallers.index(assigned_to)
                    except: curr_idx = 0
                    new_assign = st.selectbox("Re-Assign To:", all_telecallers, index=curr_idx, key=f"assign_{i}")

                if st.form_submit_button("💾 Update"):
                    try:
                        h = leads_sheet.row_values(1)
                        try: s_idx = h.index("Status") + 1
                        except: s_idx = 8
                        try: n_idx = h.index("Notes") + 1
                        except: n_idx = 12
                        try: a_idx = h.index("Assigned") + 1
                        except: a_idx = 7
                        try: t_idx = h.index("Last Call") + 1
                        except: t_idx = 10
                        
                        succ, msg = robust_update(leads_sheet, phone, s_idx, ns)
                        if succ:
                            if note: robust_update(leads_sheet, phone, n_idx, note)
                            robust_update(leads_sheet, phone, t_idx, datetime.now().strftime("%Y-%m-%d %H:%M"))
                            if new_assign and new_assign != assigned_to:
                                robust_update(leads_sheet, phone, a_idx, new_assign)
                            set_feedback(f"✅ Updated {name}!")
                            st.rerun()
                        else: st.error(msg)
                    except Exception as e: st.error(f"Err: {e}")

def show_add_lead_form(users_df):
    with st.expander("➕ Naya Lead Jodein", expanded=False):
        c1, c2 = st.columns(2)
        name = c1.text_input("Customer Ka Naam")
        phone = c2.text_input("Phone Number")
        c3, c4 = st.columns(2)
        src = c3.selectbox("Source", ["Meta Ads", "Canopy", "Agent", "Others"])
        ag = c4.text_input("Agent Name") if src == "Agent" else ""
        
        assign = st.session_state['username']
        if st.session_state['role'] == "Manager":
            all_u = users_df['Username'].tolist()
            assign = st.selectbox("Assign To", all_u, index=all_u.index(assign) if assign in all_u else 0)
        
        if st.button("💾 Save Lead"):
            if not name or not phone: st.error("⚠️ Name/Phone zaroori hai")
            else:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                leads_sheet.append_row(["L-New", ts, name, phone, src, ag, assign, "Naya Lead", "", ts])
                set_feedback(f"✅ Lead '{name}' Saved!")
                st.rerun()

# --- MASTER INSIGHTS PAGE (The Big Upgrade) ---
def show_master_insights():
    st.header("📊 Master Analytics & Team Status")
    
    try:
        df = pd.DataFrame(leads_sheet.get_all_records())
    except:
        st.error("No data available.")
        return

    if df.empty:
        st.info("No leads found.")
        return
    
    # --- PART 1: BUSINESS PERFORMANCE (Ad & Quality) ---
    st.subheader("1️⃣ Business Performance (Ads & Quality)")
    
    total = len(df)
    sold = len(df[df['Status'].str.contains("Sold", na=False)])
    junk = len(df[df['Status'].str.contains("Faltu|Not", na=False)])
    interested = len(df[df['Status'].str.contains("Interested|Visit", na=False)])
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Leads", total)
    m2.metric("🎉 Sold", sold)
    m3.metric("🔥 Interested", interested)
    m4.metric("🗑️ Junk", junk)
    
    c1, c2 = st.columns(2)
    with c1: 
        st.caption("Leads by Source (Kahan se aa rahe hain?)")
        if 'Source' in df.columns: st.bar_chart(df['Source'].value_counts())
    with c2:
        st.caption("Lead Quality Meter")
        jr = round((junk/total)*100) if total>0 else 0
        st.write(f"**Junk %:** {jr}%")
        st.progress(jr/100)
        if jr > 40: st.error("⚠️ Warning: Ad Quality is Poor (Too much junk). Check Meta Ads.")
        elif jr < 20: st.success("✅ Excellent: Ad Quality is Good.")
        else: st.warning("⚠️ Average: Ad Quality needs improvement.")

    st.divider()

    # --- PART 2: TEAM PERFORMANCE (Telecallers) ---
    st.subheader("2️⃣ Team Pulse (Telecaller Activity)")
    
    if 'Assigned' in df.columns:
        telecallers = df['Assigned'].unique()
        summary_data = []

        for tc in telecallers:
            tc_df = df[df['Assigned'] == tc]
            pending = len(tc_df[tc_df['Status'] == 'Naya Lead'])
            working = len(tc_df[tc_df['Status'].str.contains("Busy|Interested|Visit", na=False)])
            sold_tc = len(tc_df[tc_df['Status'].str.contains("Sold", na=False)])
            
            last_active = "-"
            if 'Last Call' in tc_df.columns:
                try: 
                    # Find latest date string
                    times = [x for x in tc_df['Last Call'] if x]
                    if times: last_active = max(times)
                except: pass

            summary_data.append({
                "User": tc,
                "Total": len(tc_df),
                "⚠️ Pending": pending,
                "🔥 Working": working,
                "🎉 Sold": sold_tc,
                "🕒 Last Active": last_active
            })
        
        st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
    
    # Unattended Warning
    naya_df = df[df['Status'] == "Naya Lead"]
    if not naya_df.empty:
        st.warning(f"⚠️ There are {len(naya_df)} Unattended Leads! (Status: 'Naya Lead')")
    else:
        st.success("✅ All leads are being attended.")

def show_admin(users_df):
    st.header("⚙️ Admin")
    show_feedback()
    c1, c2 = st.columns([1,2])
    with c1:
        with st.form("nu", clear_on_submit=True):
            u = st.text_input("User"); p = st.text_input("Pass", type="password")
            n = st.text_input("Name"); r = st.selectbox("Role", ["Telecaller", "Sales Specialist", "Manager"])
            if st.form_submit_button("Create"):
                if u in users_df['Username'].values: st.error("Exists")
                else: 
                    users_sheet.append_row([u, hash_pass(p), r, n])
                    set_feedback(f"✅ Created {u}"); st.rerun()
    with c2:
        st.dataframe(users_df[['Name','Username','Role']], hide_index=True)
        opts = [x for x in users_df['Username'].unique() if x != st.session_state['username']]
        if opts:
            dt = st.selectbox("Delete", opts)
            if st.button("❌ Delete"):
                users_sheet.delete_rows(users_sheet.find(dt).row)
                set_feedback(f"Deleted {dt}"); st.rerun()

def show_dashboard(users_df):
    show_feedback()
    show_add_lead_form(users_df)
    st.divider()
    show_live_leads_list(users_df)

if st.session_state['role'] == "Manager":
    t1, t2, t3 = st.tabs(["🏠 CRM", "📊 Insights", "⚙️ Admin"])
    with t1: show_dashboard(users_df)
    with t2: show_master_insights()
    with t3: show_admin(users_df)
else:
    show_dashboard(users_df)
