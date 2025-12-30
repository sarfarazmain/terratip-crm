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

# --- CUSTOM CSS ---
custom_css = """
    <style>
        /* 1. FORCE DARK MODE */
        .stApp { background-color: #0e1117 !important; color: white !important; }
        
        /* 2. HIDE DEFAULT HEADER */
        header {visibility: hidden;}
        [data-testid="stSidebarCollapsedControl"] {display: none;}
        
        /* 3. INPUT FIELDS */
        .stTextInput input, .stSelectbox div[data-baseweb="select"], .stTextArea textarea {
            background-color: #1a1a1d !important; color: white !important; border: 1px solid #444 !important;
        }
        
        /* 4. MENU BUTTON */
        div[data-testid="stHorizontalBlock"] button { border-radius: 8px; font-weight: bold; }

        /* 5. CARD STYLING */
        .stButton button {
            width: 100%; text-align: left !important; padding: 16px 18px !important;
            border-radius: 12px !important; background-color: #1a1a1d !important;
            border: 1px solid #333; margin-bottom: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        .stButton button p {
            font-family: 'Source Sans Pro', sans-serif; color: #ffffff !important;
            font-size: 15px; margin: 0; line-height: 1.5;
        }
        
        /* 6. UTILS */
        div[data-testid="stDialog"] { border-radius: 16px; background-color: #262730; }
        .big-btn { display: block; width: 100%; padding: 14px; text-align: center; border-radius: 10px; font-weight: bold; margin-bottom: 10px; text-decoration: none;}
        .call-btn { background-color: #28a745; color: white !important; }
        .wa-btn { background-color: #25D366; color: white !important; }
        .note-history { font-size: 13px; color: #ccc; background: #121212; padding: 12px; border-radius: 8px; max-height: 150px; overflow-y: auto; margin-bottom: 15px; border-left: 4px solid #555; }
        .stTabs [data-baseweb="tab-list"] button { border-radius: 20px; padding: 6px 12px; font-size: 13px; }
        label, .stMarkdown p, .stToggle p { color: #eee !important; }
    </style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- TIMEZONE ---
IST = pytz.timezone('Asia/Kolkata')
def get_ist_time(): return datetime.now(IST).strftime("%Y-%m-%d %H:%M")
def get_ist_date(): return datetime.now(IST).date()

# --- NAVIGATION STATE ---
if 'current_page' not in st.session_state: st.session_state['current_page'] = "CRM"

# --- FEEDBACK ---
def set_feedback(msg, type="success"):
    st.session_state['feedback_msg'] = msg
    st.session_state['feedback_type'] = type

def show_feedback():
    if 'feedback_msg' in st.session_state and st.session_state['feedback_msg']:
        msg = st.session_state['feedback_msg']
        icon = "✅" if st.session_state['feedback_type'] == "success" else "❌"
        st.toast(msg, icon=icon)
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
    if "naya" in s: return "🆕"
    if "ring" in s: return "📞"
    if "visit" in s: return "🗓️"
    if "lost" in s or "price" in s: return "📉"
    if "interest" in s: return "🔥"
    return "⚪"

# --- MENU ---
@st.dialog("🍔 Navigation Menu")
def open_main_menu():
    st.markdown(f"### 👤 {st.session_state['name']}")
    st.caption(f"Role: {st.session_state['role']}")
    st.divider()
    c1, c2, c3 = st.columns(3)
    if c1.button("🏠 CRM", use_container_width=True): st.session_state['current_page'] = "CRM"; st.rerun()
    if c2.button("📊 Stats", use_container_width=True): st.session_state['current_page'] = "Insights"; st.rerun()
    if c3.button("⚙️ Admin", use_container_width=True): st.session_state['current_page'] = "Admin"; st.rerun()
    st.divider()
    with st.expander("➕ Add New Lead", expanded=False):
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
    
    # Tag Handling
    tag_col_name = next((k for k in row_dict.keys() if "Tag" in k or "Label" in k), None)
    current_tag = str(row_dict.get(tag_col_name, '')) if tag_col_name else ""
    
    c1, c2 = st.columns(2)
    with c1: st.markdown(big_call_btn(phone), unsafe_allow_html=True)
    with c2: st.markdown(big_wa_btn(phone, name), unsafe_allow_html=True)
    
    st.caption(f"👤 **{name}** | 📞 {phone}")
    
    def get_index(val, opts):
        val = str(val).lower().strip()
        for i, x in enumerate(opts):
            if x.lower() == val: return i
        if "price" in val or "location" in val: return opts.index("Lost (Price / Location)")
        if "visit" in val: return opts.index("Site Visit Scheduled")
        return 0

    new_status = st.selectbox("Status", PIPELINE_OPTS, index=get_index(status, PIPELINE_OPTS))
    new_tag = st.text_input("🏷️ Custom Label (e.g. VIP, Old Meta)", value=current_tag)
    
    if len(str(notes)) > 2: st.markdown(f"<div class='note-history'>{notes}</div>", unsafe_allow_html=True)
    new_note = st.text_input("➕ New Note")
    
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
            if not cell: st.error("❌ Not found")
            else:
                r = cell.row; h = leads_sheet.row_values(1)
                def get_col_idx(n): return next((i+1 for i,v in enumerate(h) if n.lower() in v.lower()), None)
                
                updates = []
                updates.append({'range': gspread.utils.rowcol_to_a1(r, get_col_idx("Status") or 8), 'values': [[new_status]]})
                
                # Save Tag
                tag_idx = get_col_idx("Tag") or get_col_idx("Label")
                if tag_idx: updates.append({'range': gspread.utils.rowcol_to_a1(r, tag_idx), 'values': [[new_tag]]})
                
                if new_note:
                    full_note = f"[{datetime.now(IST).strftime('%d-%b')}] {new_note}\n{notes}"
                    updates.append({'range': gspread.utils.rowcol_to_a1(r, get_col_idx("Notes") or 12), 'values': [[full_note]]})
                if final_date:
                    updates.append({'range': gspread.utils.rowcol_to_a1(r, get_col_idx("Follow") or 15), 'values': [[str(final_date)]]})
                
                # Update Count & Last Call
                t_idx = get_col_idx("Last Call"); c_idx = get_col_idx("Count")
                if t_idx: updates.append({'range': gspread.utils.rowcol_to_a1(r, t_idx), 'values': [[get_ist_time()]]})
                if c_idx:
                    curr = leads_sheet.cell(r, c_idx).value
                    val = int(curr) + 1 if curr and curr.isdigit() else 1
                    updates.append({'range': gspread.utils.rowcol_to_a1(r, c_idx), 'values': [[val]]})
                
                if new_assign:
                    updates.append({'range': gspread.utils.rowcol_to_a1(r, get_col_idx("Assign") or 7), 'values': [[new_assign]]})

                leads_sheet.batch_update(updates); st.rerun()
        except Exception as e: st.error(str(e))

# --- RENDER LIST ---
def render_leads(df, users_df, label_prefix="", is_bulk=False):
    if df.empty: st.info("✅ No leads here."); return

    for i, row in df.iterrows():
        phone = str(row.get('Phone', '')).replace(',', '').replace('.', '')
        name = str(row.get('Client Name', 'Unknown'))
        raw_status = str(row.get('Status', ''))
        
        # Tags Logic
        tag_col = next((c for c in df.columns if "Tag" in c or "Label" in c), None)
        tag_val = str(row.get(tag_col, '')).strip() if tag_col else ""
        # Format Tag string to be bold and distinct
        tag_display = f" 🏷️ *{tag_val}*" if tag_val and tag_val.lower() != "nan" else ""
        
        display_status = "Lost" if "Lost" in raw_status or "Price" in raw_status else raw_status
        if "Ringing" in raw_status: display_status = "Ringing"
        
        f_col = next((c for c in df.columns if "Follow" in c), None)
        f_val = str(row.get(f_col, '')).strip()
        display_date = ""
        if len(f_val) > 5:
            try:
                d = datetime.strptime(f_val, "%Y-%m-%d").date()
                display_date = "Today" if d == datetime.now(IST).date() else d.strftime('%d %b')
            except: pass
            
        icon = get_status_icon(raw_status)
        short_name = name[:18] + ".." if len(name) > 18 else name
        
        # LABEL with TAG INCLUDED
        if display_date:
            label = f"**{short_name}**{tag_display}\n{icon} {display_status}  •  📅 {display_date}"
        else:
            label = f"**{short_name}**{tag_display}\n{icon} {display_status}"
        
        if is_bulk:
            c1, c2 = st.columns([0.15, 0.85])
            c1.checkbox("", key=f"sel_{label_prefix}_{phone}")
            if c2.button(label, key=f"btn_{label_prefix}_{phone}", use_container_width=True): open_lead_modal(row.to_dict(), users_df)
        else:
            if st.button(label, key=f"btn_{label_prefix}_{phone}", use_container_width=True): open_lead_modal(row.to_dict(), users_df)

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
        st.info(f"🔍 Found {len(res)}"); render_leads(res, users_df, "search", False); return

    today = get_ist_date()
    
    # BULK & SEARCH UI
    c_search, c_toggle = st.columns([0.65, 0.35])
    with c_search: pass
    
    is_bulk = False
    if st.session_state['role'] == "Manager":
        with c_toggle: is_bulk = st.toggle("⚡ Bulk Mode")
    
    # --- BULK TOOLBAR (ASSIGN + LABEL + DELETE) ---
    if is_bulk:
        st.info("👇 Select leads below to apply actions")
        b1, b2, b3 = st.columns([1, 1, 1])
        
        with b1:
            # Assign
            assign_target = st.selectbox("Assign", users_df['Username'].unique(), label_visibility="collapsed", placeholder="User")
            if st.button("Apply User"):
                phones = [k.split("_")[-1] for k, v in st.session_state.items() if k.startswith("sel_") and v]
                if phones:
                    try:
                        h = leads_sheet.row_values(1)
                        col_idx = next(i for i,v in enumerate(h) if "assign" in v.lower()) + 1
                        all_v = leads_sheet.get_all_values()
                        updates = []
                        for i, r in enumerate(all_v):
                            if str(r[3]).replace(',','').replace('.','') in phones:
                                updates.append({'range': gspread.utils.rowcol_to_a1(i+1, col_idx), 'values': [[assign_target]]})
                        if updates: leads_sheet.batch_update(updates); st.success("Assigned!"); st.rerun()
                    except: st.error("Error")

        with b2:
            # Label
            label_text = st.text_input("Label", placeholder="Tag (e.g. VIP)", label_visibility="collapsed")
            if st.button("Apply Label"):
                phones = [k.split("_")[-1] for k, v in st.session_state.items() if k.startswith("sel_") and v]
                if phones and label_text:
                    try:
                        h = leads_sheet.row_values(1)
                        # Find Tag column or default to col 13/14 if specifically set up, better to find dynamically
                        col_idx = next((i for i,v in enumerate(h) if "Tag" in v or "Label" in v), None)
                        if not col_idx: st.error("No 'Tags' column found in Sheet!"); return
                        col_idx += 1
                        
                        all_v = leads_sheet.get_all_values()
                        updates = []
                        for i, r in enumerate(all_v):
                            if str(r[3]).replace(',','').replace('.','') in phones:
                                updates.append({'range': gspread.utils.rowcol_to_a1(i+1, col_idx), 'values': [[label_text]]})
                        if updates: leads_sheet.batch_update(updates); st.success("Labeled!"); st.rerun()
                    except: st.error("Error")

        with b3:
            if st.button("🗑️ Delete", type="primary"):
                phones = [k.split("_")[-1] for k, v in st.session_state.items() if k.startswith("sel_") and v]
                if phones:
                    try:
                        all_v = leads_sheet.get_all_values()
                        to_del = [i+1 for i,r in enumerate(all_v) if str(r[3]).replace(',','').replace('.','') in phones]
                        for r in sorted(to_del, reverse=True): leads_sheet.delete_rows(r)
                        st.rerun()
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
    
    with t1: render_leads(df[action_cond & ~dead & ~recycle], users_df, "act", is_bulk)
    with t2: render_leads(df[future_cond & ~dead & ~recycle], users_df, "fut", is_bulk)
    with t3: render_leads(df[recycle & ~dead], users_df, "rec", is_bulk)
    with t4: render_leads(df[dead], users_df, "hist", is_bulk)

# --- ADMIN PANEL ---
def show_admin(users_df):
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
        selected_agents = st.multiselect("Assign Leads To:", users_df['Username'].tolist())
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
                    
                    if name_idx == -1 or phone_idx == -1: st.error("Could not find Name/Phone cols")
                    else:
                        name_col = df_up.columns[name_idx]; phone_col = df_up.columns[phone_idx]
                        ignore_list = [name_col.lower(), phone_col.lower(), "id", "created_time", "ad_id", "ad_name", "campaign_name", "form_id", "platform", "is_organic"]
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
                                        if val and val.lower() != "nan": notes_data.append(f"{ec}: {val}")
                                    final_note = " | ".join(notes_data)
                                    new_id = generate_lead_id(); assigned_person = next(agent_cycle)
                                    new_row = [new_id, ts, row[name_col], p_clean, "Meta Ads", "", assigned_person, "Naya Lead", "", ts, "", final_note, "", "", ""]
                                    rows_to_add.append(new_row); existing_phones_set.add(p_last_10)
                        if rows_to_add: leads_sheet.append_rows(rows_to_add); set_feedback(f"✅ Added {len(rows_to_add)} leads!"); time.sleep(1); st.rerun()
                except Exception as e: st.error(str(e))

    with c2:
        st.subheader("Team List")
        st.dataframe(users_df[['Name','Username','Role']], hide_index=True)
        opts = [x for x in users_df['Username'].unique() if x != st.session_state['username']]
        if opts:
            dt = st.selectbox("Delete", opts)
            if st.button("❌ Delete"): users_sheet.delete_rows(users_sheet.find(dt).row); set_feedback(f"Deleted {dt}"); st.rerun()

# --- MAIN APP ROUTER ---
c_search, c_menu = st.columns([0.85, 0.15])
with c_search:
    if st.session_state['current_page'] == "CRM":
        search_query = st.text_input("Search", placeholder="Name or Phone...", label_visibility="collapsed")
    else:
        st.write(f"## {st.session_state['current_page']}")

with c_menu:
    if st.button("🍔", use_container_width=True): open_main_menu()

st.divider()

if st.session_state['current_page'] == "CRM":
    q = search_query if 'search_query' in locals() and search_query else None
    show_crm(users_df, q)
elif st.session_state['current_page'] == "Insights":
    show_master_insights()
elif st.session_state['current_page'] == "Admin":
    if st.session_state['role'] == "Manager": show_admin(users_df)
    else: st.error("⛔ Access Denied")
