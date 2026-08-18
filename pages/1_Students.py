import streamlit as st
import database as db
import pandas as pd

# 1. Check Authentication (Must be logged in)
if 'user' not in st.session_state or st.session_state.user is None:
    st.warning("🔒 Please log in from the main Home page first.")
    st.stop()

user = st.session_state.user

# 2. Check Role (Students shouldn't see everyone's data)
if user['role'] == 'Student':
    st.error("🚫 Access Denied. Only Counsellors can view the student directory.")
    st.stop()

st.title("👥 Student Directory")
st.write("Overview of all student profiles in the system.")

# 3. Fetch all students directly from the new database tables
conn = db.connect()
rows = conn.execute("""
    SELECT 
        u.name as "Name", 
        sp.roll_no as "Roll No", 
        sp.branch as "Branch", 
        sp.current_year as "Year", 
        sp.status as "Workflow Status", 
        sp.risk_status as "Risk Level",
        u.email as "Email"
    FROM student_profiles sp
    JOIN users u ON sp.user_id = u.id
    ORDER BY sp.status, sp.current_year DESC
""").fetchall()
conn.close()

# 4. Display the data
if not rows:
    st.info("No student profiles have been created yet. Students need to log in and submit their profiles.")
else:
    # Convert to DataFrame for a nice Streamlit table
    df = pd.DataFrame([dict(r) for r in rows])
    
    # Add a filter to easily sort between Drafts, Submitted, and Verified students
    status_filter = st.selectbox("Filter by Status", ["All", "Verified", "Submitted", "Draft", "Rejected"])
    
    if status_filter != "All":
        df = df[df["Workflow Status"] == status_filter]
        
    st.dataframe(
        df, 
        use_container_width=True, 
        hide_index=True
    )
