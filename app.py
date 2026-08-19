import streamlit as st
import database as db

st.set_page_config(page_title="Student Counsellor Portal", layout="wide", page_icon="🎓")

db.init_db()

if 'user' not in st.session_state:
    st.session_state.user = None

# ==========================================
# SIMPLE AUTHENTICATION PASSWORDS
# Change these to whatever you want!
# ==========================================
STUDENT_PASSWORD = "1234"
COUNSELLOR_PASSWORD = "19860113"

# ==========================================
# AUTHENTICATION LOGIC
# ==========================================
def login_page():
    st.title("🎓 KITS Student Counsellor Portal")
    st.write("Welcome. Please log in to continue.")
    st.markdown("---")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        with st.form("login_form"):
            st.subheader("Login")
            
            # We still collect Name and Email so the database knows WHO is logging in
            name = st.text_input("Full Name")
            email = st.text_input("Email Address (Used as your ID)")
            role = st.selectbox("Role", ["Student", "Counsellor"])
            password = st.text_input("Password", type="password")
            
            submit = st.form_submit_button("Log In", type="primary")
            
            if submit:
                if not name or not email or not password:
                    st.error("Please fill in all fields.")
                elif role == "Student" and password != STUDENT_PASSWORD:
                    st.error("Incorrect Student password.")
                elif role == "Counsellor" and password != COUNSELLOR_PASSWORD:
                    st.error("Incorrect Counsellor password.")
                else:
                    # Passwords match! Create or fetch their profile in the DB
                    st.session_state.user = db.get_or_create_user(
                        email=email.lower().strip(), 
                        name=name.strip(), 
                        google_id=None,
                        role=role
                    )
                    st.rerun()
                    
    with col2:
        st.info(f"**Demo Passwords:**\n* Student Password: `{STUDENT_PASSWORD}`\n* Counsellor Password: `{COUNSELLOR_PASSWORD}`")

def logout():
    st.session_state.user = None
    st.rerun()

# ==========================================
# STUDENT DASHBOARD
# ==========================================
def student_dashboard():
    user = st.session_state.user
    profile = db.get_student_profile(user['id'])
    
    st.title(f"Welcome, {user['name']}")
    
    status = profile['status']
    if status == 'Draft':
        st.info("📝 Your profile is in Draft mode. Please fill out your details and submit.")
    elif status == 'Submitted':
        st.warning("⏳ Your profile is under review by a counsellor. You cannot edit it at this time.")
    elif status == 'Verified':
        st.success("✅ Your profile has been verified!")
    elif status == 'Rejected':
        st.error(f"❌ Your profile requires changes. Counsellor notes: {profile['counsellor_feedback']}")

    is_disabled = status in ['Submitted', 'Verified']
    
    with st.form("student_profile_form"):
        st.subheader("Personal & Academic Details")
        col1, col2 = st.columns(2)
        with col1:
            roll_no = st.text_input("Roll Number", value=profile.get('roll_no') or "", disabled=is_disabled)
            branch = st.selectbox("Branch", ["CSE", "ECE", "MECH", "CIVIL", "IT"], 
                                  index=["CSE", "ECE", "MECH", "CIVIL", "IT"].index(profile.get('branch')) if profile.get('branch') else 0,
                                  disabled=is_disabled)
            phone = st.text_input("Student Phone", value=profile.get('phone') or "", disabled=is_disabled)
        with col2:
            current_year = st.number_input("Current Year", min_value=1, max_value=4, value=profile.get('current_year') or 1, disabled=is_disabled)
            current_semester = st.number_input("Current Semester", min_value=1, max_value=8, value=profile.get('current_semester') or 1, disabled=is_disabled)
            parent_phone = st.text_input("Parent Phone", value=profile.get('parent_phone') or "", disabled=is_disabled)
            
        parent_name = st.text_input("Parent Name", value=profile.get('parent_name') or "", disabled=is_disabled)

        if not is_disabled:
            col3, col4 = st.columns([1, 5])
            with col3:
                save_draft = st.form_submit_button("💾 Save Draft")
            with col4:
                submit_review = st.form_submit_button("🚀 Submit for Review", type="primary")
                
            if save_draft or submit_review:
                form_data = {
                    "roll_no": roll_no, "branch": branch, "current_year": current_year,
                    "current_semester": current_semester, "phone": phone,
                    "parent_name": parent_name, "parent_phone": parent_phone
                }
                db.save_student_draft(user['id'], form_data)
                if submit_review:
                    if not roll_no or not phone:
                        st.error("Roll Number and Phone are required to submit.")
                    else:
                        db.submit_student_profile(user['id'])
                        st.success("Submitted successfully!")
                        st.rerun()
                else:
                    st.success("Draft saved!")
                    st.rerun()

# ==========================================
# COUNSELLOR DASHBOARD
# ==========================================
def counsellor_dashboard():
    user = st.session_state.user
    st.title("👨‍🏫 Counsellor Dashboard")
    
    stats = db.get_counsellor_dashboard_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pending Reviews", stats['pending_reviews'])
    c2.metric("Verified Students", stats['verified_students'])
    c3.metric("Drafts in Progress", stats['drafts_in_progress'])
    c4.metric("Students At Risk", stats['at_risk'])
    
    st.markdown("---")
    st.subheader("📋 Pending Submissions")
    pending_profiles = db.get_profiles_by_status('Submitted')
    
    if not pending_profiles:
        st.success("No pending profiles to review! Great job.")
    else:
        for p in pending_profiles:
            with st.expander(f"Review: {p['name']} ({p['roll_no']}) - {p['branch']} Year {p['current_year']}"):
                st.write(f"**Email:** {p['email']}")
                st.write(f"**Phone:** {p['phone']} | **Parent Phone:** {p['parent_phone']}")
                with st.form(f"review_form_{p['id']}"):
                    feedback = st.text_area("Feedback/Notes (Required if rejecting)", value=p.get('counsellor_feedback') or "")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("✅ Approve & Verify", type="primary"):
                            db.review_student_profile(user['id'], p['id'], 'Verified', feedback)
                            st.success("Profile Verified!")
                            st.rerun()
                    with col2:
                        if st.form_submit_button("❌ Reject (Send back to Draft)"):
                            if not feedback:
                                st.error("Please provide feedback so the student knows what to fix.")
                            else:
                                db.review_student_profile(user['id'], p['id'], 'Rejected', feedback)
                                st.success("Profile Rejected.")
                                st.rerun()

# ==========================================
# MAIN ROUTING LOGIC
# ==========================================
def main():
    if not st.session_state.user:
        login_page()
    else:
        with st.sidebar:
            st.write(f"👤 **{st.session_state.user['name']}**")
            st.write(f"📧 {st.session_state.user['email']}")
            st.write(f"🏷️ Role: {st.session_state.user['role']}")
            if st.button("Logout"):
                logout()
                
        if st.session_state.user['role'] == 'Student':
            student_dashboard()
        elif st.session_state.user['role'] == 'Counsellor':
            counsellor_dashboard()

if __name__ == "__main__":
    main()
