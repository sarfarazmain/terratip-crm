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
        
        .block-container { padding-top: 0.5rem !important; }

        /* HEADER & EXPANDER STYLING */
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
        .streamlit-expanderHeader p { width: 100%; margin: 0; display: block; }
        .streamlit-expanderHeader strong {
            display: inline-block; min-width: 80px; text-align: center;
            background: #333; color: #fff; padding: 2px 6px;
            border-radius: 4px; font-weight: 700; font-size: 12px;
            margin-right: 10px; border: 1px solid #555; vertical-align: middle;
        }
        .streamlit-expanderHeader code {
            font-family: sans-serif; font-size: 11px; background: #444;
            color: #ccc; padding: 2px 5px; border-radius: 3px;
            margin-left: 6px; border: none; vertical-align: middle;
        }
        .streamlit-expanderHeader em {
            float: right; font-style: normal; font-size: 12px; color: #aaa;
            background: #1e1e1e; padding: 2px 6px; border-radius: 4px; margin-top: 2px;
        }

        /* BUTTONS */
        .big-btn {
            display: block; width: 100%; padding: 10px; text-align: center;
            border-radius: 6px; text-decoration: none; font-weight: 700;
            font-size: 14px; letter-spacing: 0.5px; margin-bottom: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        .call-btn { background-color: #28a745; color: white !important; }
        .wa-btn { background-color: #25D366; color: white !important; }
        
        .note-history {
            font-size: 12px; color: #bbb; background: #121212;
            padding: 10px; border-radius: 6px; max-height: 80px;
            overflow-y: auto; margin-bottom: 10px; border-left: 3px solid #555;
        }
        
        div[role="radiogroup"] > label {
            padding: 5px 10px; background: #1e1e1e;
            border: 1px solid #333; border-radius: 4px; font-size: 14px;
        }
        [data-testid="stCheckbox"] { margin-top: 12px; }
        
        /* TABS STYLING */
        .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
            font-size: 16px;
            font-weight: bold;
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
                                             'role':u_row.iloc[0]['Role'], 'name':u_row.iloc[0]['Name']})
                    st.query_params["u"] = u; st.query_params["k"] = hash_pass(p)
                    st.rerun()
                else: st.error("❌ Invalid")
    st.stop()

# --- APP LAYOUT ---
c_top_1, c_top_2 = st.columns([3, 1])
with c_top_1: st.markdown(f"### 🏡 TerraTip CRM\n👤 **{st.session_state['name']}** ({st.session_state['role']})")
with c_top_2:
    if st.button("🚪 Logout", key="logout_main", use_container_width=True):
        st.session_state['logged_in'] = False; st.query_params.clear(); st.rerun()
st.divider()

def big_call_btn(num): return f"""<a href="tel:{num}" class="big-btn call-btn">📞 CALL NOW</a>"""
def big_wa_btn(num, name): return f"""<a href="https://wa.me/91{num}?text=Namaste {name}" class="big-btn wa-btn" target="_blank">💬 WHATSAPP</a>"""

# --- REUSABLE LEAD RENDERER ---
def render_leads(df, users_df, label_prefix=""):
    """
    Renders a dataframe of leads with standard UI.
    """
    if df.empty:
        st.info("✅ No leads in this section.")
        return

    status_opts = ["Naya Lead", "Ringing / Busy / No Answer", "Asked to Call Later", "Interested (Send Details)", "Site Visit Scheduled", "Visit Done (Negotiation)", "Sale Closed / Booked", "Not Interested / Price / Location", "Junk / Invalid / Agent"]
    all_telecallers = users_df['Username'].tolist()
    today = get_ist_date()

    def get_smart_index(current_val):
        val = str(current_val).lower().strip()
        if val in [x.lower() for x in status_opts]:
            for i, x in enumerate(status_opts):
                if x.lower() == val: return i
        return 0

    def get_pipeline_action(status, f_date_str):
        if f_date_str and len(str(f_date_str)) > 5:
            try:
                f_date = datetime.strptime(f_date_str, "%Y-%m-%d").date()
                if f_date < today: return ("🔴 OVERDUE", "red")
                if f_date == today: return ("🟡 Call Today!", "orange")
                if f_date > today: return (f"📅 {f_date.strftime('%d-%b')}", "green")
            except: pass
        s = status.lower()
        if "naya" in s: return ("⚡ Call Now", "blue")
        if "ring" in s: return ("⏰ Retry 4h", "orange")
        if "visit" in s: return ("📍 Confirm", "green")
        return ("❓ Update", "grey")

    for i, row in df.iterrows():
        phone = str(row.get('Phone', '')).replace(',', '').replace('.', '')
        key_suffix = f"{label_prefix}_{phone}" 
        
        assign_col_name = next((c for c in df.columns if "assign" in c.lower()), None)
        assigned_to = row.get(assign_col_name, '-') if assign_col_name else '-'
        
        f_col_name = next((c for c in df.columns if "Follow" in c), None)
        f_val = row.get(f_col_name, '') if f_col_name else ''
        status = str(row.get('Status', 'Naya Lead')).strip()
        action_text, action_color = get_pipeline_action(status, str(f_val).strip())

        t_col = next((c for c in df.columns if "Last Call" in c), None)
        t_val = str(row.get(t_col, '')).strip() if t_col else ""
        ago = get_time_ago(t_val)
        
        tag_col = next((c for c in df.columns if "Tag" in c or "Label" in c), None)
        tag_val = str(row.get(tag_col, '')).strip() if tag_col else ""
        tag_display = f"`{tag_val}`" if tag_val else ""
        
        raw_name = str(row.get('Client Name', 'Unknown'))
        name_display = raw_name[:20] + ".." if len(raw_name) > 20 else raw_name
        
        badge_icon = "⚪"
        if "naya" in status.lower(): badge_icon="⚡"
        elif "visit" in status.lower(): badge_icon="📍"
        elif action_color == "red": badge_icon="🔴"
        
        header_text = f"**{badge_icon}** {name_display} {tag_display} *{ago}*"
        
        with st.expander(label=header_text, expanded=False):
            if action_color == "blue": st.info(action_text)
            elif action_color == "green": st.success(action_text)
            elif action_color == "orange": st.warning(action_text)
            elif action_color == "red": st.error(action_text)
            else: st.info(action_text)
            
            b1, b2 = st.columns(2)
            with b1: st.markdown(big_call_btn(phone), unsafe_allow_html=True)
            with b2: st.markdown(big_wa_btn(phone, row['Client Name']), unsafe_allow_html=True)
            
            st.caption(f"**📞 {phone}** | 👤 {assigned_to}")
            st.write(f"📝 **Status:**")
            ns = st.selectbox("Status", status_opts, key=f"s_{key_suffix}", index=get_smart_index(status), label_visibility="collapsed")
            
            existing_notes = str(row.get('Notes', ''))
            if len(existing_notes) > 2: st.markdown(f"<div class='note-history'>{existing_notes}</div>", unsafe_allow_html=True)
            
            c_u1, c_u2 = st.columns(2)
            new_note = c_u1.text_input("Note", key=f"n_{key_suffix}", placeholder="Details...")
            
            date_label = "📅 Follow-up"
            if "Visit" in ns: date_label = "📍 **Visit Date**"
            c_u2.write(date_label)
            
            d_opt = c_u2.radio("Pick", ["None", "Tom", "3 Days", "Custom"], horizontal=True, key=f"r_{key_suffix}", label_visibility="collapsed")
            final_date = None
            if d_opt == "Custom": final_date = c_u2.date_input("Date", min_value=today, key=f"d_{key_suffix}", label_visibility="collapsed")
            elif d_opt == "Tom": final_date = today + timedelta(days=1)
            elif d_opt == "3 Days": final_date = today + timedelta(days=3)
            
            new_assign = None
            if st.session_state['role'] == "Manager":
                try: u_idx = all_telecallers.index(assigned_to)
                except: u_idx = 0
                new_assign = st.selectbox("Assign", all_telecallers, index=u_idx, key=f"a_{key_suffix}")

            st.write("")
            button_ph = st.empty()
            if button_ph.button("✅ SAVE", key=f"btn_{key_suffix}", type="primary", use_container_width=True):
                try:
                    cell = leads_sheet.find(phone)
                    if not cell: st.error("❌ Not found")
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
                        if final_date: updates.append({'range': gspread.utils.rowcol_to_a1(r, f_idx), 'values': [[str(final_date)]]})
                        
                        t_idx = get_col("Last Call") or 10
                        updates.append({'range': gspread.utils.rowcol_to_a1(r, t_idx), 'values': [[get_ist_time()]]})
                        
                        c_idx = get_col("Count")
                        if c_idx:
                            curr = leads_sheet.cell(r, c_idx).value
                            val = int(curr) + 1 if curr and curr.isdigit() else 1
                            updates.append({'range': gspread.utils.rowcol_to_a1(r, c_idx), 'values': [[val]]})
                        
                        if new_assign and new_assign != assigned_to:
                            a_idx = get_col("Assign") or 7
                            updates.append({'range': gspread.utils.rowcol_to_a1(r, a_idx), 'values': [[new_assign]]})

                        leads_sheet.batch_update(updates)
                        button_ph.success("✅ SAVED!")
                        time.sleep(0.5); st.rerun()
                except Exception as e: st.error(f"Err: {e}")

# --- LIVE FEED (UPDATED 4-TAB LOGIC) ---
@st.fragment(run_every=30)
def show_live_leads_list(users_df, search_q, status_f):
    try: data = leads_sheet.get_all_records(); df = pd.DataFrame(data)
    except: return

    df.columns = df.columns.astype(str).str.strip()
    assign_col_name = next((c for c in df.columns if "assign" in c.lower()), None)

    # 1. Filter by User
    if st.session_state['role'] == "Telecaller":
        if assign_col_name:
            df = df[(df[assign_col_name] == st.session_state['username']) | 
                    (df[assign_col_name] == st.session_state['name']) |
                    (df[assign_col_name] == "TC1")]

    # 2. Global Search Override
    if search_q:
        df_search = df[df.astype(str).apply(lambda x: x.str.contains(search_q, case=False)).any(axis=1)]
        st.info(f"🔍 Found {len(df_search)} results for '{search_q}'")
        render_leads(df_search, users_df, "search")
        return

    # 3. SEGMENTATION LOGIC
    today = get_ist_date()
    
    def parse_f_date(val):
        if not val or len(str(val)) < 5: return None
        try: return datetime.strptime(str(val).strip(), "%Y-%m-%d").date()
        except: return None

    f_col_name = next((c for c in df.columns if "Follow" in c), None)
    df['ParsedDate'] = df[f_col_name].apply(parse_f_date) if f_col_name else None
    
    # DEFINE STATUS GROUPS
    # A. Dead/Closed
    dead_mask = df['Status'].str.contains("Closed|Booked|Junk|Invalid|Agent", case=False, na=False)
    
    # B. Recycle (Price / Location) - BUT only if they don't have a future date set!
    recycle_mask = df['Status'].str.contains("Price|Location|Not Interest", case=False, na=False)
    
    # C. Date Based (Action vs Future)
    date_action_mask = (df['ParsedDate'].notna()) & (df['ParsedDate'] <= today)
    future_mask = (df['ParsedDate'].notna()) & (df['ParsedDate'] > today)
    
    # D. New Leads
    new_lead_mask = df['Status'].str.contains("Naya|New", case=False, na=False)
    
    # --- ASSIGNING LEADS TO BUCKETS ---
    
    # BUCKET 1: ACTION (Date <= Today OR New Leads) AND NOT Dead
    # Note: If a lead is "Price Issue" but I set a follow-up for today, it should appear in ACTION, not Recycle.
    action_df = df[ (date_action_mask | new_lead_mask) & (~dead_mask) ].copy()
    
    # Sorting Action
    def get_sort_priority(row):
        if pd.notna(row['ParsedDate']):
            if row['ParsedDate'] < today: return 0 # Overdue
            return 1 # Today
        return 2 # New
    if not action_df.empty:
        action_df['Priority'] = action_df.apply(get_sort_priority, axis=1)
        action_df = action_df.sort_values(by=['Priority'])

    # BUCKET 2: FUTURE (Date > Today) AND NOT Dead
    future_df = df[ future_mask & (~dead_mask) ].copy()
    if not future_df.empty:
        future_df = future_df.sort_values(by='ParsedDate')

    # BUCKET 3: RECYCLE / MISMATCH
    # Logic: Status is Price/Location, AND Date is NULL (active concern addressed), AND Not Dead
    recycle_df = df[ recycle_mask & (df['ParsedDate'].isna()) & (~dead_mask) & (~new_lead_mask) ].copy()

    # BUCKET 4: HISTORY / CLOSED
    # Logic: Dead/Closed/Junk OR (Status=Price/Loc/Other but no date and not captured by recycle?)
    # Basically anything left over.
    history_mask = dead_mask | ( (~date_action_mask) & (~new_lead_mask) & (~future_mask) & (~recycle_mask) )
    history_df = df[history_mask].copy()

    # --- RENDER TABS ---
    tab1, tab2, tab3, tab4 = st.tabs([
        f"🔥 Action ({len(action_df)})", 
        f"📅 Waiting ({len(future_df)})",
        f"♻️ Recycle ({len(recycle_df)})",
        f"❌ Closed ({len(history_df)})"
    ])

    with tab1:
        st.caption("Calls to make NOW (Overdue, Today, New).")
        render_leads(action_df, users_df, "action")
        
    with tab2:
        st.caption("Scheduled for later.")
        render_leads(future_df, users_df, "future")
        
    with tab3:
        st.caption("💎 Mismatch leads (Price/Location). Retarget them for future projects.")
        render_leads(recycle_df, users_df, "recycle")
        
    with tab4:
        st.caption("Closed deals, agents, and junk data.")
        render_leads(history_df, users_df, "history")

def show_add_lead_form(users_df):
    with st.expander("➕ Naya Lead Jodein", expanded=False):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name"); phone = c2.text_input("Phone")
        c3, c4 = st.columns(2)
        src = c3.selectbox("Source", ["Meta Ads", "Canopy", "Agent", "Others"])
        ag = c4.text_input("Agent Name") if src == "Agent" else ""
        extra_notes = st.text_area("Notes / Instant Form Answers")
        
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
