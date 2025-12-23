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

# --- CONFIGURATION ---
st.set_page_config(page_title="TerraTip CRM", layout="wide", page_icon="🏡")

# --- CUSTOM CSS (MOBILE OPTIMIZED) ---
custom_css = """
    <style>
        header {visibility: hidden;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stAppDeployButton {display: none;}
        [data-testid="stElementToolbar"] {display: none;}
        [data-testid="stDecoration"] {display: none;}
        
        /* CARD STYLING */
        [data-testid="stExpander"] {
            background-color: #1E1E1E;
            border: 1px solid #444;
            border-radius: 12px;
            margin-bottom: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        
        /* MASSIVE BUTTONS */
        .big-btn {
            display: block;
            width: 100%;
            padding: 16px; 
            text-align: center;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 900;
            font-size: 18px;
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: all 0.2s;
        }
        .big-btn:active { transform: scale(0.98); }
        .call-btn { background-color: #28a745; color: white !important; }
        .wa-btn { background-color: #25D366; color: white !important; }
        
        /* FORM CLEANUP */
        .stRadio > div { gap: 12px; }
        div[role="radiogroup"] > label {
            background: #2b2b2b;
            padding: 10px;
            border-radius: 6px;
            border: 1px solid #333;
            width: 100%;
        }
        div[role="radiogroup"] > label:hover {
            border-color: #666;
        }
    </style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- FEEDBACK SYSTEM ---
def set_feedback(message, type="success"):
    st.session_state['feedback_msg'] = message
    st.session_state['feedback_type'] = type

def show_feedback():
    if 'feedback_msg' in st.session_state and st.session_state['feedback_msg']:
        msg = st.session_state['feedback_msg']
        typ = st.session_state.get('feedback_type', 'success')
        
        if typ == "success": 
            st.toast(msg, icon="✅")
            st.success(msg, icon="✅")
        elif typ == "error": 
            st.toast(msg, icon="❌")
            st.error(msg, icon="❌")
        elif typ == "warning": 
            st.toast(msg, icon="⚠️")
            st.warning(msg, icon="⚠️")
            
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

# --- ID GENERATOR ---
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

# --- APP ---
st.sidebar.title("TerraTip CRM 🏡")
st.sidebar.write(f"👤 **{st.session_state['name']}**")
if st.sidebar.button("Logout"):
    st.session_state['logged_in'] = False; st.query_params.clear(); st.rerun()

def big_call_btn(num): return f"""<a href="tel:{num}" class="big-btn call-btn">📞 CALL NOW</a>"""
def big_wa_btn(num, name): return f"""<a href="https://wa.me/91{num}?text=Namaste {name}" class="big-btn wa-btn" target="_blank">💬 WHATSAPP</a>"""

@st.fragment(run_every=10)
def show_live_leads_list(users_df):
    try: data = leads_sheet.get_all_records(); df = pd.DataFrame(data)
    except: return

    c_search, c_filter = st.columns([2, 1])
    search_query = c_search.text_input("🔍 Search", placeholder="Name / Phone", key="search_query_persistent")
    status_filter = c_filter.multiselect("Filter", df['Status'].unique() if 'Status' in df.columns else [], key="status_filter_persistent")

    if st.session_state['role'] == "Telecaller":
        c_match = [c for c in df.columns if "Assigned" in c]
        if c_match:
            df = df[(df[c_match[0]] == st.session_state['username']) | 
                    (df[c_match[0]] == st.session_state['name']) |
                    (df[c_match[0]] == "TC1")]

    if search_query: df = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]
    if status_filter: df = df[df['Status'].isin(status_filter)]

    today = date.today()
    def get_priority(row):
        status = row.get('Status', '')
        f_date_str = str(row.get('Next Followup', '')).strip()
        if "Naya" in status: return 0
        if f_date_str and len(f_date_str) > 5:
            try:
                if datetime.strptime(f_date_str, "%Y-%m-%d").date() <= today: return 1
            except: pass
        return 2

    if not df.empty:
        f_col = next((c for c in df.columns if "Follow" in c), None)
        if f_col: df['Next Followup'] = df[f_col]
        df['Priority'] = df.apply(get_priority, axis=1)
        df = df.sort_values(by='Priority', ascending=True)

    if df.empty: st.info("📭 No leads found."); return

    st.caption(f"⚡ Live: {len(df)} Leads")
    # STATUS LIST (Matches your Sheet)
    status_opts = ["Naya Lead", "Call Uthaya Nahi / Busy", "Baat Hui - Interested", "Site Visit Scheduled", "Visit Done - Soch Raha Hai", "Faltu / Agent / Spam", "Not Interested (Mehenga Hai)", "Sold (Plot Bik Gaya)"]
    all_telecallers = users_df['Username'].tolist()

    def get_pipeline_action(status):
        if "Naya" in status: return ("⚡ ACTION: Abhi Call Karein", "blue")
        if "Busy" in status: return ("⏰ ACTION: 4 Ghante baad try karein", "orange")
        if "Interested" in status: return ("💬 ACTION: WhatsApp Brochure bhejein", "green")
        if "Scheduled" in status: return ("📍 ACTION: Visit Confirm Karein", "green")
        if "Visit Done" in status: return ("🤝 ACTION: Closing ke liye push karein", "blue")
        if "Faltu" in status: return ("🗑️ ACTION: Ignore", "red")
        if "Sold" in status: return ("🎉 ACTION: Party!", "green")
        return ("❓ ACTION: Update Status", "grey")

    for i, row in df.iterrows():
        name = row.get('Client Name', 'Unknown')
        status = row.get('Status', 'Naya Lead')
        phone = str(row.get('Phone', '')).replace(',', '').replace('.', '')
        assigned_to = row.get('Assigned', '-')
        
        icon = "⚪"
        if "Sold" in status: icon = "🟢"
        elif "Faltu" in status: icon = "🔴"
        elif "Visit" in status: icon = "🚕"
        elif "Naya" in status: icon = "⚡"
        
        alert = "🔔 CALL DUE | " if row.get('Priority') == 1 else ""
        action_text, action_color = get_pipeline_action(status)

        with st.expander(f"{icon} {alert}{name}"):
            if action_color == "blue": st.info(action_text)
            elif action_color == "green": st.success(action_text)
            elif action_color == "orange": st.warning(action_text)
            elif action_color == "red": st.error(action_text)
            else: st.info(action_text)
            
            # --- BIG BUTTONS ---
            b1, b2 = st.columns(2)
            with b1: st.markdown(big_call_btn(phone), unsafe_allow_html=True)
            with b2: st.markdown(big_wa_btn(phone, name), unsafe_allow_html=True)
            st.write("") 
            st.markdown(f"**📞 {phone}** | 📌 {row.get('Source', '-')}")
            if st.session_state['role'] == "Manager": st.caption(f"Assigned: {assigned_to}")

            with st.form(f"u_{i}"):
                # UX UPGRADE: Use Radio instead of Selectbox for easier tapping
                st.write("📝 **Change Status:**")
                ns = st.selectbox("Select Status", status_opts, key=f"s_{i}", index=status_opts.index(status) if status in status_opts else 0, label_visibility="collapsed")
                
                c_u1, c_u2 = st.columns(2)
                note = c_u1.text_input("Note", key=f"n_{i}", placeholder="Client said...")
                
                # UX UPGRADE: Compact Date Buttons
                c_u2.write("📅 Follow-up:")
                date_option = c_u2.radio("Follow-up", ["None", "Tom", "3 Days", "1 Wk"], horizontal=True, key=f"radio_{i}", label_visibility="collapsed")
                
                final_date = None
                if date_option == "Tom": final_date = today + timedelta(days=1)
                elif date_option == "3 Days": final_date = today + timedelta(days=3)
                elif date_option == "1 Wk": final_date = today + timedelta(days=7)
                
                new_assign = None
                if st.session_state['role'] == "Manager":
                    new_assign = st.selectbox("Re-Assign:", all_telecallers, index=all_telecallers.index(assigned_to) if assigned_to in all_telecallers else 0, key=f"a_{i}")

                # MASSIVE UPDATE BUTTON
                st.write("")
                if st.form_submit_button("✅ UPDATE LEAD STATUS", type="primary", use_container_width=True):
                    try:
                        h = leads_sheet.row_values(1)
                        # Dynamic Column Finder
                        try: s_idx = h.index("Status")+1
                        except: s_idx = 8
                        try: n_idx = h.index("Notes")+1 
                        except: n_idx = 12
                        try: a_idx = h.index("Assigned")+1 
                        except: a_idx = 7
                        try: t_idx = h.index("Last Call")+1 
                        except: t_idx = 10
                        
                        f_idx = 15
                        for idx, col_name in enumerate(h):
                            if "Follow" in col_name: f_idx = idx + 1; break
                        
                        succ, msg = robust_update(leads_sheet, phone, s_idx, ns)
                        if succ:
                            if note: robust_update(leads_sheet, phone, n_idx, note)
                            if final_date: robust_update(leads_sheet, phone, f_idx, str(final_date))
                            robust_update(leads_sheet, phone, t_idx, datetime.now().strftime("%Y-%m-%d %H:%M"))
                            if new_assign and new_assign != assigned_to:
                                robust_update(leads_sheet, phone, a_idx, new_assign)
                            set_feedback(f"✅ Updated {name}")
                            st.rerun()
                        else: st.error(msg)
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
                    if phone in all_phones: st.error(f"⚠️ Phone {phone} exists!"); return
                except: pass
                
                ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                new_id = generate_lead_id()
                row_data = [new_id, ts, name, phone, src, ag, assign, "Naya Lead", "", ts, "", "", "", "", ""] 
                leads_sheet.append_row(row_data)
                set_feedback(f"✅ Saved {name}")
                st.rerun()

def show_master_insights():
    st.header("📊 Analytics")
    try: df = pd.DataFrame(leads_sheet.get_all_records())
    except: 
        st.error("Could not load data.")
        return
    
    if df.empty: st.info("No data"); return

    # --- FIX: NORMALIZE HEADERS (Strip spaces) ---
    df.columns = df.columns.str.strip()

    st.subheader("1️⃣ Business Pulse")
    tot = len(df); sold = len(df[df['Status'].str.contains("Sold", na=False)])
    junk = len(df[df['Status'].str.contains("Faltu", na=False)])
    m1,m2,m3 = st.columns(3)
    m1.metric("Total", tot); m2.metric("Sold", sold); m3.metric("Junk", junk)
    
    st.subheader("2️⃣ Team Activity")
    
    # Check for 'Assigned' OR 'Assigned To'
    assign_col = 'Assigned' if 'Assigned' in df.columns else 'Assigned To'
    
    if assign_col in df.columns:
        stats = []
        for user, user_df in df.groupby(assign_col):
            pending = len(user_df[user_df['Status'] == 'Naya Lead'])
            working = len(user_df[user_df['Status'].str.contains("Busy|Interested|Visit", na=False)])
            sold_count = len(user_df[user_df['Status'].str.contains("Sold", na=False)])
            
            last_active = "-"
            # Check for 'Last Call'
            lc_col = 'Last Call' if 'Last Call' in df.columns else None
            if lc_col:
                valid_dates = [str(d) for d in user_df[lc_col] if str(d).strip() != ""]
                if valid_dates: last_active = max(valid_dates)
            
            stats.append({
                "User": user,
                "Total": len(user_df),
                "⚠️ Pending": pending,
                "🔥 Active": working,
                "🎉 Sold": sold_count,
                "🕒 Last Active": last_active
            })
        
        if stats:
            st.dataframe(pd.DataFrame(stats), use_container_width=True, hide_index=True)
        else:
            st.info("No activity yet.")
    else:
        st.error(f"Column '{assign_col}' not found. Headers detected: {list(df.columns)}")

def show_admin(users_df):
    st.header("⚙️ Admin")
    show_feedback()

    c1, c2 = st.columns([1,2])
    with c1:
        st.subheader("Create User")
        with st.form("nu", clear_on_submit=True):
            u = st.text_input("User"); p = st.text_input("Pass", type="password")
            n = st.text_input("Name"); r = st.selectbox("Role", ["Telecaller", "Sales Specialist", "Manager"])
            if st.form_submit_button("Create"):
                if u in users_df['Username'].values: st.error("Exists")
                else: 
                    users_sheet.append_row([u, hash_pass(p), r, n])
                    set_feedback(f"✅ Created {u}"); st.rerun()
        
        st.divider()
        st.subheader("📥 Bulk Upload (Auto-Distribute)")
        st.caption("Upload CSV. Leads will be distributed among selected agents.")
        
        telecaller_list = users_df[users_df['Role'].isin(['Telecaller', 'Sales Specialist', 'Manager'])]['Username'].tolist()
        selected_agents = st.multiselect("Assign Leads To:", telecaller_list, default=telecaller_list)
        
        uploaded_file = st.file_uploader("Choose CSV File", type=['csv'])
        
        if uploaded_file is not None and st.button("Start Upload"):
            if not selected_agents:
                st.error("⚠️ Please select at least one agent.")
            else:
                try:
                    try: df_up = pd.read_csv(uploaded_file, encoding='utf-8')
                    except: 
                        try: uploaded_file.seek(0); df_up = pd.read_csv(uploaded_file, encoding='utf-16', sep='\t')
                        except: uploaded_file.seek(0); df_up = pd.read_csv(uploaded_file, encoding='ISO-8859-1')
                    
                    cols = [c.lower() for c in df_up.columns]
                    name_idx = -1
                    for i, c in enumerate(cols):
                        if "full_name" in c or "fullname" in c: name_idx = i; break
                    if name_idx == -1:
                        for i, c in enumerate(cols):
                            if "name" in c and "ad" not in c and "form" not in c and "campaign" not in c: name_idx = i; break
                    if name_idx == -1: name_idx = next((i for i, c in enumerate(cols) if "name" in c), 0)

                    phone_idx = next((i for i, c in enumerate(cols) if "phone" in c or "mobile" in c or "p:" in c), 1)
                    
                    name_col = df_up.columns[name_idx]
                    phone_col = df_up.columns[phone_idx]
                    
                    all_phones = set(leads_sheet.col_values(4))
                    rows_to_add = []
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    agent_cycle = itertools.cycle(selected_agents)
                    
                    for idx, row in df_up.iterrows():
                        p_raw = str(row[phone_col])
                        p_clean = re.sub(r'\D', '', p_raw)
                        
                        if len(p_clean) >= 10 and p_clean not in all_phones:
                            new_id = generate_lead_id()
                            assigned_person = next(agent_cycle)
                            new_row = [new_id, ts, row[name_col], p_clean, "Meta Ads", "", assigned_person, "Naya Lead", "", ts, "", "", "", "", ""]
                            rows_to_add.append(new_row)
                            all_phones.add(p_clean)
                            time.sleep(0.01)
                    
                    if rows_to_add:
                        leads_sheet.append_rows(rows_to_add)
                        set_feedback(f"✅ Added {len(rows_to_add)} leads! Distributed to {len(selected_agents)} agents.")
                    else:
                        set_feedback("⚠️ No new leads added (duplicates).", "warning")
                    
                    time.sleep(1)
                    st.rerun()
                except Exception as e: st.error(f"Processing Error: {e}")

    with c2:
        st.subheader("Team List")
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
