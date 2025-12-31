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

# --- IMPORT CLICK DETECTOR ---
try:
    from st_click_detector import click_detector
except ImportError:
    st.error("⚠️ Library missing. Please run: pip install st-click-detector")
    st.stop()

# --- CONFIGURATION ---
st.set_page_config(page_title="TerraTip CRM", layout="wide", page_icon="🏡", initial_sidebar_state="collapsed")

# --- 1. GLOBAL APP CSS (THEME AWARE) ---
# We use 'var(--...)' so colors auto-flip between Light and Dark mode
custom_css = """
    <style>
        /* BASE APP: Let Streamlit handle the background, we just tweak the components */
        header {visibility: hidden;}
        [data-testid="stSidebarCollapsedControl"] {display: none;}
        
        /* 1. INPUT FIELDS (Auto-Theme) */
        .stTextInput input, .stSelectbox div[data-baseweb="select"], .stTextArea textarea {
            background-color: var(--secondary-background-color) !important;
            color: var(--text-color) !important;
            border: 1px solid var(--text-color) !important;
            opacity: 0.9; /* Slight transparency to blend borders */
        }
        
        /* 2. BUTTONS (Auto-Theme) */
        div.stButton > button {
            background-color: var(--secondary-background-color);
            color: var(--text-color);
            border: 1px solid var(--text-color);
            transition: all 0.3s ease;
        }
        div.stButton > button:hover {
            border-color: #FF4B4B;
            color: #FF4B4B;
        }
        
        /* 3. MODALS/DIALOGS */
        div[data-testid="stDialog"] { 
            background-color: var(--secondary-background-color) !important; 
            color: var(--text-color) !important;
            border: 1px solid var(--text-color);
        }
        
        /* 4. TEXT FIXES */
        label, p, .stMarkdown, h1, h2, h3, h4, h5, h6 { 
            color: var(--text-color) !important; 
        }

        /* Action Buttons (Keep specific colors as they indicate status) */
        .big-btn { display: block; width: 100%; padding: 12px; text-align: center; border-radius: 8px; font-weight: bold; margin-bottom: 10px; text-decoration: none; font-size: 15px; color: white !important; }
        .call-btn { background-color: #28a745; }
        .wa-btn { background-color: #25D366; }
    </style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- TIMEZONE ---
IST = pytz.timezone('Asia/Kolkata')
def get_ist_time(): return datetime.now(IST).strftime("%Y-%m-%d %H:%M")
def get_ist_date(): return datetime.now(IST).date()

if 'current_page' not in st.session_state: st.session_state['current_page'] = "CRM"

# --- HELPER: DATE FORMATTING ---
def format_datetime(val_str):
    if not val_str or len(str(val_str)) < 5: return "-"
    try:
        dt = datetime.strptime(str(val_str).strip(), "%Y-%m-%d %H:%M")
        return dt.strftime("%d-%b %H:%M")
    except: return "-"

def format_date_only(val_str):
    if not val_str or len(str(val_str)) < 5: return "-"
    try:
        d = datetime.strptime(str(val_str).strip(), "%Y-%m-%d").date()
        if d == get_ist_date(): return "Today"
        return d.strftime("%d-%b")
    except: return "-"

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

# --- HELPERS ---
def big_call_btn(num): return f"""<a href="tel:{num}" class="big-btn call-btn">📞 CALL NOW</a>"""
def big_wa_btn(num, name): return f"""<a href="https://wa.me/91{num}?text=Namaste {name}" class="big-btn wa-btn" target="_blank">💬 WHATSAPP</a>"""

PIPELINE_OPTS = [
    "Naya Lead", "Ringing / No Response", "Call Back Later", 
    "Interested / Send Details", "Follow-up / Thinking", 
    "Site Visit Scheduled", "Negotiation / Visit Done", 
    "Sale Closed", "Lost (Price / Location)", "Junk / Invalid / Broker"
]

def get_status_icon(status):
    s = str(status).lower().strip()
    if "naya" in s: return "⚡"
    if "ring" in s: return "📞"
    if "visit" in s: return "🗓"
    if "lost" in s or "price" in s: return "📉"
    if "interest" in s: return "🔥"
    return "⚪"

# --- MENU ---
@st.dialog("🍔 Navigation")
def open_main_menu():
    st.markdown(f"**👤 {st.session_state['name']}**")
    st.caption(f"Role: {st.session_state['role']}")
    st.divider()
    c1, c2, c3 = st.columns(3)
    if c1.button("🏠 CRM", use_container_width=True): st.session_state['current_page'] = "CRM"; st.rerun()
    if c2.button("📊 Stats", use_container_width=True): st.session_state['current_page'] = "Insights"; st.rerun()
    if c3.button("⚙️ Admin", use_container_width=True): st.session_state['current_page'] = "Admin"; st.rerun()
    st.divider()
    with st.expander("➕ New Lead", expanded=False):
        with st.form("menu_add"):
            name = st.text_input("Name"); phone = st.text_input("Phone")
            src = st.selectbox("Source", ["Meta Ads", "Canopy", "Agent", "Referral"])
            notes = st.text_area("Notes")
            if st.form_submit_button("Save"):
                try:
                    ts = get_ist_time(); new_id = generate_lead_id()
                    row = [new_id, ts, name, phone, src, "", st.session_state['username'], "Naya Lead", "", ts, "", notes, "", "", ""]
                    leads_sheet.append_row(row); st.success("Added!"); time.sleep(1); st.rerun()
                except Exception as e: st.error(str(e))
    st.divider()
    if st.button("🚪 Logout", use_container_width=True): st.session_state['logged_in'] = False; st.rerun()

# --- LEAD MODAL ---
@st.dialog("📋 Lead Details")
def open_lead_modal(row_dict, users_df):
    phone = str(row_dict.get('Phone', '')).replace(',', '').replace('.', '')
    name = row_dict.get('Client Name', 'Unknown')
    status = row_dict.get('Status', 'Naya Lead')
    notes = row_dict.get('Notes', '')
    
    tag_col = next((k for k in row_dict.keys() if "Tag" in k or "Label" in k), None)
    curr_tag = str(row_dict.get(tag_col, '')) if tag_col else ""
    
    c1, c2 = st.columns(2)
    with c1: st.markdown(big_call_btn(phone), unsafe_allow_html=True)
    with c2: st.markdown(big_wa_btn(phone, name), unsafe_allow_html=True)
    st.caption(f"**{name}** | {phone}")
    
    def get_index(val, opts):
        val = str(val).lower().strip()
        for i, x in enumerate(opts):
            if x.lower() == val: return i
        if "price" in val: return opts.index("Lost (Price / Location)")
        return 0

    new_status = st.selectbox("Status", PIPELINE_OPTS, index=get_index(status, PIPELINE_OPTS))
    new_tag = st.text_input("🏷️ Label (e.g. VIP, Old Data)", value=curr_tag)
    
    if len(str(notes)) > 2: st.markdown(f"<div class='note-history'>{notes}</div>", unsafe_allow_html=True)
    new_note = st.text_input("New Note")
    
    today = get_ist_date()
    col_d1, col_d2 = st.columns([2, 1])
    date_opt = col_d1.radio("Follow-up", ["None", "Tom", "3 Days", "Custom"], horizontal=True, label_visibility="collapsed")
    final_date = None
    if date_opt == "Custom": final_date = st.date_input("Date", min_value=today)
    elif date_opt == "Tom": final_date = today + timedelta(days=1)
    elif date_opt == "3 Days": final_date = today + timedelta(days=3)
    
    new_assign = None
    if st.session_state['role'] == "Manager":
        try: u_idx = users_df['Username'].tolist().index(row_dict.get('Assign', ''))
        except: u_idx = 0
        new_assign = st.selectbox("Assign", users_df['Username'].tolist(), index=u_idx)

    if st.button("✅ SAVE", type="primary", use_container_width=True):
        try:
            cell = leads_sheet.find(phone)
            if not cell: st.error("Not found")
            else:
                r = cell.row; h = leads_sheet.row_values(1)
                def get_idx(n): return next((i+1 for i,v in enumerate(h) if n.lower() in v.lower()), None)
                updates = []
                updates.append({'range': gspread.utils.rowcol_to_a1(r, get_idx("Status") or 8), 'values': [[new_status]]})
                tag_idx = get_idx("Tag") or get_idx("Label")
                if tag_idx: updates.append({'range': gspread.utils.rowcol_to_a1(r, tag_idx), 'values': [[new_tag]]})
                if new_note:
                    full_note = f"[{datetime.now(IST).strftime('%d-%b')}] {new_note}\n{notes}"
                    updates.append({'range': gspread.utils.rowcol_to_a1(r, get_idx("Notes") or 12), 'values': [[full_note]]})
                if final_date:
                    updates.append({'range': gspread.utils.rowcol_to_a1(r, get_idx("Follow") or 15), 'values': [[str(final_date)]]})
                t_idx = get_idx("Last Call")
                if t_idx: updates.append({'range': gspread.utils.rowcol_to_a1(r, t_idx), 'values': [[get_ist_time()]]})
                if new_assign:
                    updates.append({'range': gspread.utils.rowcol_to_a1(r, get_idx("Assign") or 7), 'values': [[new_assign]]})
                leads_sheet.batch_update(updates); st.rerun()
        except Exception as e: st.error(str(e))

# --- 2. CARD CSS INJECTOR (THEME AWARE FIX) ---
CARD_STYLE = """
<style>
    body { margin: 0; padding: 0; font-family: sans-serif; background-color: transparent; }
    
    a.card-link { text-decoration: none; color: inherit; display: block; }
    
    .lead-card {
        background-color: var(--secondary-background-color); /* AUTO-THEME BACKGROUND */
        border: 1px solid var(--text-color);
        opacity: 0.95; /* Prevent border from being too harsh */
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        position: relative;
        overflow: hidden;
    }
    
    .lead-card:hover { 
        filter: brightness(110%); /* Universal hover effect */
        border-color: #666; 
    }
    
    .status-strip {
        position: absolute; left: 0; top: 0; bottom: 0; width: 5px;
    }
    .strip-red { background-color: #FF4B4B; }
    .strip-orange { background-color: #FFA500; }
    .strip-green { background-color: #28a745; }
    .strip-grey { background-color: #555; }

    /* HEADER */
    .card-header {
        display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;
    }
    .card-name {
        font-size: 16px; font-weight: 700; 
        color: var(--text-color); /* AUTO-THEME TEXT */
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 60%;
    }
    
    /* PILL TAG (Right Side) */
    .card-tag {
        font-size: 10px; font-weight: 700; text-transform: uppercase;
        padding: 4px 8px; border-radius: 12px;
        background-color: var(--background-color); color: var(--text-color); 
        border: 1px solid var(--text-color);
        white-space: nowrap;
        opacity: 0.8;
    }

    /* BODY */
    .card-body {
        font-size: 14px; 
        color: var(--text-color); /* AUTO-THEME TEXT */
        opacity: 0.8;
        margin-bottom: 10px; display: flex; align-items: center; gap: 6px;
    }

    /* FOOTER (Split) */
    .card-footer {
        display: flex; justify-content: space-between; align-items: center;
        border-top: 1px solid var(--text-color); 
        opacity: 0.7;
        padding-top: 8px;
        font-size: 12px; 
        color: var(--text-color);
        font-family: monospace;
    }
    
    .footer-left {
        font-weight: 600;
        display: flex; align-items: center; gap: 4px;
        opacity: 1 !important; /* Keep status text bright */
    }
    .text-red { color: #FF4B4B; }
    .text-orange { color: #FFA500; }
    .text-green { color: #28a745; }
    .text-blue { color: #4287f5; }
</style>
"""

def generate_cards_html(dframe, context):
    html = CARD_STYLE 
    today = get_ist_date()
    
    for i, row in dframe.iterrows():
        phone = str(row.get('Phone', '')).replace(',', '').replace('.', '')
        name = str(row.get('Client Name', 'Unknown'))
        raw_status = str(row.get('Status', ''))
        
        # Tag
        tag_col = next((c for c in row.index if "Tag" in c or "Label" in c), None)
        tag_val = str(row.get(tag_col, '')).strip() if tag_col else ""
        tag_html = f"<div class='card-tag'>{tag_val}</div>" if tag_val and tag_val.lower() != "nan" else ""
        
        # Date Logic
        f_val = str(row.get(next((c for c in row.index if "Follow" in c), 'Follow'), '')).strip()
        t_val = str(row.get(next((c for c in row.index if "Last Call" in c), 'Last'), '')).strip()
        last_update = format_datetime(t_val)
        
        # Default styling
        strip_class = "strip-grey"
        next_date_html = ""
        
        # Context-Specific Logic
        if context == "Action":
            # Action Tab: Show Urgency
            strip_class = "strip-red"
            try:
                d = datetime.strptime(str(f_val).strip(), "%Y-%m-%d").date()
                if d < today: next_date_html = "<span class='footer-left text-red'>⚠️ Overdue</span>"
                elif d == today: next_date_html = "<span class='footer-left text-orange'>🔥 Today</span>"
                else: next_date_html = "<span class='footer-left text-green'>⚡ New</span>"
            except: next_date_html = "<span class='footer-left text-green'>⚡ New</span>"
            
        elif context == "Future":
            # Future Tab: Show Date
            strip_class = "strip-green"
            next_date_html = f"<span class='footer-left text-blue'>📅 {format_date_only(f_val)}</span>"
            
        elif context == "Recycle":
            strip_class = "strip-orange"
            next_date_html = "<span class='footer-left'>♻️ Recycle</span>"
            
        else: # History
            strip_class = "strip-grey"
            next_date_html = "<span class='footer-left'>🔒 Closed</span>"

        icon = get_status_icon(raw_status)
        display_status = "Lost" if "Lost" in raw_status else raw_status.split(" /")[0]

        card = f"""
        <a href='#' id='{phone}' class='card-link'>
            <div class='lead-card'>
                <div class='status-strip {strip_class}'></div>
                <div class='card-header'>
                    <div class='card-name'>{name}</div>
                    {tag_html}
                </div>
                <div class='card-body'>
                    <span>{icon}</span>
                    <span>{display_status}</span>
                </div>
                <div class='card-footer'>
                    {next_date_html}
                    <div>🕒 {last_update}</div>
                </div>
            </div>
        </a>
        """
        html += card
    return html

# --- LIVE FEED ---
@st.fragment(run_every=30)
def show_crm(users_df, search_q):
    try: data = leads_sheet.get_all_records(); df = pd.DataFrame(data)
    except: return
    df.columns = df.columns.astype(str).str.strip()

    if st.session_state['role'] == "Telecaller":
        ac = next((c for c in df.columns if "assign" in c.lower()), None)
        if ac: df = df[(df[ac] == st.session_state['username']) | (df[ac] == st.session_state['name']) | (df[ac] == "TC1")]

    if search_q:
        res = df[df.astype(str).apply(lambda x: x.str.contains(search_q, case=False)).any(axis=1)]
        st.info(f"🔍 Found {len(res)}")
        clicked = click_detector(generate_cards_html(res, "Search"), key="search_click")
        if clicked:
            r = df[df['Phone'].astype(str).str.replace(r'\D','',regex=True) == clicked].iloc[0]
            open_lead_modal(r.to_dict(), users_df)
        return

    today = get_ist_date()
    
    # Bulk Mode
    c_search, c_toggle = st.columns([0.65, 0.35])
    with c_search: pass
    is_bulk = False
    if st.session_state['role'] == "Manager":
        with c_toggle: is_bulk = st.toggle("⚡ Bulk")
    
    # --- BULK ACTIONS (RESTORED) ---
    if is_bulk:
        st.info("Select leads")
        c1, c2, c3 = st.columns([1.5, 1.5, 1])
        with c1:
            assign_target = st.selectbox("Assign", users_df['Username'].tolist(), label_visibility="collapsed", placeholder="User")
            if st.button("Assign"):
                phones = [k.split("_")[-1] for k, v in st.session_state.items() if k.startswith("sel_") and v]
                if phones:
                    try:
                        h = leads_sheet.row_values(1)
                        col_idx = next((i+1 for i,v in enumerate(h) if "Assign" in v), None)
                        if col_idx:
                            all_v = leads_sheet.get_all_values(); updates = []
                            for i, r in enumerate(all_v):
                                if len(r)>3 and str(r[3]).replace(',','').replace('.','') in phones:
                                    updates.append({'range': gspread.utils.rowcol_to_a1(i+1, col_idx), 'values': [[assign_target]]})
                            if updates: leads_sheet.batch_update(updates); st.success("Done!"); time.sleep(1); st.rerun()
                    except: st.error("Error")
        with c2:
            label_text = st.text_input("Label", placeholder="Tag", label_visibility="collapsed")
            if st.button("Tag"):
                phones = [k.split("_")[-1] for k, v in st.session_state.items() if k.startswith("sel_") and v]
                if phones and label_text:
                    try:
                        h = leads_sheet.row_values(1)
                        col_idx = next((i+1 for i,v in enumerate(h) if "Tag" in v or "Label" in v), None)
                        if col_idx:
                            all_v = leads_sheet.get_all_values(); updates = []
                            for i, r in enumerate(all_v):
                                if len(r)>3 and str(r[3]).replace(',','').replace('.','') in phones:
                                    updates.append({'range': gspread.utils.rowcol_to_a1(i+1, col_idx), 'values': [[label_text]]})
                            if updates: leads_sheet.batch_update(updates); st.success("Done!"); time.sleep(1); st.rerun()
                    except: st.error("Error")
        with c3:
            if st.button("🗑️"):
                phones = [k.split("_")[-1] for k, v in st.session_state.items() if k.startswith("sel_") and v]
                if phones:
                    try:
                        all_v = leads_sheet.get_all_values()
                        to_del = [i+1 for i,r in enumerate(all_v) if len(r)>3 and str(r[3]).replace(',','').replace('.','') in phones]
                        for r in sorted(to_del, reverse=True): leads_sheet.delete_rows(r)
                        st.success("Del"); time.sleep(1); st.rerun()
                    except: st.error("Error")

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
    
    def render_tab_content(dframe, ctx, key_prefix):
        if dframe.empty: st.info("Empty")
        else:
            if ctx == "Future": dframe = dframe.sort_values(by='PD')
            
            if is_bulk:
                # Bulk Mode: Standard Buttons
                for i, row in dframe.iterrows():
                    c1, c2 = st.columns([0.15, 0.85])
                    c1.checkbox("", key=f"sel_{key_prefix}_{row['Phone']}")
                    c2.button(f"{row['Client Name']}", key=f"btn_{key_prefix}_{row['Phone']}", use_container_width=True)
            else:
                # View Mode: HTML Cards (CSS Injected)
                html = generate_cards_html(dframe, ctx)
                clicked = click_detector(html, key=f"click_{key_prefix}")
                if clicked:
                    r = df[df['Phone'].astype(str).str.replace(r'\D','',regex=True) == clicked]
                    if not r.empty: open_lead_modal(r.iloc[0].to_dict(), users_df)

    with t1: render_tab_content(df[action_cond & ~dead & ~recycle], "Action", "act")
    with t2: render_tab_content(df[future_cond & ~dead & ~recycle], "Future", "fut")
    with t3: render_tab_content(df[recycle & ~dead], "Recycle", "rec")
    with t4: render_tab_content(df[dead], "History", "hist")

# --- ADMIN PANEL ---
def show_admin(users_df):
    c1, c2 = st.columns([1,2])
    with c1:
        st.subheader("Create User")
        with st.form("nu"):
            u = st.text_input("User"); p = st.text_input("Pass", type="password")
            n = st.text_input("Name"); r = st.selectbox("Role", ["Telecaller", "Sales Specialist", "Manager"])
            if st.form_submit_button("Create"):
                users_sheet.append_row([u, hash_pass(p), r, n]); st.success("Created!"); st.rerun()
        st.divider()
        st.subheader("📥 Upload CSV")
        ag = st.multiselect("Assign", users_df['Username'].tolist())
        up = st.file_uploader("CSV", type=['csv'])
        if up and st.button("Upload"):
            if not ag: st.error("Select Agent!")
            else:
                try:
                    try: df_up = pd.read_csv(up, encoding='utf-8')
                    except: df_up = pd.read_csv(up, encoding='ISO-8859-1')
                    cols = [c.lower() for c in df_up.columns]
                    n_i = next((i for i, c in enumerate(cols) if "name" in c), -1)
                    p_i = next((i for i, c in enumerate(cols) if "phone" in c or "mobile" in c), -1)
                    if n_i == -1 or p_i == -1: st.error("Column missing")
                    else:
                        nc = df_up.columns[n_i]; pc = df_up.columns[p_i]
                        ex_phones = set(re.sub(r'\D', '', str(p))[-10:] for p in leads_sheet.col_values(4))
                        rows = []; cyc = itertools.cycle(ag); ts = get_ist_time()
                        for _, r in df_up.iterrows():
                            p_clean = re.sub(r'\D', '', str(r[pc]))[-10:]
                            if len(p_clean)==10 and p_clean not in ex_phones:
                                rows.append([generate_lead_id(), ts, r[nc], p_clean, "Upload", "", next(cyc), "Naya Lead", "", ts, "", "", "", "", ""])
                                ex_phones.add(p_clean)
                        if rows: leads_sheet.append_rows(rows); st.success(f"Added {len(rows)}"); time.sleep(1); st.rerun()
                except Exception as e: st.error(str(e))
    with c2:
        st.subheader("Team")
        st.dataframe(users_df[['Name','Role']], hide_index=True)
        opts = [x for x in users_df['Username'].unique() if x != st.session_state['username']]
        if opts:
            d_u = st.selectbox("Delete User", opts)
            if st.button("❌ Delete"):
                cell = users_sheet.find(d_u); users_sheet.delete_rows(cell.row); st.success("Deleted"); st.rerun()

# --- ROUTER ---
c_search, c_menu = st.columns([0.85, 0.15])
with c_search:
    if st.session_state['current_page'] == "CRM":
        search_query = st.text_input("Search", placeholder="Search...", label_visibility="collapsed")
    else: st.write(f"## {st.session_state['current_page']}")

with c_menu:
    if st.button("🍔", use_container_width=True): open_main_menu()

st.divider()

if st.session_state['current_page'] == "CRM":
    q = search_query if 'search_query' in locals() and search_query else None
    show_crm(users_df, q)
elif st.session_state['current_page'] == "Insights":
    st.title("📊 Stats"); st.info("Analytics coming soon.")
elif st.session_state['current_page'] == "Admin":
    if st.session_state['role'] == "Manager": show_admin(users_df)
    else: st.error("⛔ Access Denied")
