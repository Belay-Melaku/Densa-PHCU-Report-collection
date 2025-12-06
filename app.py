import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import io
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

# --- CONFIGURATION ---
st.set_page_config(page_title="Densa PHCU Reporting", layout="wide")

# Database Setup (SQLite)
conn = sqlite3.connect('densa_phcu_data.db', check_same_thread=False)
c = conn.cursor()

# Create table if not exists
def init_db():
    c.execute('''CREATE TABLE IF NOT EXISTS reports
                 (date TEXT, reporter_name TEXT, reporter_phone TEXT, 
                  institution TEXT, metrics TEXT, timestamp TEXT)''')
    conn.commit()

init_db()

# --- CONSTANTS ---
INSTITUTIONS = [
    "Densa HC /Merged Health Post", "02 Densa Zuriya Health Post", 
    "03 Derew Health Post", "04 Wejed Health Post", "06 Gert Health Post",
    "07 Lenguat Health Post", "08 Alegeta Health Post", "09 Sensa Health Post"
]

METRICS_GROUPS = {
    "Family Planning": [
        "All forms of Family planning accepted",
        "Long term Family planning accepted",
        "IUCD provided",
        "Immediate Postpartum Family Planning Service Provided"
    ],
    "Maternal Health (ANC/Delivery)": [
        "Pregnant women Screened",
        "ANC 1st contact service given",
        "ANC 4th contact service given",
        "ANC 8th contact service given",
        "Pregnant Mothers send to Health Center for skilled Birth",
        "Home Delivery happened",
        "Skilled Birth Attended",
        "Postnatal Care Service Provided",
        "Maternal conference conducted (Yes=1/No=0)",
        "number of Maternal conference participants"
    ],
    "Disease Prevention (TB/Hygiene)": [
        "Household visited",
        "Improved Latrine at visited household",
        "Unimproved Latrine at visited household",
        "presumptive TB case screened",
        "presumptive TB cases sent to HC for investigation"
    ],
    "Child Health (<5 years)": [
        "<5 children Treated for Pneumonia",
        "<5 children Treated for Diarrhea",
        "<5 children screened for acute malnutritional",
        "6–59 month children supplemented with Vitamin A",
        "24-29 month children Dewormed"
    ],
    "CBHI (Insurance)": [
        "CBHI membership renewal (higher paid)",
        "CBHI membership renewal (medium paid)",
        "CBHI membership renewal (free)",
        "CBHI new membership",
        "CBHI money collected (ETB)",
        "CBHI money saved to bank (ETB)"
    ]
}

# --- FUNCTIONS ---

