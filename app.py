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

    if search_q: df = df[df.astype(str).apply(lambda x: x.str.contains(search_q, case=False)).any(axis=1)]
    if status_f: df = df[df['Status'].isin(status_f)]

    today = get_ist_date()
    
    # --- BULK ACTIONS (Manager Only) ---
    is_bulk_mode = False
    if st.session_state['role'] == "Manager":
        c_bulk_switch, c_bulk_input = st.columns([1, 3])
        is_bulk_mode = c_bulk_switch.toggle("⚡ Bulk Actions Mode")
        
        if is_bulk_mode:
            with c_bulk_input:
                bk_t1, bk_t2 = st.tabs(["🏷️ Apply Label", "🗑️ Delete Leads"])
                
                # TAB 1: LABELING
                with bk_t1:
                    b_col1, b_col2 = st.columns([2, 1])
                    tag_to_apply = b_col1.text_input("New Label", placeholder="e.g. Hot", label_visibility="collapsed")
                    if b_col2.button("Apply Label", type="primary"):
                        if not tag_to_apply: st.error("Type label.")
                        else:
                            selected_phones = [str(row['Phone']).replace(',', '').replace('.', '') for idx, row in df.iterrows() if st.session_state.get(f"sel_{str(row['Phone']).replace(',', '').replace('.', '')}", False)]
                            if not selected_phones: st.warning("No leads checked.")
                            else:
                                try:
                                    h = leads_sheet.row_values(1)
                                    try: t_idx = next(i for i,v in enumerate(h) if "Tag" in v or "Label" in v) + 1
                                    except: st.error("❌ 'Tags' column missing."); t_idx = None
                                    if t_idx:
                                        all_records = leads_sheet.get_all_values()
                                        updates = []
                                        for p in selected_phones:
                                            r_idx = -1
                                            for i, row in enumerate(all_records):
                                                if str(row[3]).replace('.0','') == str(p): r_idx = i + 1; break
                                            if r_idx != -1: updates.append({'range': gspread.utils.rowcol_to_a1(r_idx, t_idx), 'values': [[tag_to_apply]]})
                                        if updates: leads_sheet.batch_update(updates); set_feedback(f"✅ Applied!"); time.sleep(1); st.rerun()
                                except Exception as e: st.error(f"Err: {e}")

                # TAB 2: DELETE (NEW FEATURE)
                with bk_t2:
                    st.warning("⚠️ Action cannot be undone.")
                    d_col1, d_col2 = st.columns([2, 1])
                    confirm_txt = d_col1.text_input("Type DELETE to confirm", placeholder="DELETE", label_visibility="collapsed")
                    if d_col2.button("🗑️ Delete Selected", type="primary"):
                        if confirm_txt != "DELETE":
                            st.error("Please type DELETE exactly.")
                        else:
                            selected_phones = [str(row['Phone']).replace(',', '').replace('.', '') for idx, row in df.iterrows() if st.session_state.get(f"sel_{str(row['Phone']).replace(',', '').replace('.', '')}", False)]
                            if not selected_phones: st.warning("No leads selected.")
                            else:
                                try:
                                    all_records = leads_sheet.get_all_values()
                                    rows_to_delete = []
                                    for p in selected_phones:
                                        for i, row in enumerate(all_records):
                                            if str(row[3]).replace('.0','') == str(p):
                                                rows_to_delete.append(i + 1)
                                                break
                                    
                                    if rows_to_delete:
                                        rows_to_delete.sort(reverse=True)
                                        for r in rows_to_delete:
                                            leads_sheet.delete_rows(r)
                                        set_feedback(f"✅ Deleted {len(rows_to_delete)} leads."); time.sleep(1); st.rerun()
                                    else:
                                        st.warning("Could not find rows to delete.")
                                except Exception as e: st.error(f"Delete Error: {e}")

    # --- LEAD LIST RENDERING ---
    def get_lead_meta(row):
        status = str(row.get('Status', '')).strip()
        f_col = next((c for c in df.columns if "Follow" in c), None)
        f_val = str(row.get(f_col, '')).strip() if f_col else ""
        t_col = next((c for c in df.columns if "Last Call" in c), None)
        t_val = str(row.get(t_col, '')).strip() if t_col else ""
        ago = get_time_ago(t_val)
        
        tag_col = next((c for c in df.columns if "Tag" in c or "Label" in c), None)
        tag_val = str(row.get(tag_col, '')).strip() if tag_col else ""
        tag_display = f"`{tag_val}`" if tag_val else ""
        
        raw_name = str(row.get('Client Name', 'Unknown'))
        name_display = raw_name[:20] + ".." if len(raw_name) > 20 else raw_name
        
        score = 4; badge_text = "PASSIVE"; badge_icon = "⚪"
        sort_date = date.max 
        
        if "naya" in status.lower() or "new" in status.lower(): 
            score = 0; badge_text = "NEW"; badge_icon="⚡"
        elif "visit" in status.lower() or "schedule" in status.lower(): 
            score = 0; badge_text = "VISIT"; badge_icon="📍"
        elif "negotiat" in status.lower(): 
            score = 0; badge_text = "DEAL"; badge_icon="💰"
        elif f_val and len(f_val) > 5:
            try:
                f_date = datetime.strptime(f_val, "%Y-%m-%d").date()
                sort_date = f_date
                if f_date < today: score = 1; badge_text = f"LATE {f_date.strftime('%d%b')}"; badge_icon="🔴"
                elif f_date == today: score = 2; badge_text = "TODAY"; badge_icon="🟡"
                else: score = 3; badge_text = f"{f_date.strftime('%d%b')}"; badge_icon="🗓️"
            except: pass
            
        if "VISIT" in badge_text and f_val and len(f_val) > 5:
             try: 
                 f_date = datetime.strptime(f_val, "%Y-%m-%d").date()
                 badge_text = f"{f_date.strftime('%d%b')}"; badge_icon="📍"
                 sort_date = f_date
             except: pass

        return score, sort_date, badge_text, badge_icon, ago, f_val, name_display, tag_display

    if not df.empty:
        df[['Score', 'SortDate', 'Badge', 'Icon', 'Ago', 'FDate', 'ShortName', 'TagText']] = df.apply(lambda row: pd.Series(get_lead_meta(row)), axis=1)
        df = df.sort_values(by=['Score', 'SortDate'], ascending=[True, True])

    if df.empty: st.info("📭 No leads found."); return

    st.caption(f"⚡ Live: {len(df)} Leads (IST Time: {get_ist_time()})")
    
    status_opts = ["Naya Lead", "Ringing / Busy / No Answer", "Asked to Call Later", "Interested (Send Details)", "Site Visit Scheduled", "Visit Done (Negotiation)", "Sale Closed / Booked", "Not Interested / Price / Location", "Junk / Invalid / Agent"]
    all_telecallers = users_df['Username'].tolist()

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
                if f_date > today: return (f"📅 {f_date.strftime('%d-%b')}", "green")
                if f_date == today: return ("🟡 Call Today!", "orange")
            except: pass
        s = status.lower()
        if "naya" in s: return ("⚡ Call Now", "blue")
        if "ring" in s: return ("⏰ Retry 4h", "orange")
        if "visit" in s: return ("📍 Confirm", "green")
        return ("❓ Update", "grey")

    for i, row in df.iterrows():
        phone = str(row.get('Phone', '')).replace(',', '').replace('.', '')
        assigned_to = row.get(assign_col_name, '-') if assign_col_name else '-'
        f_col_name = next((c for c in df.columns if "Follow" in c), None)
        f_val = row.get(f_col_name, '') if f_col_name else ''
        status = str(row.get('Status', 'Naya Lead')).strip()
        action_text, action_color = get_pipeline_action(status, str(f_val).strip())

        header_text = f"**{row['Icon']} {row['Badge']}** {row['ShortName']} {row['TagText']} *{row['Ago']}*"
        
        container = st
        if is_bulk_mode:
            c_check, c_body = st.columns([0.1, 0.9])
            with c_check: st.checkbox("", key=f"sel_{phone}")
            container = c_body
            
        with container.expander(label=header_text, expanded=False):
            if action_color == "blue": st.info(action_text)
            elif action_color == "green": st.success(action_text)
            elif action_color == "orange": st.warning(action_text)
            else: st.info(action_text)
            
            b1, b2 = st.columns(2)
            with b1: st.markdown(big_call_btn(phone), unsafe_allow_html=True)
            with b2: st.markdown(big_wa_btn(phone, row['Client Name']), unsafe_allow_html=True)
            
            st.caption(f"**📞 {phone}** | 👤 {assigned_to}")
            st.write(f"📝 **Status:**")
            ns = st.selectbox("Status", status_opts, key=f"s_{i}", index=get_smart_index(status), label_visibility="collapsed")
            
            existing_notes = str(row.get('Notes', ''))
            if len(existing_notes) > 2: st.markdown(f"<div class='note-history'>{existing_notes}</div>", unsafe_allow_html=True)
            
            c_u1, c_u2 = st.columns(2)
            new_note = c_u1.text_input("Note", key=f"n_{i}", placeholder="Details...")
            
            date_label = "📅 Follow-up"
            if "Visit" in ns: date_label = "📍 **Visit Date**"
            c_u2.write(date_label)
            
            d_opt = c_u2.radio("Pick", ["None", "Tom", "3 Days", "Custom"], horizontal=True, key=f"r_{i}", label_visibility="collapsed")
            final_date = None
            if d_opt == "Custom": final_date = c_u2.date_input("Date", min_value=today, key=f"d_{i}", label_visibility="collapsed")
            elif d_opt == "Tom": final_date = today + timedelta(days=1)
            elif d_opt == "3 Days": final_date = today + timedelta(days=3)
            
            new_assign = None
            if st.session_state['role'] == "Manager":
                try: u_idx = all_telecallers.index(assigned_to)
                except: u_idx = 0
                new_assign = st.selectbox("Assign", all_telecallers, index=u_idx, key=f"a_{i}")

            st.write("")
            button_ph = st.empty()
            if button_ph.button("✅ SAVE", key=f"btn_{i}", type="primary", use_container_width=True):
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
            if lc_col: valid_dates = [str(d) for d in user_df[lc_col] if str(d).strip() != ""]; 
            if valid_dates: last_active = max(valid_dates)
            stats.append({"User": user, "Total": len(user_df), "⚠️ Pending": pending, "🔥 Active": working, "🎉 Sold": sold_count, "🕒 Last Active": last_active})
        if stats: st.dataframe(pd.DataFrame(stats), use_container_width=True, hide_index=True)
        else: st.info("No activity yet.")

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
                    
                    # 1. FIND NAME/PHONE
                    cols = [c.lower() for c in df_up.columns]
                    name_idx = next((i for i, c in enumerate(cols) if any(x in c for x in ["full_name", "fullname", "name"])), -1)
                    phone_idx = next((i for i, c in enumerate(cols) if any(x in c for x in ["phone", "mobile", "p:"])), -1)
                    
                    if name_idx == -1 or phone_idx == -1:
                        st.error("Could not find 'Name' or 'Phone' columns automatically.")
                    else:
                        name_col = df_up.columns[name_idx]
                        phone_col = df_up.columns[phone_idx]
                        
                        # 2. FILTER OUT JUNK COLUMNS
                        # We specifically block standard Meta/Facebook columns
                        ignore_list = [
                            name_col.lower(), phone_col.lower(),
                            "id", "created_time", "ad_id", "ad_name", "adset_id", "adset_name",
                            "campaign_id", "campaign_name", "form_id", "form_name", 
                            "platform", "is_organic", "date", "start_date", "end_date"
                        ]
                        
                        # Keep only columns that are NOT in the ignore list
                        extra_cols = [c for c in df_up.columns if c.lower() not in ignore_list]

                        raw_existing = leads_sheet.col_values(4); existing_phones_set = {re.sub(r'\D', '', str(p))[-10:] for p in raw_existing}
                        rows_to_add = []; ts = get_ist_time(); agent_cycle = itertools.cycle(selected_agents)
                        
                        for idx, row in df_up.iterrows():
                            p_raw = str(row[phone_col]); p_clean = re.sub(r'\D', '', p_raw)
                            if len(p_clean) >= 10:
                                p_last_10 = p_clean[-10:]
                                if p_last_10 not in existing_phones_set:
                                    # Collect ONLY clean answers for Notes
                                    notes_data = []
                                    for ec in extra_cols:
                                        val = str(row[ec]).strip()
                                        if val and val.lower() != "nan":
                                            # Format: "Question: Answer"
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
    try: df_temp = pd.DataFrame(leads_sheet.get_all_records()); status_opts = df_temp['Status'].unique() if 'Status' in df_temp.columns else []
    except: status_opts = []
    status_f = c_filter.multiselect("Filter", status_opts, key="status_f")
    show_live_leads_list(users_df, search_q, status_f)

# --- EXECUTION ---
if st.session_state['role'] == "Manager":
    t1, t2, t3 = st.tabs(["🏠 CRM", "📊 Insights", "⚙️ Admin"])
    with t1: show_dashboard(users_df)
    with t2: show_master_insights()
    with t3: show_admin(users_df)
else:
    show_dashboard(users_df)
