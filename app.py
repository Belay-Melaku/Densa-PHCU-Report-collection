import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import io

# --- PAGE CONFIG ---
st.set_page_config(page_title="Densa PHCU Reporting", layout="wide")

# --- 🔒 SECURITY CONFIGURATION (UPDATED) ---
# These are the exact logins you requested:
USERS = {
    "Admin": "admin1234",    # Administrator
    "Densa": "densa1234"     # Standard User
}

def check_password():
    """Returns `True` if the user had a correct password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["username"] in USERS and st.session_state["password"] == USERS[st.session_state["username"]]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show inputs
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        # Password incorrect, show input + error
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.error("😕 User not known or password incorrect")
        return False
    else:
        # Password correct
        return True

# --- MAIN APP LOGIC ---
if check_password():
    # EVERYTHING BELOW THIS LINE ONLY RUNS IF LOGGED IN
    
    # --- CONNECT TO GOOGLE SHEETS ---
    def get_google_sheet():
        try:
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
            client = gspread.authorize(creds)
            sheet_url = st.secrets["private_gsheets_url"]["url"]
            sheet = client.open_by_url(sheet_url).sheet1
            return sheet
        except Exception as e:
            st.error(f"❌ Connection Error: {e}")
            st.stop()

    # --- CONSTANTS ---
    INSTITUTIONS = [
        "Densa HC /Merged Health Post", "02 Densa Zuriya Health Post", 
        "03 Derew Health Post", "04 Wejed Health Post", "06 Gert Health Post",
        "07 Lenguat Health Post", "08 Alegeta Health Post", "09 Sensa Health Post"
    ]

    METRICS_GROUPS = {
        "Family Planning": [
            "All forms of Family planning accepted", "Long term Family planning accepted",
            "IUCD provided", "Immediate Postpartum Family Planning Service Provided"
        ],
        "Maternal Health": [
            "Pregnant women Screened", "ANC 1st contact service given",
            "ANC 4th contact service given", "ANC 8th contact service given",
            "Pregnant Mothers send to Health Center for skilled Birth", "Home Delivery happened",
            "Skilled Birth Attended", "Postnatal Care Service Provided",
            "Maternal conference conducted (1=Yes/0=No)", "number of Maternal conference participants"
        ],
        "Disease Prevention": [
            "Household visited", "Improved Latrine at visited household",
            "Unimproved Latrine at visited household", "presumptive TB case screened",
            "presumptive TB cases sent to HC for investigation"
        ],
        "Child Health": [
            "<5 children Treated for Pneumonia", "<5 children Treated for Diarrhea",
            "<5 children screened for acute malnutritional", "6–59 month children supplemented with Vitamin A",
            "24-29 month children Dewormed"
        ],
        "CBHI": [
            "CBHI membership renewal (higher paid)", "CBHI membership renewal (medium paid)",
            "CBHI membership renewal (free)", "CBHI new membership",
            "CBHI money collected (ETB)", "CBHI money saved to bank (ETB)"
        ]
    }

    ALL_METRICS = []
    for group in METRICS_GROUPS.values():
        ALL_METRICS.extend(group)

    # Sidebar Logout Button
    st.sidebar.success(f"👤 Logged in as: {st.session_state['username']}")
    if st.sidebar.button("Log Out"):
        del st.session_state["password_correct"]
        st.rerun()

    # --- APP NAVIGATION ---
    st.title("🏥 Densa PHCU Report System")
    page = st.sidebar.radio("Navigate", ["📝 Data Entry", "📊 Dashboard"])

    # PAGE 1: DATA ENTRY
    if page == "📝 Data Entry":
        st.header("Daily Activity Form")
        col1, col2, col3 = st.columns(3)
        with col1:
            report_date = st.date_input("Date of Report")
        with col2:
            reporter_name = st.text_input("Reporter Name (Required)")
        with col3:
            reporter_phone = st.text_input("Reporter Phone (Required)")
            
        institution = st.selectbox("Select Health Institution", INSTITUTIONS)
        
        if reporter_name and reporter_phone:
            with st.form("entry_form"):
                data_values = {}
                for category, indicators in METRICS_GROUPS.items():
                    st.subheader(f"🔹 {category}")
                    cols = st.columns(3)
                    for i, ind in enumerate(indicators):
                        data_values[ind] = cols[i%3].number_input(ind, min_value=0, step=1)
                
                submitted = st.form_submit_button("Submit Report")
                
                if submitted:
                    with st.spinner("Saving to Google Sheet..."):
                        sheet = get_google_sheet()
                        row_data = [str(report_date), reporter_name, reporter_phone, institution, str(datetime.now())]
                        for m in ALL_METRICS:
                            row_data.append(data_values.get(m, 0))
                        sheet.append_row(row_data)
                        st.success("✅ Report Submitted!")
        else:
            st.warning("⚠️ Enter Name and Phone to enable the form.")

    # PAGE 2: DASHBOARD
    elif page == "📊 Dashboard":
        st.header("Report Dashboard")
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()

        sheet = get_google_sheet()
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty:
            # Filters
            col1, col2 = st.columns(2)
            with col1:
                filter_inst = st.multiselect("Filter Institution", INSTITUTIONS)
            with col2:
                # Basic date filtering logic if needed
                pass 

            if filter_inst:
                df = df[df['Institution'].isin(filter_inst)]

            st.dataframe(df)

            # --- AUTOMATIC SUMMATION ---
            st.markdown("---")
            st.subheader("📈 Aggregated Totals")
            st.info("This table shows the SUM of all reports selected above.")
            
            numeric_df = df[ALL_METRICS]
            numeric_df = numeric_df.apply(pd.to_numeric, errors='coerce').fillna(0)
            
            total_row = numeric_df.sum().to_frame(name="TOTAL SUM")
            st.table(total_row)
            # -----------------------------------
            
            # Download
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False)
            st.download_button("📥 Download Report as Excel", data=output.getvalue(), file_name="Densa_Report.xlsx")
        else:
            st.info("No data found.")