def send_email_with_excel(df, recipient_email):
    # This requires a configured sender email (e.g., Gmail App Password)
    sender_email = "your_system_email@gmail.com" 
    sender_password = "your_app_password" # Use environment variables in production
    
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = f"Densa PHCU Report - {datetime.now().strftime('%Y-%m-%d')}"
    
    body = "Attached is the requested Densa PHCU data report."
    msg.attach(MIMEText(body, 'plain'))
    
    # Convert DF to Excel in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    output.seek(0)
    
    part = MIMEBase('application', "octet-stream")
    part.set_payload(output.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', 'attachment; filename="Densa_Report.xlsx"')
    msg.attach(part)
    
    try:
        # Note: This is a placeholder. Needs actual SMTP server setup to work.
        # server = smtplib.SMTP('smtp.gmail.com', 587)
        # server.starttls()
        # server.login(sender_email, sender_password)
        # server.sendmail(sender_email, recipient_email, msg.as_string())
        # server.quit()
        return True, "Email simulation successful (Configure SMTP for real sending)"
    except Exception as e:
        return False, str(e)

# --- UI LAYOUT ---

st.title("🏥 Densa PHCU Daily Report Collecting")
st.markdown("---")

# Sidebar for Navigation
page = st.sidebar.radio("Navigate", ["📝 New Data Entry", "📊 Dashboard & Reports", "📂 Excel Upload/Email"])

# ---------------- PAGE 1: DATA ENTRY ----------------
if page == "📝 New Data Entry":
    st.header("Daily Activity Form")
    
    # Mandatory Reporter Info
    col1, col2, col3 = st.columns(3)
    with col1:
        report_date = st.date_input("Date of Report")
    with col2:
        reporter_name = st.text_input("Reporter Full Name (Mandatory)")
    with col3:
        reporter_phone = st.text_input("Reporter Phone (Mandatory)")
        
    institution = st.selectbox("Select Health Institution", INSTITUTIONS)
    
    if reporter_name and reporter_phone:
        with st.form("entry_form"):
            data_payload = {}
            
            # Dynamic Form Generation based on Groups
            for category, indicators in METRICS_GROUPS.items():
                st.subheader(f"🔹 {category}")
                cols = st.columns(3)
                for i, ind in enumerate(indicators):
                    # Special logic for Maternal Conference
                    if ind == "Maternal conference conducted (Yes=1/No=0)":
                        val = cols[i%3].selectbox(ind, ["No", "Yes"])
                        data_payload[ind] = 1 if val == "Yes" else 0
                    elif ind == "number of Maternal conference participants":
                        # Only relevant if conference is yes, but we collect 0 otherwise
                        data_payload[ind] = cols[i%3].number_input(ind, min_value=0, step=1)
                    else:
                        data_payload[ind] = cols[i%3].number_input(ind, min_value=0, step=1)
            
            submitted = st.form_submit_button("Submit Report")
            
            if submitted:
                # Save to DB
                import json
                json_data = json.dumps(data_payload)
                c.execute("INSERT INTO reports VALUES (?, ?, ?, ?, ?, ?)", 
                          (report_date, reporter_name, reporter_phone, institution, json_data, datetime.now()))
                conn.commit()
                st.success(f"Report for {institution} submitted successfully!")
    else:
        st.warning("⚠️ Please enter your Name and Phone Number to proceed.")

# ---------------- PAGE 2: DASHBOARD ----------------
elif page == "📊 Dashboard & Reports":
    st.header("Data Analysis & Export")
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        filter_inst = st.multiselect("Filter by Institution", INSTITUTIONS)
    with col2:
        filter_date = st.date_input("Filter by Date", value=None)
        
    # Load Data
    df_raw = pd.read_sql_query("SELECT * FROM reports", conn)
    
    if not df_raw.empty:
        import json
        # Expand JSON metrics into columns
        metrics_list = []
        for index, row in df_raw.iterrows():
            m = json.loads(row['metrics'])
            m['Date'] = row['date']
            m['Institution'] = row['institution']
            m['Reporter'] = row['reporter_name']
            metrics_list.append(m)
            
        df_final = pd.DataFrame(metrics_list)
        
        # Apply Filters
        if filter_inst:
            df_final = df_final[df_final['Institution'].isin(filter_inst)]
        if filter_date:
            df_final['Date'] = pd.to_datetime(df_final['Date'])
            df_final = df_final[df_final['Date'].dt.date == filter_date]

        # CALCULATE TOTAL ROW (Automatic Summation)
        numeric_cols = df_final.select_dtypes(include='number').columns
        total_row = df_final[numeric_cols].sum().to_frame().T
        total_row['Institution'] = 'TOTAL (Aggregated)'
        total_row['Date'] = '---'
        total_row['Reporter'] = '---'
        
        # Combine
        df_display = pd.concat([df_final, total_row], ignore_index=True)
        
        st.dataframe(df_display, use_container_width=True)
        
        # Download Button
        st.download_button(
            label="Download Data as Excel",
            data=io.BytesIO(df_display.to_csv(index=False).encode()),
            file_name='densa_phcu_report.csv',
            mime='text/csv',
        )
    else:
        st.info("No data found in the system yet.")

# ---------------- PAGE 3: UPLOAD & EMAIL ----------------
elif page == "📂 Excel Upload/Email":
    st.header("Administrative Tools")
    
    tab1, tab2 = st.tabs(["Upload Excel Data", "Email Report"])
    
    with tab1:
        st.info("Upload an Excel file to bulk import data. Ensure column names match the metrics.")
        uploaded_file = st.file_uploader("Choose Excel File", type=['xlsx'])
        if uploaded_file:
            try:
                uploaded_df = pd.read_excel(uploaded_file)
                st.write("Preview:", uploaded_df.head())
                if st.button("Confirm Import"):
                    st.success("Data imported successfully! (Logic to parse and save to DB goes here)")
            except Exception as e:
                st.error(f"Error reading file: {e}")
                
    with tab2:
        st.write("Send the current aggregated report to `melakubelay47@gmail.com`")
        if st.button("Send Report Now"):
            # Fetch current data
            df_raw = pd.read_sql_query("SELECT * FROM reports", conn)
            # (Data processing same as above...)
            # For demo, we just simulate
            success, message = send_email_with_excel(df_raw, "melakubelay47@gmail.com")
            if success:
                st.success(message)
            else:
                st.error(f"Failed: {message}")
