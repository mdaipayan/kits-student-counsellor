import streamlit as st
import database as db
import base64
import hashlib

st.set_page_config(page_title="Student Counsellor Portal", layout="wide", page_icon="🎓")

db.init_db()

if 'user' not in st.session_state:
    st.session_state.user = None

# ==========================================
# DEFAULT PASSWORDS (For First Time Login)
# ==========================================
STUDENT_PASSWORD = "student123"
COUNSELLOR_PASSWORD = "faculty123"

def hash_password(password):
    """Encrypts the password so it isn't stored as plain text."""
    return hashlib.sha256(password.encode()).hexdigest()

# ==========================================
# AUTHENTICATION LOGIC
# ==========================================
def login_page():
    st.title("🎓 KITS Student Counsellor Portal")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.write("### Secure Login")
        st.write("Please enter your credentials to access the portal.")
        
        with st.form("login_form"):
            name = st.text_input("Full Name (Only required for first login)")
            email = st.text_input("Email Address (Used as your ID)")
            role = st.selectbox("Role", ["Student", "Counsellor"])
            password = st.text_input("Password", type="password")
            
            submit = st.form_submit_button("Log In", type="primary", use_container_width=True)
            
            if submit:
                if not email or not password:
                    st.error("Please fill in Email and Password.")
                else:
                    email_clean = email.lower().strip()
                    user = db.get_user_by_email(email_clean)
                    
                    if not user:
                        # 1. NEW USER: Check against the default password
                        if not name:
                            st.error("Full Name is required for your first login.")
                        elif role == "Student" and password == STUDENT_PASSWORD:
                            st.session_state.user = db.create_initial_user(email_clean, name.strip(), role)
                            st.rerun()
                        elif role == "Counsellor" and password == COUNSELLOR_PASSWORD:
                            st.session_state.user = db.create_initial_user(email_clean, name.strip(), role)
                            st.rerun()
                        else:
                            st.error("Invalid credentials.")
                    else:
                        # 2. RETURNING USER: Check if they still need to change their password
                        if user['password_changed'] == 0:
                            if (role == "Student" and password == STUDENT_PASSWORD) or \
                               (role == "Counsellor" and password == COUNSELLOR_PASSWORD):
                                db.update_last_login(user['id'])
                                st.session_state.user = user
                                st.rerun()
                            else:
                                st.error("Invalid credentials.")
                        
                        # 3. VERIFIED USER: Check against their custom hashed password
                        else:
                            if user['password_hash'] == hash_password(password) and user['role'] == role:
                                db.update_last_login(user['id'])
                                st.session_state.user = user
                                st.rerun()
                            else:
                                st.error("Invalid credentials.")

def force_password_change():
    st.title("🔒 Set Your Personal Password")
    st.warning("Because this is your first time logging in, you are required to set a personal, secure password.")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("change_password_form"):
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm New Password", type="password")
            
            if st.form_submit_button("Update Password", type="primary", use_container_width=True):
                if len(new_password) < 6:
                    st.error("Password must be at least 6 characters long.")
                elif new_password != confirm_password:
                    st.error("Passwords do not match!")
                else:
                    db.update_user_password(st.session_state.user['id'], hash_password(new_password))
                    # Update the session state so they can proceed
                    st.session_state.user['password_changed'] = 1 
                    st.success("Password updated successfully!")
                    st.rerun()

def logout():
    st.session_state.user = None
    st.rerun()

# ==========================================
# STUDENT DASHBOARD
# ==========================================
def student_dashboard():
    user = st.session_state.user
    profile = db.get_student_profile(user['id'])
    
    if not profile:
        conn = db.connect()
        conn.execute("INSERT INTO student_profiles (user_id, status) VALUES (?, 'Draft')", (user['id'],))
        conn.commit()
        conn.close()
        st.rerun()
        
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
        st.write("**Profile Photo**")
        existing_photo = profile.get('photo')
        
        if existing_photo:
            st.image(base64.b64decode(existing_photo), width=150, caption="Current Photo")
            
        st.write("Update your photo using one of the methods below:")
        photo_col1, photo_col2 = st.columns(2)
        with photo_col1:
            uploaded_file = st.file_uploader("1. Upload a file", type=['jpg', 'jpeg', 'png'], disabled=is_disabled)
        with photo_col2:
            camera_photo = st.camera_input("2. Or use your camera", disabled=is_disabled)
            
        st.markdown("---")
        
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
                photo_data_to_save = existing_photo
                if camera_photo:
                    photo_data_to_save = base64.b64encode(camera_photo.getvalue()).decode('utf-8')
                elif uploaded_file:
                    photo_data_to_save = base64.b64encode(uploaded_file.getvalue()).decode('utf-8')

                form_data = {
                    "roll_no": roll_no, "branch": branch, "current_year": current_year,
                    "current_semester": current_semester, "phone": phone,
                    "parent_name": parent_name, "parent_phone": parent_phone,
                    "photo": photo_data_to_save
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
                img_col, info_col = st.columns([1, 4])
                
                with img_col:
                    if p.get('photo'):
                        st.image(base64.b64decode(p['photo']), use_container_width=True)
                    else:
                        st.info("No photo provided")
                        
                with info_col:
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

    st.markdown("---")
    st.subheader("✅ Verified Students (Manage Records)")
    verified_profiles = db.get_profiles_by_status('Verified')
    
    if not verified_profiles:
        st.info("No students have been verified yet.")
    else:
        for p in verified_profiles:
            with st.expander(f"Manage: {p['name']} ({p['roll_no']})"):
                col_img, col_info, col_action = st.columns([1, 3, 1])
                
                with col_img:
                    if p.get('photo'):
                        st.image(base64.b64decode(p['photo']), use_container_width=True)
                
                with col_info:
                    st.write(f"**Email:** {p['email']}")
                    st.write(f"**Branch/Year:** {p['branch']} - Year {p['current_year']}")
                    st.write(f"**Phone:** {p['phone']}")
                    
                with col_action:
                    if st.button("🗑️ Delete Record", key=f"delete_btn_{p['id']}", type="secondary"):
                        db.delete_student_record(user['id'], p['id'])
                        st.warning(f"Deleted profile for {p['name']}")
                        st.rerun()

# ==========================================
# MAIN ROUTING LOGIC
# ==========================================
def main():
    if not st.session_state.user:
        login_page()
    elif st.session_state.user['password_changed'] == 0:
        # Intercept the user and force them to change their password
        with st.sidebar:
            if st.button("Logout"):
                logout()
        force_password_change()
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
