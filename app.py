import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import io
import json

# --- PAGE CONFIG ---
st.set_page_config(page_title="Densa PHCU Reporting", layout="wide")

# --- CBHI PLAN DATA (STATIC) ---
# Plan for [higher paid, medium paid, free, new membership]
CBHI_PLAN = {
    "Densa HC /Merged Health Post": {"higher paid": 453, "medium paid": 551, "free": 474, "new membership": 251},
    "02 Densa Zuriya Health Post": {"higher paid": 147, "medium paid": 316, "free": 155, "new membership": 0},
    "03 Derew Health Post": {"higher paid": 456, "medium paid": 557, "free": 478, "new membership": 429},
    "04 Wejed Health Post": {"higher paid": 246, "medium paid": 346, "free": 249, "new membership": 0},
    "06 Gert Health Post": {"higher paid": 237, "medium paid": 298, "free": 255, "new membership": 22},
    "07 Lenguat Health Post": {"higher paid": 240, "medium paid": 328, "free": 244, "new membership": 0},
    "08 Alegeta Health Post": {"higher paid": 217, "medium paid": 252, "free": 248, "new membership": 22},
    "09 Sensa Health Post": {"higher paid": 173, "medium paid": 272, "free": 179, "new membership": 0}
}

# --- CONSTANTS ---
INSTITUTIONS = list(CBHI_PLAN.keys())

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
ALL_METRICS.append("Total CBHI (Auto)")


# --- GOOGLE SHEET CONNECTION (UPDATED TO USE json_key) ---
@st.cache_data(ttl=3600) # Cache data for 1 hour
def get_google_sheet():
    try:
        # Load the entire service account JSON from the single 'json_key' field
        json_info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        # Use the dictionary directly for authorization
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json_info, scope)
        client = gspread.authorize(creds)
        
        sheet_url = st.secrets["private_gsheets_url"]["url"]
        sheet = client.open_by_url(sheet_url).sheet1
        return sheet
    except Exception as e:
        # We handle the error here for better user feedback
        st.error(f"❌ Connection Error: {e}. Check Streamlit Secrets and Google Sheet sharing.")
        st.stop()


# --- MAIN APP LOGIC (NOW PUBLICLY ACCESSIBLE) ---
st.title("🏥 Densa PHCU Report System")
page = st.sidebar.radio("Navigate", ["📝 Data Entry", "📊 Dashboard", "📈 CBHI Performance Report"])

# ==========================================
# PAGE 1: DATA ENTRY
# ==========================================
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
                    # Skip the Auto-calculated metric in the form
                    if ind == "Total CBHI (Auto)": continue
                    data_values[ind] = cols[i%3].number_input(ind, min_value=0, step=1)
            
            submitted = st.form_submit_button("Submit Report")
            
            if submitted:
                with st.spinner("Saving to Google Sheet..."):
                    # --- CALCULATION: Total CBHI (Sum of 4 membership types) ---
                    total_cbhi = (
                        data_values.get("CBHI membership renewal (higher paid)", 0) +
                        data_values.get("CBHI membership renewal (medium paid)", 0) +
                        data_values.get("CBHI membership renewal (free)", 0) +
                        data_values.get("CBHI new membership", 0)
                    )
                    data_values["Total CBHI (Auto)"] = total_cbhi
                    # -----------------------------------------------------------

                    sheet = get_google_sheet()
                    row_data = [str(report_date), reporter_name, reporter_phone, institution, str(datetime.now())]
                    for m in ALL_METRICS:
                        row_data.append(data_values.get(m, 0))
                    
                    sheet.append_row(row_data)
                    # Clear cache to ensure dashboard sees the new data immediately
                    st.cache_data.clear() 
                    st.success(f"✅ Report Submitted! Total CBHI calculated: {total_cbhi}")
    else:
        st.warning("⚠️ Enter Name and Phone to enable the form.")

