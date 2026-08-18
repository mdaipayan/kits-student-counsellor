import streamlit as st
import pandas as pd
import database as db

# 1. Check Authentication (Must be logged in)
if 'user' not in st.session_state or st.session_state.user is None:
    st.warning("🔒 Please log in from the main Home page first.")
    st.stop()

user = st.session_state.user

# 2. Check Role (Students shouldn't see aggregate reports)
if user['role'] == 'Student':
    st.error("🚫 Access Denied. Only Counsellors and Administrators can view reports.")
    st.stop()

st.title("📊 Analytics & Reports")
st.write("Comprehensive overview of student statuses and counselling interactions.")

# 3. Fetch data using the new schema
conn = db.connect()
rows = conn.execute("""
    SELECT 
        sp.roll_no as "Roll No", 
        u.name as "Name", 
        sp.branch as "Branch", 
        sp.current_year as "Year", 
        sp.risk_status as "Risk Status",
        COUNT(c.id) AS "Total Sessions"
    FROM student_profiles sp
    JOIN users u ON sp.user_id = u.id
    LEFT JOIN counselling_sessions c ON c.student_profile_id = sp.id
    WHERE sp.is_active = 1 AND sp.status IN ('Submitted', 'Verified')
    GROUP BY sp.id
    ORDER BY sp.current_year DESC, sp.roll_no
""").fetchall()
conn.close()

# 4. Display and Export
if rows:
    df = pd.DataFrame([dict(r) for r in rows])
    
    # Show summary metrics at the top
    st.subheader("Summary Metrics")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Students Tracked", len(df))
    col2.metric("Total Counselling Sessions", df["Total Sessions"].sum())
    col3.metric("Students At Risk", len(df[df["Risk Status"].isin(["At Risk", "Critical"])]))
    
    st.markdown("---")
    st.subheader("Detailed Report")
    
    # Display the table
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Download Button
    st.download_button(
        label="📥 Download Report as CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="kits_counselling_report.csv",
        mime="text/csv"
    )
else:
    st.info("No verified or submitted student data available to generate reports.")
