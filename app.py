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

# --- CUSTOM CSS (MOBILE APP STYLE) ---
custom_css = """
    <style>
        header {visibility: hidden;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stAppDeployButton {display: none;}
        
        .block-container { padding-top: 0.5rem !important; }

        /* --- CARD BUTTON STYLING --- */
        .stButton button {
            width: 100%;
            text-align: left !important;
            padding: 14px 18px !important;
            border-radius: 12px !important;
            background-color: #1E1E24; /* Darker, premium card color */
            border: 1px solid #333;
            transition: all 0.2s ease-in-out;
            height: auto !important;
            white-space: pre-wrap !important; /* Allow 2 lines */
            display: block;
            margin-bottom: 4px;
        }
        
        .stButton button:active {
            background-color: #000;
            border-color: #ff4b4b;
            transform: scale(0.98);
        }
        
        /* Make the Name text inside button larger */
        .stButton button p {
            font-size: 16px;
            margin: 0;
            line-height: 1.5;
        }

        /* --- POPUP / DIALOG STYLING --- */
        div[data-testid="stDialog"] {
            border-radius: 16px;
            padding-bottom: 20px;
        }

        /* --- ACTION BUTTONS IN POPUP --- */
        .big-btn {
            display: block; width: 100%; padding: 14px; text-align: center;
            border-radius: 10px; text-decoration: none; font-weight: 600;
            font-size: 16px; margin-bottom: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        }
        .call-btn { background-color: #28a745; color: white !important; }
        .wa-btn { background-color: #25D366; color: white !important; }
        
        .note-history {
            font-size: 13px; color: #aaa; background: #121212;
            padding: 12px; border-radius: 8px; max-height: 150px;
            overflow-y: auto; margin-bottom: 15px; border-left: 4px solid #555;
            line-height: 1.5;
        }
        
        /* HIDE DEFAULT BUTTON BORDERS */
        button:focus { outline: none !important; box-shadow: none !important; }
        
        /* TABS */
        .stTabs [data-baseweb="tab-list"] { gap: 8px; }
        .stTabs [data-baseweb="tab-list"] button {
            border-radius: 20px;
            padding: 4px 12px;
            font-size: 14px;
        }
    </style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- TIMEZONE ---
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

def generate_lead_id(prefix="L"):
    ts = str(int(time.time()))[-6:] 
    rand = str(random.randint(10, 99))
    return f"{prefix}-{ts}{rand}"

# --- LOGIN ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

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

# --- APP HEADER ---
c_top_1, c_top_2 = st.columns([3, 1])
with c_top_1: st.markdown(f"### 🏡 TerraTip CRM\n👤 **{st.session_state['name']}** ({st.session_state['role']})")
with c_top_2:
    if st.button("🚪 Logout", key="logout_main", use_container_width=True):
        st.session_state['logged_in'] = False; st.query_params.clear(); st.rerun()
st.divider()

def big_call_btn(num): return f"""<a href="tel:{num}" class="big-btn call-btn">📞 CALL NOW</a>"""
def big_wa_btn(num, name): return f"""<a href="https://wa.me/91{num}?text=Namaste {name}" class="big-btn wa-btn" target="_blank">💬 WHATSAPP</a>"""

# --- ICON HELPER ---
def get_status_icon(status):
    s = str(status).lower().strip()
    if "naya" in s or "new" in s: return "🆕"
    if "ring" in s: return "📞" # Ringing
    if "busy" in s or "no answer" in s: return "🚫" # Busy
    if "later" in s: return "⏰" # Call Later
    if "interest" in s and "not" not in s: return "🔥" # Interested
    if "visit scheduled" in s: return "🗓️" # Visit Scheduled
    if "visit done" in s or "negotiat" in s: return "🤝" # Negotiation
    if "closed" in s or "booked" in s: return "✅" # Sold
    if "price" in s or "location" in s: return "📉" # Recycle
    if "junk" in s or "agent" in s: return "🗑️" # Junk
    return "⚪"

# --- LEAD MODAL ---
@st.dialog("📋 Lead Details")
def open_lead_modal(row_dict, users_df):
    phone = str(row_dict.get('Phone', '')).replace(',', '').replace('.', '')
    name = row_dict.get('Client Name', 'Unknown')
    status = row_dict.get('Status', 'Naya Lead')
    notes = row_dict.get('Notes', '')
    assigned_to = row_dict.get('Assign', '-')
    
    # Action Buttons
    b1, b2 = st.columns(2)
    with b1: st.markdown(big_call_btn(phone), unsafe_allow_html=True)
    with b2: st.markdown(big_wa_btn(phone, name), unsafe_allow_html=True)
    
    st.divider()
    
    # Key Info
    st.caption(f"👤 **{name}** | 📞 {phone}")
    st.caption(f"👮 Assigned: {assigned_to}")
    
    # Status Update
    status_opts = ["Naya Lead", "Ringing / Busy / No Answer", "Asked to Call Later", "Interested (Send Details)", "Site Visit Scheduled", "Visit Done (Negotiation)", "Sale Closed / Booked", "Not Interested / Price / Location", "Junk / Invalid / Agent"]
    
    def get_index(val, opts):
        val = str(val).lower().strip()
        for i, x in enumerate(opts):
            if x.lower() == val: return i
        return 0

    new_status = st.selectbox("Update Status", status_opts, index=get_index(status, status_opts))
    
    # History
    if len(str(notes)) > 2:
        st.markdown(f"**📝 History:**")
        st.markdown(f"<div class='note-history'>{notes}</div>", unsafe_allow_html=True)
    
    new_note = st.text_input("➕ Add Note", placeholder="Type update here...")
    
    # Follow Up
    st.write("📅 **Next Follow-up:**")
    today = get_ist_date()
    col_d1, col_d2 = st.columns([2, 1])
    date_opt = col_d1.radio("Quick Pick", ["None", "Tomorrow", "3 Days", "Custom"], horizontal=True, label_visibility="collapsed")
    
    final_date = None
    if date_opt == "Custom":
        final_date = st.date_input("Select Date", min_value=today)
    elif date_opt == "Tomorrow":
        final_date = today + timedelta(days=1)
    elif date_opt == "3 Days":
        final_date = today + timedelta(days=3)
        
    # Re-Assign
    new_assign = None
    if st.session_state['role'] == "Manager":
        all_telecallers = users_df['Username'].tolist()
        try: u_idx = all_telecallers.index(assigned_to)
        except: u_idx = 0
        new_assign = st.selectbox("Re-Assign To", all_telecallers, index=u_idx)

    # Save
    if st.button("✅ SAVE & CLOSE", type="primary", use_container_width=True):
        try:
            cell = leads_sheet.find(phone)
            if not cell: st.error("❌ Lead not found!")
            else:
                r = cell.row
                h = leads_sheet.row_values(1)
                
                def get_col(n):
                    try: return next(i for i,v in enumerate(h) if n.lower() in v.lower()) + 1
                    except: return None
                
                updates = []
                updates.append({'range': gspread.utils.rowcol_to_a1(r, get_col("Status") or 8), 'values': [[new_status]]})
                
                if new_note:
                    ts_str = datetime.now(IST).strftime("%d-%b")
                    full_note = f"[{ts_str}] {new_note}\n{notes}"
                    updates.append({'range': gspread.utils.rowcol_to_a1(r, get_col("Notes") or 12), 'values': [[full_note]]})
                
                if final_date:
                    updates.append({'range': gspread.utils.rowcol_to_a1(r, get_col("Follow") or 15), 'values': [[str(final_date)]]})
                
                updates.append({'range': gspread.utils.rowcol_to_a1(r, get_col("Last Call") or 10), 'values': [[get_ist_time()]]})
                
                c_idx = get_col("Count")
                if c_idx:
                    curr = leads_sheet.cell(r, c_idx).value
                    val = int(curr) + 1 if curr and curr.isdigit() else 1
                    updates.append({'range': gspread.utils.rowcol_to_a1(r, c_idx), 'values': [[val]]})
                
                if new_assign and new_assign != assigned_to:
                    updates.append({'range': gspread.utils.rowcol_to_a1(r, get_col("Assign") or 7), 'values': [[new_assign]]})

                leads_sheet.batch_update(updates)
                st.success("Saved!")
                time.sleep(0.5)
                st.rerun()
                
        except Exception as e:
            st.error(f"Error: {e}")

# --- REUSABLE LEAD RENDERER ---
def render_leads(df, users_df, label_prefix=""):
    if df.empty:
        st.info("✅ No leads in this section.")
        return

    for i, row in df.iterrows():
        phone = str(row.get('Phone', '')).replace(',', '').replace('.', '')
        name = str(row.get('Client Name', 'Unknown'))
        raw_status = str(row.get('Status', ''))
        
        # 1. SMART STATUS (Shorten Text)
        display_status = raw_status
        if "Not Interested" in raw_status: display_status = "Not Interested"
        elif "Ringing" in raw_status: display_status = "Ringing"
        elif "Visit Done" in raw_status: display_status = "Visit Done"
        
        # 2. DATE LOGIC
        f_col = next((c for c in df.columns if "Follow" in c), None)
        f_val = str(row.get(f_col, '')).strip()
        display_date = ""
        if len(f_val) > 5:
            try:
                d = datetime.strptime(f_val, "%Y-%m-%d").date()
                if d == datetime.now(IST).date(): display_date = "Today"
                else: display_date = d.strftime('%d %b')
            except: pass
            
        icon = get_status_icon(raw_status)
        short_name = name[:22] + ".." if len(name) > 22 else name
        
        # 3. CARD LABEL (2 Lines: Name \n Icon Status ... Date)
        # Using a distinct Separator '•' for clean alignment without spacing hacks
        if display_date:
            label = f"**{short_name}**\n{icon} {display_status}   •   📅 {display_date}"
        else:
            label = f"**{short_name}**\n{icon} {display_status}"
        
        if st.button(label, key=f"btn_{label_prefix}_{phone}", use_container_width=True):
            open_lead_modal(row.to_dict(), users_df)

# --- LIVE FEED ---
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

    if search_q:
        df_search = df[df.astype(str).apply(lambda x: x.str.contains(search_q, case=False)).any(axis=1)]
        st.info(f"🔍 Found {len(df_search)} results")
        render_leads(df_search, users_df, "search")
        return

    today = get_ist_date()
    
    def parse_f_date(val):
        if not val or len(str(val)) < 5: return None
        try: return datetime.strptime(str(val).strip(), "%Y-%m-%d").date()
        except: return None

    f_col_name = next((c for c in df.columns if "Follow" in c), None)
    df['ParsedDate'] = df[f_col_name].apply(parse_f_date) if f_col_name else None
    
    # MASKS
    dead_mask = df['Status'].str.contains("Closed|Booked|Junk|Invalid|Agent", case=False, na=False)
    recycle_mask = df['Status'].str.contains("Price|Location|Not Interest", case=False, na=False)
    date_action_mask = (df['ParsedDate'].notna()) & (df['ParsedDate'] <= today)
    future_mask = (df['ParsedDate'].notna()) & (df['ParsedDate'] > today)
    new_lead_mask = df['Status'].str.contains("Naya|New", case=False, na=False)
    
    # BUCKET 1: ACTION
    action_df = df[ (date_action_mask | new_lead_mask) & (~dead_mask) ].copy()
    def get_sort_priority(row):
        if pd.notna(row['ParsedDate']):
            if row['ParsedDate'] < today: return 0 
            return 1 
        return 2 
    if not action_df.empty:
        action_df['Priority'] = action_df.apply(get_sort_priority, axis=1)
        action_df = action_df.sort_values(by=['Priority'])

    # BUCKET 2: FUTURE
    future_df = df[ future_mask & (~dead_mask) ].copy()
    if not future_df.empty: future_df = future_df.sort_values(by='ParsedDate')

    # BUCKET 3: RECYCLE
    recycle_df = df[ recycle_mask & (df['ParsedDate'].isna()) & (~dead_mask) & (~new_lead_mask) ].copy()

    # BUCKET 4: HISTORY
    history_mask = dead_mask | ( (~date_action_mask) & (~new_lead_mask) & (~future_mask) & (~recycle_mask) )
    history_df = df[history_mask].copy()

    tab1, tab2, tab3, tab4 = st.tabs([
        f"🔥 Action ({len(action_df)})", 
        f"📅 Future ({len(future_df)})", 
        f"♻️ Recycle ({len(recycle_df)})", 
        f"❌ Closed ({len(history_df)})"
    ])

    with tab1: render_leads(action_df, users_df, "action")
    with tab2: render_leads(future_df, users_df, "future")
    with tab3: render_leads(recycle_df, users_df, "recycle")
    with tab4: render_leads(history_df, users_df, "history")

def show_add_lead_form(users_df):
    with st.expander("➕ Naya Lead Jodein", expanded=False):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name"); phone = c2.text_input("Phone")
        c3, c4 = st.columns(2)
        src = c3.selectbox("Source", ["Meta Ads", "Canopy", "Agent", "Others"])
        ag = c4.text_input("Agent Name") if src == "Agent" else ""
        extra_notes = st.text_area("Notes")
        
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
                    if clean_new in clean_existing: st.error(f"⚠️ Duplicate! {phone} already exists.")
                    else:
                        ts = get_ist_time(); new_id = generate_lead_id()
                        row_data = [new_id, ts, name, phone, src, ag, assign, "Naya Lead", "", ts, "", extra_notes, "", "", ""] 
                        leads_sheet.append_row(row_data)
                        set_feedback(f"✅ Saved {name}"); st.rerun()
                except Exception as e: st.error(f"Err: {e}")

def show_master_insights():
    st.header("📊 Analytics")
    try: df = pd.DataFrame(leads_sheet.get_all_records())
    except: st.error("Could not load data."); return
    if df.empty: st.info("No data"); return
    df.columns = df.columns.astype(str).str.strip()
    st.subheader("1️⃣ Business Pulse")
    tot = len(df); sold = len(df[df['Status'].str.contains("Closed", na=False)])
    junk = len(df[df['Status'].str.contains("Junk|Not Interest", na=False)])
    m1,m2,m3 = st.columns(3); m1.metric("Total", tot); m2.metric("Sold", sold); m3.metric("Junk", junk)

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
                else: users_sheet.append_row([u, hash_pass(p), r, n]); set_feedback(f"✅ Created {u}"); st.rerun()
        
        st.divider()
        st.subheader("📥 Bulk Upload (Meta CSV)")
        telecaller_list = users_df[users_df['Role'].isin(['Telecaller', 'Sales Specialist', 'Manager'])]['Username'].tolist()
        selected_agents = st.multiselect("Assign Leads To:", telecaller_list, default=telecaller_list)
        uploaded_file = st.file_uploader("Choose CSV File", type=['csv'])
        if uploaded_file is not None and st.button("Start Upload"):
            if not selected_agents: st.error("⚠️ Please select at least one agent.")
            else:
                try:
                    try: df_up = pd.read_csv(uploaded_file, encoding='utf-8')
                    except: 
                        try: uploaded_file.seek(0); df_up = pd.read_csv(uploaded_file, encoding='utf-16', sep='\t')
                        except: uploaded_file.seek(0); df_up = pd.read_csv(uploaded_file, encoding='ISO-8859-1')
                    
                    cols = [c.lower() for c in df_up.columns]
                    name_idx = next((i for i, c in enumerate(cols) if any(x in c for x in ["full_name", "fullname", "name"])), -1)
                    phone_idx = next((i for i, c in enumerate(cols) if any(x in c for x in ["phone", "mobile", "p:"])), -1)
                    
                    if name_idx == -1 or phone_idx == -1:
                        st.error("Could not find 'Name' or 'Phone' columns automatically.")
                    else:
                        name_col = df_up.columns[name_idx]
                        phone_col = df_up.columns[phone_idx]
                        
                        ignore_list = [
                            name_col.lower(), phone_col.lower(),
                            "id", "created_time", "ad_id", "ad_name", "adset_id", "adset_name",
                            "campaign_id", "campaign_name", "form_id", "form_name", 
                            "platform", "is_organic", "date", "start_date", "end_date"
                        ]
                        
                        extra_cols = [c for c in df_up.columns if c.lower() not in ignore_list]
                        raw_existing = leads_sheet.col_values(4); existing_phones_set = {re.sub(r'\D', '', str(p))[-10:] for p in raw_existing}
                        rows_to_add = []; ts = get_ist_time(); agent_cycle = itertools.cycle(selected_agents)
                        
                        for idx, row in df_up.iterrows():
                            p_raw = str(row[phone_col]); p_clean = re.sub(r'\D', '', p_raw)
                            if len(p_clean) >= 10:
                                p_last_10 = p_clean[-10:]
                                if p_last_10 not in existing_phones_set:
                                    notes_data = []
                                    for ec in extra_cols:
                                        val = str(row[ec]).strip()
                                        if val and val.lower() != "nan":
                                            notes_data.append(f"{ec}: {val}")
                                    final_note = " | ".join(notes_data)
                                    
                                    new_id = generate_lead_id(); assigned_person = next(agent_cycle)
                                    new_row = [new_id, ts, row[name_col], p_clean, "Meta Ads", "", assigned_person, "Naya Lead", "", ts, "", final_note, "", "", ""]
                                    rows_to_add.append(new_row); existing_phones_set.add(p_last_10)
                        
                        if rows_to_add: leads_sheet.append_rows(rows_to_add); set_feedback(f"✅ Added {len(rows_to_add)} leads!"); time.sleep(1); st.rerun()
                except Exception as e: st.error(f"Processing Error: {e}")

    with c2:
        st.subheader("Team List")
        st.dataframe(users_df[['Name','Username','Role']], hide_index=True)
        opts = [x for x in users_df['Username'].unique() if x != st.session_state['username']]
        if opts:
            dt = st.selectbox("Delete", opts)
            if st.button("❌ Delete"): users_sheet.delete_rows(users_sheet.find(dt).row); set_feedback(f"Deleted {dt}"); st.rerun()

def show_dashboard(users_df):
    show_feedback(); show_add_lead_form(users_df); st.divider()
    c_search, c_filter = st.columns([2, 1])
    search_q = c_search.text_input("🔍 Search", placeholder="Name / Phone", key="search_q")
    show_live_leads_list(users_df, search_q, None)

# --- EXECUTION ---
if st.session_state['role'] == "Manager":
    t1, t2, t3 = st.tabs(["🏠 CRM", "📊 Insights", "⚙️ Admin"])
    with t1: show_dashboard(users_df)
    with t2: show_master_insights()
    with t3: show_admin(users_df)
else:
    show_dashboard(users_df)
