import streamlit as st
from datetime import date
import database as db

# 1. Check Authentication (Must be logged in)
if 'user' not in st.session_state or st.session_state.user is None:
    st.warning("🔒 Please log in from the main Home page first.")
    st.stop()

user = st.session_state.user

# ==========================================
# VIEW FOR STUDENTS (Read-Only History)
# ==========================================
if user['role'] == 'Student':
    st.title("🗣️ My Counselling Sessions")
    st.write("Here is the history of your counselling sessions and mentor advice.")
    
    conn = db.connect()
    # Find the student's profile ID
    profile = conn.execute("SELECT id FROM student_profiles WHERE user_id = ?", (user['id'],)).fetchone()
    
    if not profile:
        st.info("You haven't set up your profile yet. Head to the Home page to get started.")
        st.stop()
        
    sessions = conn.execute("""
        SELECT session_date, reason, discussion, intervention, action_required, followup_date, status 
        FROM counselling_sessions 
        WHERE student_profile_id = ? 
        ORDER BY session_date DESC
    """, (profile['id'],)).fetchall()
    conn.close()
    
    if not sessions:
        st.info("No counselling sessions recorded yet.")
    else:
        for s in sessions:
            with st.expander(f"📅 {s['session_date']} - Status: {s['status']}"):
                st.write(f"**Topics Discussed:** {s['reason']}")
                st.write(f"**Mentor Observation:** {s['discussion']}")
                st.write(f"**Advice / Intervention:** {s['intervention']}")
                st.write(f"**Action Required:** {s['action_required']}")
                if s['followup_date']:
                    st.info(f"🗓️ **Follow-up Scheduled For:** {s['followup_date']}")
    st.stop()

# ==========================================
# VIEW FOR COUNSELLORS (Log new sessions)
# ==========================================
st.title("🗣️ Record Counselling Session")

conn = db.connect()
# Get students who have submitted or verified profiles
students = conn.execute("""
    SELECT sp.id as profile_id, u.name, sp.roll_no 
    FROM student_profiles sp
    JOIN users u ON sp.user_id = u.id
    WHERE sp.status IN ('Submitted', 'Verified')
""").fetchall()
conn.close()

if not students:
    st.warning("No students are currently available for counselling. Students need to log in and submit their profiles first.")
    st.stop()

# Create a dropdown map of "Roll No — Name" -> Profile ID
student_map = {f"{s['roll_no']} — {s['name']}": s["profile_id"] for s in students}
selected = st.selectbox("Select Student", list(student_map.keys()))
student_profile_id = student_map[selected]

with st.form("session_form"):
    session_date = st.date_input("Session Date", date.today())
    reason = st.multiselect("Reason", [
        "Academic", "Attendance", "Behaviour", "Personal",
        "Financial", "Career", "Other"
    ])
    concern = st.text_area("Student's Concern")
    discussion = st.text_area("Discussion / Mentor Observation")
    intervention = st.text_area("Advice / Intervention")
    action = st.text_area("Action Required")
    followup = st.date_input("Follow-up Date", value=None)
    status = st.selectbox("Status", ["Open", "Monitoring", "Resolved"])
    
    save = st.form_submit_button("Save Counselling Session", type="primary")

    if save:
        conn = db.connect()
        conn.execute("""
            INSERT INTO counselling_sessions
            (student_profile_id, counsellor_id, session_date, reason, student_concern, discussion,
             intervention, action_required, followup_date, status)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (student_profile_id, user['id'], str(session_date), ", ".join(reason), concern,
              discussion, intervention, action,
              str(followup) if followup else None, status))
        conn.commit()
        conn.close()
        st.success("✅ Counselling session saved successfully.")