# ==========================================
# PAGE 2: GENERAL DASHBOARD
# ==========================================
elif page == "📊 Dashboard":
    st.header("General Daily Report Dashboard")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()

    sheet = get_google_sheet()
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    if not df.empty:
        df.columns = [c.strip() for c in df.columns] 
        
        col1, col2 = st.columns(2)
        with col1:
            filter_inst = st.multiselect("Filter Institution", INSTITUTIONS)
        with col2:
            # Placeholder for date filtering
            pass 

        df_filtered = df
        if filter_inst:
            df_filtered = df[df['Institution'].isin(filter_inst)]

        st.dataframe(df_filtered, use_container_width=True)

        # --- AUTOMATIC SUMMATION ---
        st.markdown("---")
        st.subheader("📈 Aggregated Totals")
        st.info("This table shows the SUM of all reports currently displayed (filtered or total).")
        
        sum_metrics = [m for m in ALL_METRICS if "money" not in m] # Exclude money fields from general summation
        
        numeric_df = df_filtered[sum_metrics]
        numeric_df = numeric_df.apply(pd.to_numeric, errors='coerce').fillna(0)
        
        total_row = numeric_df.sum().to_frame(name="TOTAL SUM")
        st.table(total_row)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_filtered.to_excel(writer, index=False)
        st.download_button("📥 Download Report as Excel", data=output.getvalue(), file_name="Densa_Report.xlsx")
    else:
        st.info("No data found.")

# ==========================================
# PAGE 3: CBHI PERFORMANCE REPORT
# ==========================================
elif page == "📈 CBHI Performance Report":
    st.header("CBHI Performance Analysis (Plan vs. Achievement)")
    st.info("This report aggregates all submitted data to measure performance against the static plan.")

    sheet = get_google_sheet()
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    if df.empty:
        st.warning("No data submitted yet to generate the performance report.")
        st.stop()

    # 1. AGGREGATE ACHIEVEMENT (SUM)
    cbhi_achievement_cols = [
        "CBHI membership renewal (higher paid)", "CBHI membership renewal (medium paid)", 
        "CBHI membership renewal (free)", "CBHI new membership"
    ]
    
    df_achieved = df.copy()
    df_achieved[cbhi_achievement_cols] = df_achieved[cbhi_achievement_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
    
    df_aggregated = df_achieved.groupby('Institution')[cbhi_achievement_cols].sum().reset_index()
    df_aggregated.rename(columns={
        'CBHI membership renewal (higher paid)': 'Achieved Higher Paid',
        'CBHI membership renewal (medium paid)': 'Achieved Medium Paid',
        'CBHI membership renewal (free)': 'Achieved Free',
        'CBHI new membership': 'Achieved New Membership'
    }, inplace=True)

    # 2. PREPARE PLAN DATA
    plan_data = pd.DataFrame([
        {'Institution': k, 
         'Plan Higher Paid': v['higher paid'],
         'Plan Medium Paid': v['medium paid'],
         'Plan Free': v['free'],
         'Plan New Membership': v['new membership']}
        for k, v in CBHI_PLAN.items()
    ])
    
    # 3. MERGE AND CALCULATE
    df_final = pd.merge(plan_data, df_aggregated, on='Institution', how='left').fillna(0)
    
    df_final['Total Plan'] = df_final['Plan Higher Paid'] + df_final['Plan Medium Paid'] + df_final['Plan Free'] + df_final['Plan New Membership']
    df_final['Total Achieved'] = df_final['Achieved Higher Paid'] + df_final['Achieved Medium Paid'] + df_final['Achieved Free'] + df_final['Achieved New Membership']

    df_final['Performance %'] = (df_final['Total Achieved'] / df_final['Total Plan']) * 100
    df_final['Performance %'] = df_final['Performance %'].apply(lambda x: f"{x:,.1f}%")

    # 4. DISPLAY
    display_cols = ['Institution', 'Total Plan', 'Total Achieved', 'Performance %',
                    'Plan Higher Paid', 'Achieved Higher Paid', 'Plan Medium Paid', 
                    'Achieved Medium Paid', 'Plan Free', 'Achieved Free', 
                    'Plan New Membership', 'Achieved New Membership']
    
    st.dataframe(df_final[display_cols], use_container_width=True)
    
    csv = df_final.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download CBHI Performance Report",
        data=csv,
        file_name="CBHI_Performance_Report.csv",
        mime="text/csv"
    )
