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

# --- CUSTOM CSS (VISIBILITY FIX) ---
custom_css = """
    <style>
        /* 1. AGGRESSIVE DARK MODE ENFORCEMENT */
        /* Force the whole app to be dark, ignoring system settings */
        .stApp {
            background-color: #0e1117 !important;
            color: #ffffff !important;
        }
        
        /* Force inputs (Search/Text) to be dark with white text */
        div[data-baseweb="input"] {
            background-color: #262730 !important;
            border-color: #444 !important;
        }
        input.st-ai {
            color: white !important;
        }
        
        /* 2. SIDEBAR BUTTON (THE FIX) */
        /* We make it a solid, visible floating button in the top left */
        [data-testid="stSidebarCollapsedControl"] {
            display: flex !important;
            visibility: visible !important;
            background-color: #262730 !important; /* Solid dark grey */
            color: #ffffff !important; /* Bright white icon */
            border: 2px solid #444 !important;
            border-radius: 12px !important;
            width: 45px !important;
            height: 45px !important;
            justify-content: center;
            align-items: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.5) !important;
            
            /* Pin it to the top-left, independent of the header */
            position: fixed !important;
            top: 15px !important;
            left: 15px !important;
            z-index: 1000001 !important;
        }
        
        /* Increase icon size inside the button */
        [data-testid="stSidebarCollapsedControl"] svg {
            width: 24px !important;
            height: 24px !important;
            fill: white !important;
        }

        /* 3. HEADER REMOVAL */
        /* Remove the top bar entirely so it doesn't block anything */
        header[data-testid="stHeader"] {
            display: none !important;
        }
        [data-testid="stToolbar"] {
            display: none !important;
        }

        /* 4. LAYOUT ADJUSTMENT */
        /* Push the main content down so the button doesn't overlap the search bar */
        .block-container { 
            padding-top: 5rem !important; 
        }

        /* 5. CARD STYLING (Standardized) */
        .stButton button {
            width: 100%;
            text-align: left !important;
            padding: 16px 18px !important;
            border-radius: 12px !important;
            background-color: #1a1a1d !important;
            border: 1px solid #333;
            margin-bottom: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        
        .stButton button p {
            font-family: 'Source Sans Pro', sans-serif;
            color: #ffffff !important;
            font-size: 15px;
            margin: 0;
            line-height: 1.5;
        }

        /* 6. UTILS */
        div[data-testid="stDialog"] { border-radius: 16px; background-color: #262730; }
        .big-btn { display: block; width: 100%; padding: 14px; text-align: center; border-radius: 10px; font-weight: bold; margin-bottom: 10px; text-decoration: none;}
        .call-btn { background-color: #28a745; color: white !important; }
        .wa-btn { background-color: #25D366; color: white !important; }
        .note-history { font-size: 13px; color: #ccc; background: #121212; padding: 12px; border-radius: 8px; max-height: 150px; overflow-y: auto; margin-bottom: 15px; border-left: 4px solid #555; }
        .stTabs [data-baseweb="tab-list"] button { border-radius: 20px; padding: 6px 12px; font-size: 13px; }
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

def big_call_btn(num): return f"""<a href="tel:{num}" class="big-btn call-btn">📞 CALL NOW</a>"""
def big_wa_btn(num, name): return f"""<a href="https://wa.me/91{num}?text=Namaste {name}" class="big-btn wa-btn" target="_blank">💬 WHATSAPP</a>"""

# --- PIPELINE STATUSES ---
PIPELINE_OPTS = [
    "Naya Lead", "Ringing / No Response", "Call Back Later", 
    "Interested / Send Details", "Follow-up / Thinking", 
    "Site Visit Scheduled", "Negotiation / Visit Done", 
    "Sale Closed", "Lost (Price / Location)", "Junk / Invalid / Broker"
]

def get_status_icon(status):
    s = str(status).lower().strip()
    if "naya" in s or "new" in s: return "🆕"
    if "ring" in s: return "📞"
    if "back later" in s: return "⏰"
    if "follow-up" in s or "thinking" in s: return "🤔"
    if "interest" in s: return "🔥"
    if "visit" in s: return "🗓️"
    if "negotiat" in s: return "🤝"
    if "closed" in s or "booked" in s: return "✅"
    if "lost" in s or "price" in s or "location" in s: return "📉"
    if "junk" in s or "invalid" in s: return "🗑️"
    return "⚪"

# --- LEAD MODAL ---
@st.dialog("📋 Lead Details")
def open_lead_modal(row_dict, users_df):
    phone = str(row_dict.get('Phone', '')).replace(',', '').replace('.', '')
    name = row_dict.get('Client Name', 'Unknown')
    status = row_dict.get('Status', 'Naya Lead')
    notes = row_dict.get('Notes', '')
    assigned_to = row_dict.get('Assign', '-')
    
    b1, b2 = st.columns(2)
    with b1: st.markdown(big_call_btn(phone), unsafe_allow_html=True)
    with b2: st.markdown(big_wa_btn(phone, name), unsafe_allow_html=True)
    
    st.divider()
    st.caption(f"👤 **{name}** | 📞 {phone}")
    st.caption(f"👮 Assigned: {assigned_to}")
    
    def get_index(val, opts):
        val = str(val).lower().strip()
        for i, x in enumerate(opts):
            if x.lower() == val: return i
        if "price" in val or "location" in val: return opts.index("Lost (Price / Location)")
        if "visit" in val: return opts.index("Site Visit Scheduled")
        if "busy" in val: return opts.index("Ringing / No Response")
        return 0

    new_status = st.selectbox("Update Status", PIPELINE_OPTS, index=get_index(status, PIPELINE_OPTS))
    
    if len(str(notes)) > 2:
        st.markdown(f"**📝 History:**")
        st.markdown(f"<div class='note-history'>{notes}</div>", unsafe_allow_html=True)
    
    new_note = st.text_input("➕ Add Note", placeholder="Type update here...")
    
    st.write("📅 **Next Follow-up:**")
    today = get_ist_date()
    col_d1, col_d2 = st.columns([2, 1])
    date_opt = col_d1.radio("Quick Pick", ["None", "Tomorrow", "3 Days", "Custom"], horizontal=True, label_visibility="collapsed")
    
    final_date = None
    if date_opt == "Custom": final_date = st.date_input("Select Date", min_value=today)
    elif date_opt == "Tomorrow": final_date = today + timedelta(days=1)
    elif date_opt == "3 Days": final_date = today + timedelta(days=3)
        
    new_assign = None
    if st.session_state['role'] == "Manager":
        all_telecallers = users_df['Username'].tolist()
        try: u_idx = all_telecallers.index(assigned_to)
        except: u_idx = 0
        new_assign = st.selectbox("Re-Assign To", all_telecallers, index=u_idx)

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
                time.sleep(0.5); st.rerun()
        except Exception as e: st.error(f"Error: {e}")

# --- LEAD RENDERER ---
def render_leads(df, users_df, label_prefix="", is_bulk=False):
    if df.empty:
        st.info("✅ No leads here.")
        return

    for i, row in df.iterrows():
        phone = str(row.get('Phone', '')).replace(',', '').replace('.', '')
        name = str(row.get('Client Name', 'Unknown'))
        raw_status = str(row.get('Status', ''))
        
        display_status = raw_status
        if "Lost" in raw_status: display_status = "Lost (Price/Loc)"
        elif "Ringing" in raw_status: display_status = "Ringing"
        elif "Negotiation" in raw_status: display_status = "Negotiation"
        elif "Follow-up" in raw_status: display_status = "Follow-up"
        
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
        short_name = name[:20] + ".." if len(name) > 20 else name
        
        if display_date:
            label = f"**{short_name}**\n{icon} {display_status}  •  📅 {display_date}"
        else:
            label = f"**{short_name}**\n{icon} {display_status}"
        
        if is_bulk:
            c_check, c_btn = st.columns([0.15, 0.85])
            with c_check: st.checkbox("", key=f"sel_{label_prefix}_{phone}")
            with c_btn:
                if st.button(label, key=f"btn_{label_prefix}_{phone}", use_container_width=True):
                    open_lead_modal(row.to_dict(), users_df)
        else:
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
        render_leads(df_search, users_df, "search", False)
        return

    today = get_ist_date()
    
    # --- BULK TOGGLE & SEARCH ROW ---
    c_search, c_toggle = st.columns([0.6, 0.4])
    with c_search:
        # Placeholder for visual alignment
        pass
    
    is_bulk = False
    if st.session_state['role'] == "Manager":
        with c_toggle:
            is_bulk = st.toggle("⚡ Bulk Mode")
    
    if is_bulk:
        st.warning("Select leads below to delete")
        if st.button("🗑️ DELETE SELECTED", type="primary"):
            selected_phones = [k.split("_")[-1] for k, v in st.session_state.items() if k.startswith("sel_") and v]
            if not selected_phones: st.error("No leads selected")
            else:
                try:
                    all_vals = leads_sheet.get_all_values()
                    rows_to_del = []
                    for i, row in enumerate(all_vals):
                        p_clean = str(row[3]).replace(',', '').replace('.', '')
                        if p_clean in selected_phones: rows_to_del.append(i+1)
                    rows_to_del.sort(reverse=True)
                    for r in rows_to_del: leads_sheet.delete_rows(r)
                    set_feedback(f"Deleted {len(rows_to_del)} leads"); time.sleep(1); st.rerun()
                except Exception as e: st.error(str(e))

    def parse_f_date(val):
        if not val or len(str(val)) < 5: return None
        try: return datetime.strptime(str(val).strip(), "%Y-%m-%d").date()
        except: return None

    f_col_name = next((c for c in df.columns if "Follow" in c), None)
    df['ParsedDate'] = df[f_col_name].apply(parse_f_date) if f_col_name else None
    
    dead_mask = df['Status'].str.contains("Closed|Booked|Junk|Invalid|Agent", case=False, na=False)
    recycle_mask = df['Status'].str.contains("Lost|Price|Location|Not Interest", case=False, na=False)
    date_action_mask = (df['ParsedDate'].notna()) & (df['ParsedDate'] <= today)
    future_mask = (df['ParsedDate'].notna()) & (df['ParsedDate'] > today)
    new_lead_mask = df['Status'].str.contains("Naya|New", case=False, na=False)
    
    action_df = df[ (date_action_mask | new_lead_mask) & (~dead_mask) & (~recycle_mask) ].copy()
    def get_sort_priority(row):
        if pd.notna(row['ParsedDate']):
            if row['ParsedDate'] < today: return 0 
            return 1 
        return 2 
    if not action_df.empty:
        action_df['Priority'] = action_df.apply(get_sort_priority, axis=1)
        action_df = action_df.sort_values(by=['Priority'])

    future_df = df[ future_mask & (~dead_mask) & (~recycle_mask) ].copy()
    if not future_df.empty: future_df = future_df.sort_values(by='ParsedDate')

    recycle_df = df[ recycle_mask & (~dead_mask) ].copy()
    history_df = df[dead_mask | ( (~date_action_mask) & (~new_lead_mask) & (~future_mask) & (~recycle_mask) )].copy()

    tab1, tab2, tab3, tab4 = st.tabs([
        f"🔥 Action ({len(action_df)})", 
        f"📅 Future ({len(future_df)})", 
        f"♻️ Recycle ({len(recycle_df)})", 
        f"❌ Closed ({len(history_df)})"
    ])

    with tab1: render_leads(action_df, users_df, "action", is_bulk)
    with tab2: render_leads(future_df, users_df, "future", is_bulk)
    with tab3: render_leads(recycle_df, users_df, "recycle", is_bulk)
    with tab4: render_leads(history_df, users_df, "history", is_bulk)

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

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f"### 👤 {st.session_state['name']}")
    st.caption(f"Role: {st.session_state['role']}")
    st.divider()
    page = st.radio("Navigate", ["🏠 CRM", "📊 Insights", "⚙️ Admin"])
    st.divider()
    
    if page == "🏠 CRM":
        st.markdown("### ➕ Add New Lead")
        with st.form("add_lead_sidebar", clear_on_submit=True):
            name = st.text_input("Name")
            phone = st.text_input("Phone")
            src = st.selectbox("Source", ["Meta Ads", "Canopy", "Agent", "Others"])
            notes = st.text_area("Notes")
            if st.form_submit_button("Save Lead", type="primary"):
                 try:
                    all_phones = leads_sheet.col_values(4)
                    clean_existing = {re.sub(r'\D', '', str(p))[-10:] for p in all_phones}
                    clean_new = re.sub(r'\D', '', phone)[-10:]
                    if clean_new in clean_existing: st.error(f"Duplicate!")
                    else:
                        ts = get_ist_time(); new_id = generate_lead_id()
                        assign = st.session_state['username']
                        row_data = [new_id, ts, name, phone, src, "", assign, "Naya Lead", "", ts, "", notes, "", "", ""] 
                        leads_sheet.append_row(row_data)
                        st.toast(f"✅ Saved {name}!")
                        time.sleep(1); st.rerun()
                 except Exception as e: st.error(f"Err: {e}")

    st.divider()
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state['logged_in'] = False; st.query_params.clear(); st.rerun()

# --- MAIN SCREEN ---
if page == "🏠 CRM":
    search_q = st.text_input("🔍 Search Leads", placeholder="Type Name or Phone...", label_visibility="collapsed")
    show_live_leads_list(users_df, search_q, None)

elif page == "📊 Insights":
    show_master_insights()

elif page == "⚙️ Admin":
    if st.session_state['role'] == "Manager":
        show_admin(users_df)
    else:
        st.error("⛔ Access Denied: Managers Only")
