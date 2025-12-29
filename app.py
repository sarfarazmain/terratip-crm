import streamlit as st
import pandas as pd
import datetime

# -----------------------------------------------------------------------------
# 1. APP CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="TerraTip CRM",
    page_icon="🏡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -----------------------------------------------------------------------------
# 2. SESSION STATE & MOCK DATA SETUP
# -----------------------------------------------------------------------------
# We create some dummy data to ensure the app runs immediately.
if "users_df" not in st.session_state:
    data = {
        'Username': ['admin', 'sales1'],
        'Role': ['Manager', 'Sales Executive'],
        'Name': ['System Admin', 'Amit Kumar']
    }
    st.session_state.users_df = pd.DataFrame(data)

if "leads_data" not in st.session_state:
    # Creating an empty dataframe with columns for real estate leads
    st.session_state.leads_data = pd.DataFrame(columns=[
        "Date", "Name", "Phone", "Status", "Source", "Budget", "Interest", "Notes"
    ])

# -----------------------------------------------------------------------------
# 3. HELPER FUNCTIONS (The Fix for NameError)
# -----------------------------------------------------------------------------

def show_feedback():
    """
    Displays a small feedback widget (Placeholder for the missing function).
    """
    with st.expander("📢 System Feedback / Report Bug"):
        st.write("Found an issue? Let us know.")
        st.text_area("Describe the issue", height=70)
        st.button("Submit Feedback")

def show_add_lead_form(users_df):
    """
    Displays the form to add a new Real Estate lead.
    """
    st.markdown("### ➕ Add New Lead")
    
    with st.form("add_lead_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            name = st.text_input("Client Name", placeholder="e.g. Rahul Singh")
            phone = st.text_input("Phone Number", placeholder="+91...")
            
        with col2:
            source = st.selectbox("Source", ["Instagram Ads", "Facebook", "Referral", "Cold Call", "Walk-in"])
            status = st.selectbox("Status", ["New", "Follow-up", "Site Visit Scheduled", "Negotiation", "Closed"])
            
        with col3:
            budget = st.number_input("Budget (Lakhs)", min_value=0.0, step=0.5)
            assign_to = st.selectbox("Assign To", users_df['Name'].unique())

        interest = st.text_input("Property Interest (e.g. 1000 sqft Plot, Corner)")
        notes = st.text_area("Initial Notes / Requirements")
        
        submitted = st.form_submit_button("Save Lead", use_container_width=True)
        
        if submitted:
            # Create a new record
            new_lead = {
                "Date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Name": name,
                "Phone": phone,
                "Status": status,
                "Source": source,
                "Budget": budget,
                "Interest": interest,
                "Notes": notes
            }
            # Append to session state dataframe
            st.session_state.leads_data = pd.concat(
                [st.session_state.leads_data, pd.DataFrame([new_lead])], 
                ignore_index=True
            )
            st.success(f"✅ Lead '{name}' added successfully!")

def show_recent_leads():
    """
    Displays the list of recent leads below the form.
    """
    st.divider()
    st.subheader("📋 Recent Leads")
    if not st.session_state.leads_data.empty:
        st.dataframe(st.session_state.leads_data, use_container_width=True)
    else:
        st.info("No leads found. Add a lead above to get started.")

# -----------------------------------------------------------------------------
# 4. DASHBOARD LOGIC
# -----------------------------------------------------------------------------

def show_dashboard(users_df):
    """
    Main dashboard view.
    This was the function causing the error in your screenshot.
    """
    # 1. Show Feedback widget
    show_feedback()
    
    # 2. Show Add Lead Form
    show_add_lead_form(users_df)
    
    # 3. Divider and List
    show_recent_leads()

def show_insights():
    st.header("📊 Insights")
    st.info("Analytics module coming soon.")

def show_admin():
    st.header("⚙️ Admin Panel")
    st.write("Manage users and settings here.")

# -----------------------------------------------------------------------------
# 5. MAIN APP EXECUTION
# -----------------------------------------------------------------------------

def main():
    # Top Bar / Header
    col_logo, col_spacer, col_user = st.columns([1, 4, 2])
    with col_logo:
        st.title("🏡 TerraTip CRM")
    with col_user:
        st.write("") # Spacer
        st.write(f"👤 **System Admin (Manager)**")
        if st.button("Logout"):
            st.rerun()

    st.markdown("---")

    # Menu Tabs (Matching your screenshot: CRM | Insights | Admin)
    tab1, tab2, tab3 = st.tabs(["🏠 CRM", "📊 Insights", "⚙️ Admin"])

    with tab1:
        # Pass the users dataframe to the dashboard
        show_dashboard(st.session_state.users_df)

    with tab2:
        show_insights()

    with tab3:
        show_admin()

if __name__ == "__main__":
    main()
