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

# --- CUSTOM CSS ---
custom_css = """
    <style>
        header {visibility: hidden;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stAppDeployButton {display: none;}
        
        .block-container { padding-top: 1rem !important; }

        /* PROFESSIONAL HEADER STYLE */
        .streamlit-expanderHeader {
            font-family: 'Roboto', sans-serif;
            font-size: 16px !important;
            font-weight: 600 !important;
            color: #ffffff !important;
            background-color: #262730 !important;
            border: 1px solid #444 !important;
            border-radius: 8px !important;
            padding: 15px 20px !important;
            margin-bottom: 8px !important;
        }
        
        [data-testid="stExpander"] { border: None !important; box-shadow: None !important; }
        
        /* ACTION BUTTONS */
        .big-btn {
            display: block;
            width: 100%;
            padding: 12px; 
            text-align: center;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 700;
            font-size: 15px;
            letter-spacing: 0.5px;
            margin-bottom: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        .call-btn { background-color: #28a745; color: white !important; }
        .wa-btn { background-color: #25D366; color: white !important; }
        
        /* COMPACT NOTE HISTORY */
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
        
        /* FORM LABELS */
        div[role="radiogroup"] > label {
            padding: 5px 10px;
            background: #1e1e1e;
            border: 1px solid #333;
            border-radius: 4px;
            font-size: 14px;
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

def robust_update(sheet, phone_number, col_index, value):
    try:
        cell = sheet.find(phone_number)
        if cell:
            sheet.update_cell(cell.row, col_index, value)
            return True, "Updated"
        return False, "Lead not found"
    except Exception as e: return False, str(e)

def generate_lead_id(prefix="L"):
    ts = str(int(time.time()))[-6:] 
    rand = str(random.randint(10, 99))
    return f"{prefix}-{ts}{rand}"

# --- HELPER: TIME AGO ---
def get_time_ago(last_call_str):
    if not last_call_str or len(str(last_call_str)) < 5: return "New"
    try:
        last_dt = datetime.strptime(str(last_call_str).strip(), "%Y-%m-%d %H:%M")
    except:
        try: last_dt = datetime.strptime(str(last_call_str).strip(), "%Y-%m-%d")
        except: return "-"
    
    if last_dt.tzinfo is None: last_dt = IST.localize(last_dt)
    now = datetime.now(IST)
    diff = now - last_dt
    
    if diff.days == 0:
        hrs = diff.seconds // 3600
        if hrs == 0: return "Just now"
        return f"{hrs}h ago"
    elif diff.days == 1: return "Yesterday"
    else: return f"{diff.days}d ago"

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
        st.title("🔐 TerraTip CRM")
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

    today = get_ist_date()
    
    # --- CLEAN SORTING & HEADER LOGIC ---
    def get_lead_meta(row):
        status = str(row.get('Status', '')).strip()
        
        # Follow-Up Date Logic
        f_col = next((c for c in df.columns if "Follow" in c), None)
        f_val = str(row.get(f_col, '')).strip() if f_col else ""
        
        # Last Active Logic
        t_col = next((c for c in df.columns if "Last Call" in c), None)
        t_val = str(row.get(t_col, '')).strip() if t_col else ""
        ago = get_time_ago(t_val)
        
        # Determine Priority Score & Header Badge
        score = 4 # Default
        badge_icon = "⚪"
        badge_text = "PASSIVE"
        
        # 1. New Lead?
        if "naya" in status.lower() or "new" in status.lower():
            score = 0
            badge_icon = "⚡"
            badge_text = "NEW LEAD"
        # 2. Site Visit / Closing?
        elif "visit" in status.lower() or "schedule" in status.lower():
            score = 0
            badge_icon = "📍"
            badge_text = "VISIT" # Will append date below
        elif "negotiat" in status.lower():
            score = 0
            badge_icon = "💰"
            badge_text = "CLOSING"
        # 3. Check Dates
        elif f_val and len(f_val) > 5:
            try:
                f_date = datetime.strptime(f_val, "%Y-%m-%d").date()
                if f_date < today:
                    score = 1
                    badge_icon = "🔴"
                    badge_text = f"LATE ({f_date.strftime('%d-%b')})"
                elif f_date == today:
                    score = 2
                    badge_icon = "🟡"
                    badge_text = "TODAY"
                else:
                    score = 3
                    badge_icon = "🗓️"
                    badge_text = f"{f_date.strftime('%d-%b')}"
            except: pass
            
        # Override Badge Text if Visit and Date Known
        if "VISIT" in badge_text and f_val and len(f_val) > 5:
             try:
                f_date = datetime.strptime(f_val, "%Y-%m-%d").date()
                badge_text = f"VISIT: {f_date.strftime('%d-%b')}"
             except: pass

        return score, badge_icon, badge_text, ago, f_val

    if not df.empty:
        # Apply Logic
        df[['Score', 'Icon', 'Badge', 'Ago', 'FDate']] = df.apply(lambda row: pd.Series(get_lead_meta(row)), axis=1)
        # Sort
        df = df.sort_values(by=['Score'], ascending=True)

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
        # Fallback Keywords
        if "naya" in val: return 0
        if "ring" in val or "busy" in val: return 1
        if "later" in val: return 2
        if "interest" in val: return 3
        if "schedule" in val or "visit" in val: return 4
        if "done" in val: return 5
        if "close" in val or "sold" in val: return 6
        if "not" in val: return 7
        if "junk" in val: return 8
        return 0

    for i, row in df.iterrows():
        name = row.get('Client Name', 'Unknown')
        phone = str(row.get('Phone', '')).replace(',', '').replace('.', '')
        assigned_to = row.get(assign_col_name, '-') if assign_col_name else '-'
        
        # Header Construction
        header_text = f"{row['Icon']} {row['Badge']} | {name} | 🕒 {row['Ago']}"
        
        with st.expander(label=header_text, expanded=False):
            
            # --- ROW 1: ACTION BUTTONS ---
            b1, b2 = st.columns(2)
            with b1: st.markdown(big_call_btn(phone), unsafe_allow_html=True)
            with b2: st.markdown(big_wa_btn(phone, name), unsafe_allow_html=True)
            
            # --- ROW 2: STATUS & DETAILS ---
            c_det1, c_det2 = st.columns([2, 1])
            with c_det1:
                st.caption(f"**📞 {phone}** | Source: {row.get('Source', '-')}")
                st.caption(f"👤 Assigned: {assigned_to}")
            with c_det2:
                # Status Dropdown
                current_status = str(row.get('Status', 'Naya Lead'))
                ns = st.selectbox("Status", status_opts, key=f"s_{i}", index=get_smart_index(current_status))

            # --- ROW 3: HISTORY ---
            existing_notes = str(row.get('Notes', ''))
            if existing_notes and existing_notes != "nan" and len(existing_notes) > 2:
                st.markdown(f"<div class='note-history'>{existing_notes}</div>", unsafe_allow_html=True)
            
            # --- ROW 4: INPUTS ---
            c_in1, c_in2 = st.columns(2)
            new_note = c_in1.text_input("New Note", key=f"n_{i}", placeholder="Type detail...")
            
            # Smart Date Label
            d_label = "📅 Next Call"
            if "Visit" in ns: d_label = "📍 **Site Visit Date**"
            
            c_in2.write(d_label)
            d_opt = c_in2.radio("Select", ["None", "Tom", "3 Days", "Custom"], horizontal=True, key=f"r_{i}", label_visibility="collapsed")
            
            final_date = None
            if d_opt == "Custom": final_date = c_in2.date_input("Date", min_value=today, key=f"d_{i}", label_visibility="collapsed")
            elif d_opt == "Tom": final_date = today + timedelta(days=1)
            elif d_opt == "3 Days": final_date = today + timedelta(days=3)
            
            # Save Button
            st.write("")
            button_ph = st.empty()
            if button_ph.button("✅ SAVE CHANGES", key=f"btn_{i}", type="primary", use_container_width=True):
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
                        
                        if new_note:
                            n_idx = get_col("Notes") or 12
                            ts_str = datetime.now(IST).strftime("%d-%b")
                            full_note = f"[{ts_str}] {new_note}\n{existing_notes}"
                            updates.append({'range': gspread.utils.rowcol_to_a1(r, n_idx), 'values': [[full_note]]})
                        
                        f_idx = get_col("Follow") or 15
                        if final_date: 
                            updates.append({'range': gspread.utils.rowcol_to_a1(r, f_idx), 'values': [[str(final_date)]]})
                        
                        t_idx = get_col("Last Call") or 10
                        updates.append({'range': gspread.utils.rowcol_to_a1(r, t_idx), 'values': [[get_ist_time()]]})
                        
                        c_idx = get_col("Count")
                        if c_idx:
                            curr = leads_sheet.cell(r, c_idx).value
                            val = int(curr) + 1 if curr and curr.isdigit() else 1
                            updates.append({'range': gspread.utils.rowcol_to_a1(r, c_idx), 'values': [[val]]})

                        leads_sheet.batch_update(updates)
                        button_ph.success("✅ SAVED SUCCESSFULLY!")
                        time.sleep(0.7)
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
                "Total": len(user_df),
                "⚠️ Pending": pending,
                "🔥 Active": working,
                "🎉 Sold": sold_count,
                "🕒 Last Active": last_active
            })
        if stats: st.dataframe(pd.DataFrame(stats), use_container_width=True, hide_index=True)
        else: st.info("No activity yet.")
    else: st.error(f"⚠️ System Error: Could not find 'Assigned' column.")

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
                    
                    # STRICT DEDUPE
                    raw_existing = leads_sheet.col_values(4)
                    existing_phones_set = {re.sub(r'\D', '', str(p))[-10:] for p in raw_existing}
                    
                    rows_to_add = []
                    ts = get_ist_time()
                    
                    agent_cycle = itertools.cycle(selected_agents)
                    
                    for idx, row in df_up.iterrows():
                        p_raw = str(row[phone_col])
                        p_clean = re.sub(r'\D', '', p_raw)
                        
                        if len(p_clean) >= 10:
                            p_last_10 = p_clean[-10:]
                            if p_last_10 not in existing_phones_set:
                                new_id = generate_lead_id()
                                assigned_person = next(agent_cycle)
                                new_row = [new_id, ts, row[name_col], p_clean, "Meta Ads", "", assigned_person, "Naya Lead", "", ts, "", "", "", "", ""]
                                rows_to_add.append(new_row)
                                existing_phones_set.add(p_last_10)
                    
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
    
    c_search, c_filter = st.columns([2, 1])
    search_q = c_search.text_input("🔍 Search", placeholder="Name / Phone", key="search_q")
    
    try: 
        df_temp = pd.DataFrame(leads_sheet.get_all_records())
        status_opts = df_temp['Status'].unique() if 'Status' in df_temp.columns else []
    except: status_opts = []
    
    status_f = c_filter.multiselect("Filter", status_opts, key="status_f")
    
    show_live_leads_list(users_df, search_q, status_f)

if st.session_state['role'] == "Manager":
    t1, t2, t3 = st.tabs(["🏠 CRM", "📊 Insights", "⚙️ Admin"])
    with t1: show_dashboard(users_df)
    with t2: show_master_insights()
    with t3: show_admin(users_df)
else:
    show_dashboard(users_df)
