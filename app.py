import streamlit as st
import database as db
import bcrypt
import uuid
import boto3
import pandas as pd
import io
from datetime import date


st.set_page_config(page_title="Student Counsellor Portal", layout="wide", page_icon="🎓")

db.init_db()

if 'user' not in st.session_state:
    st.session_state.user = None

STUDENT_PASSWORD = "student123"
COUNSELLOR_PASSWORD = "faculty123"

# --- NEW BCRYPT SECURITY FUNCTIONS ---
def hash_password(password):
    """Hashes a password using a secure bcrypt salt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password, hashed_password):
    """Verifies a plain password against the stored bcrypt hash."""
    if not hashed_password:
        return False
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def upload_photo_to_r2(file_bytes, mime_type="image/jpeg"):
    """Uploads photo to Cloudflare R2 and returns public URL."""
    s3 = boto3.client('s3',
        endpoint_url=st.secrets['r2']['endpoint'],
        aws_access_key_id=st.secrets['r2']['access_key'],
        aws_secret_access_key=st.secrets['r2']['secret_key']
    )
    file_name = f"profile_photos/{uuid.uuid4().hex}.jpg"
    s3.put_object(
        Bucket=st.secrets['r2']['bucket_name'], 
        Key=file_name, 
        Body=file_bytes, 
        ContentType=mime_type
    )
    return f"{st.secrets['r2']['public_url']}/{file_name}"

def login_page():
    st.title("🎓 Student Counsellor Portal")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.write("### Secure Login")
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
                        if user['password_changed'] == 0:
                            if (role == "Student" and password == STUDENT_PASSWORD) or \
                               (role == "Counsellor" and password == COUNSELLOR_PASSWORD):
                                db.update_last_login(user['id'])
                                st.session_state.user = user
                                st.rerun()
                            else:
                                st.error("Invalid credentials.")
                        else:
                            if verify_password(password, user['password_hash']) and user['role'] == role:
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
                    st.session_state.user['password_changed'] = 1 
                    st.success("Password updated successfully!")
                    st.rerun()

def logout():
    st.session_state.user = None
    st.rerun()

def student_dashboard():
    user = st.session_state.user
    profile = db.get_student_profile(user['id'])
    
    if not profile:
        db.create_blank_profile(user['id'])
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
        st.subheader("1. Profile Photo")
        existing_photo = profile.get('photo')
        if existing_photo:
            st.image(existing_photo, width=120)
            
        p1, p2 = st.columns(2)
        with p1: uploaded_file = st.file_uploader("Upload a file", type=['jpg', 'jpeg', 'png'], disabled=is_disabled)
        with p2: camera_photo = st.camera_input("Or use camera", disabled=is_disabled)
        st.markdown("---")
        
        st.subheader("2. Personal Details")
        c1, c2, c3 = st.columns(3)
        with c1:
            gender = st.selectbox("Gender", ["Male", "Female", "Other"], index=["Male", "Female", "Other"].index(profile.get('gender')) if profile.get('gender') in ["Male", "Female", "Other"] else 0, disabled=is_disabled)
            phone = st.text_input("Personal Phone", value=profile.get('phone') or "", disabled=is_disabled)
        with c2:
            try: def_dob = date.fromisoformat(profile.get('dob')) if profile.get('dob') else date(2005, 1, 1)
            except: def_dob = date(2005, 1, 1)
            dob = st.date_input("Date of Birth", value=def_dob, min_value=date(1990, 1, 1), max_value=date.today(), disabled=is_disabled)
        with c3:
            blood_group = st.selectbox("Blood Group", ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Unknown"], index=["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Unknown"].index(profile.get('blood_group')) if profile.get('blood_group') else 8, disabled=is_disabled)
        st.markdown("---")

        st.subheader("3. Academic Details")
        a1, a2, a3, a4 = st.columns(4)
        with a1: roll_no = st.text_input("Roll Number", value=profile.get('roll_no') or "", disabled=is_disabled)
        with a2: branch = st.selectbox("Branch", ["CSE", "ECE", "MECH", "CIVIL", "IT"], index=["CSE", "ECE", "MECH", "CIVIL", "IT"].index(profile.get('branch')) if profile.get('branch') else 0, disabled=is_disabled)
        with a3: current_year = st.number_input("Year", 1, 4, profile.get('current_year') or 1, disabled=is_disabled)
        with a4: current_semester = st.number_input("Semester", 1, 8, profile.get('current_semester') or 1, disabled=is_disabled)
        cgpa = st.number_input("Current CGPA", min_value=0.0, max_value=10.0, step=0.1, value=profile.get('cgpa') or 0.0, disabled=is_disabled)
        st.markdown("---")

        st.subheader("4. Address & Living Arrangements")
        hostel_status = st.selectbox("Are you a Day Scholar or Hosteller?", ["Day Scholar", "Hosteller"], index=["Day Scholar", "Hosteller"].index(profile.get('hostel_status')) if profile.get('hostel_status') in ["Day Scholar", "Hosteller"] else 0, disabled=is_disabled)
        
        ad1, ad2 = st.columns(2)
        with ad1: address = st.text_area("Permanent Home Address", value=profile.get('address') or "", disabled=is_disabled)
        with ad2: local_address = st.text_area("Local Address (Fill only if Day Scholar)", value=profile.get('local_address') or "", disabled=is_disabled)
            
        h1, h2 = st.columns(2)
        with h1: hostel_name = st.text_input("Hostel Name (Fill only if Hosteller)", value=profile.get('hostel_name') or "", disabled=is_disabled)
        with h2: room_number = st.text_input("Room Number (Fill only if Hosteller)", value=profile.get('room_number') or "", disabled=is_disabled)
        st.markdown("---")

        st.subheader("5. Guardian Details")
        f1, f2 = st.columns(2)
        with f1:
            parent_name = st.text_input("Parent/Permanent Guardian Name", value=profile.get('parent_name') or "", disabled=is_disabled)
            parent_phone = st.text_input("Parent Phone Number", value=profile.get('parent_phone') or "", disabled=is_disabled)
        with f2:
            local_guardian_name = st.text_input("Local Guardian Name", value=profile.get('local_guardian_name') or "", disabled=is_disabled)
            local_guardian_phone = st.text_input("Local Guardian Phone Number", value=profile.get('local_guardian_phone') or "", disabled=is_disabled)
            local_guardian_relation = st.text_input("Relationship to Local Guardian", value=profile.get('local_guardian_relation') or "", disabled=is_disabled)
        st.markdown("---")

        st.subheader("6. Health Details")
        medical_history = st.text_area("Medical History / Allergies", value=profile.get('medical_history') or "", disabled=is_disabled)
        st.markdown("---")

        if not is_disabled:
            col3, col4 = st.columns([1, 5])
            with col3: save_draft = st.form_submit_button("💾 Save Draft")
            with col4: submit_review = st.form_submit_button("🚀 Submit for Review", type="primary")
                
            if save_draft or submit_review:
                photo_data_to_save = existing_photo
                if camera_photo:
                    with st.spinner("Uploading photo to cloud..."):
                        photo_data_to_save = upload_photo_to_r2(camera_photo.getvalue())
                elif uploaded_file:
                    with st.spinner("Uploading photo to cloud..."):
                        photo_data_to_save = upload_photo_to_r2(uploaded_file.getvalue(), uploaded_file.type)

                form_data = {
                    "roll_no": roll_no, "branch": branch, "current_year": current_year, "current_semester": current_semester,
                    "cgpa": cgpa, "dob": str(dob), "gender": gender, "blood_group": blood_group, 
                    "phone": phone, "parent_name": parent_name, "parent_phone": parent_phone, 
                    "address": address, "hostel_status": hostel_status, "local_address": local_address, 
                    "hostel_name": hostel_name, "room_number": room_number,
                    "local_guardian_name": local_guardian_name, "local_guardian_phone": local_guardian_phone, "local_guardian_relation": local_guardian_relation,
                    "medical_history": medical_history, "photo": photo_data_to_save
                }
                
                db.save_student_draft(user['id'], form_data)
                
                if submit_review:
                    if not roll_no or not phone or not address:
                        st.error("Roll Number, Phone, and Permanent Address are required to submit.")
                    else:
                        db.submit_student_profile(user['id'])
                        st.success("Submitted successfully!")
                        st.rerun()
                else:
                    st.success("Draft saved!")
                    st.rerun()

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
    
    # 1. PENDING SUBMISSIONS
    st.subheader("📋 Pending Submissions")
    pending_profiles = db.get_profiles_by_status('Submitted')
    
    if not pending_profiles:
        st.success("No pending profiles to review.")
    else:
        for p in pending_profiles:
            with st.expander(f"Review: {p['name']} ({p['roll_no']}) - {p['branch']} Year {p['current_year']}"):
                t1, t2, t3, t4 = st.tabs(["Personal & Health", "Logistics & Guardians", "Academic", "Action"])
                with t1:
                    if p.get('photo'): st.image(p['photo'], width=150)
                    else: st.info("No photo")
                    st.write(f"**Email:** {p['email']} | **Phone:** {p['phone']}")
                    st.write(f"**DOB:** {p.get('dob')} | **Gender:** {p.get('gender')} | **Blood Group:** {p.get('blood_group')}")
                    st.write(f"**Medical History:** {p.get('medical_history')}")
                with t2:
                    st.write(f"**Permanent Address:** {p.get('address')}")
                    st.write(f"**Status:** {p.get('hostel_status')} | **Local Guardian:** {p.get('local_guardian_name')} ({p.get('local_guardian_phone')})")
                with t3:
                    st.write(f"**Branch/Year:** {p.get('branch')} - Year {p.get('current_year')} (Sem {p.get('current_semester')}) | **CGPA:** {p.get('cgpa')}")
                with t4:
                    with st.form(f"review_form_{p['id']}"):
                        feedback = st.text_area("Feedback/Notes", value=p.get('counsellor_feedback') or "")
                        c_a, c_b = st.columns(2)
                        with c_a:
                            if st.form_submit_button("✅ Approve & Verify", type="primary"):
                                db.review_student_profile(user['id'], p['id'], 'Verified', feedback)
                                st.rerun()
                        with c_b:
                            if st.form_submit_button("❌ Reject"):
                                db.review_student_profile(user['id'], p['id'], 'Rejected', feedback)
                                st.rerun()

    st.markdown("---")
    
    # 2. VERIFIED STUDENTS
    st.subheader("✅ Verified Students")
    verified_profiles = db.get_profiles_by_status('Verified')
    if not verified_profiles:
        st.info("No verified students yet.")
    else:
        for p in verified_profiles:
            with st.expander(f"View: {p['name']} ({p['roll_no']})"):
                if p.get('photo'): st.image(p['photo'], width=120)
                st.write(f"**Email:** {p['email']} | **Phone:** {p['phone']} | **Branch:** {p['branch']}")

    st.markdown("---")
    
    # 3. BULK EXCEL IMPORT
    st.subheader("📥 Bulk Onboard Students via Excel")
    st.info("Upload an Excel file to instantly create accounts for hundreds of students. Make sure your columns match the required template.")
    
    # ----------------------------------------------------
    # NEW: Download Sample Template Button
    # ----------------------------------------------------
    template_bytes = db.generate_excel_template()
    st.download_button(
        label="📥 Download Sample Excel Template",
        data=template_bytes,
        file_name="student_import_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help="Download this template, fill in your students' details, and upload it below."
    )
    
    st.markdown("---")
    
    uploaded_excel = st.file_uploader("Upload Filled Student Registry (.xlsx)", type=['xlsx'])
    if uploaded_excel:
        df = pd.read_excel(uploaded_excel)
        st.write("Preview of data to be imported:")
        st.dataframe(df.head())
        
        if st.button("🚀 Run Bulk Import", type="primary"):
            success, skipped = db.bulk_import_students(user['id'], df)
            st.success(f"Successfully imported {success} students. Skipped {skipped}.")
            st.rerun()
    
    # 4. SEARCH & REMOVE ANY STUDENT
    st.subheader("🔍 Search & Remove Any Student")
    all_students = db.get_all_students()
    if all_students:
        student_options = {f"{s['name']} - {s['roll_no'] or 'No Roll'} ({s['email']})": s['user_id'] for s in all_students}
        selected_student = st.selectbox("Select student to delete:", ["-- Select --"] + list(student_options.keys()))
        if selected_student != "-- Select --":
            if st.button("🗑️ Permanently Delete Student Account", type="primary"):
                db.delete_student_completely(user['id'], student_options[selected_student])
                st.success("Student removed.")
                st.rerun()

    # ----------------------------------------------------
    # SECTION 5: NAAC & NBA INSPECTION EXPORTS
    # ----------------------------------------------------
    st.markdown("---")
    st.subheader("📊 NAAC / NBA Compliance Reports")
    st.info("Download official, audit-ready summaries of all verified student files for accreditation committees.")
    
    col_pdf, col_excel = st.columns(2)
    
    with col_pdf:
        pdf_bytes = db.generate_naac_pdf()
        st.download_button(
            label="📄 Download NAAC PDF Report",
            data=pdf_bytes,
            file_name=f"NAAC_Counselling_Report_{date.today()}.pdf",
            mime="application/pdf",
            help="Generates an official PDF table of all verified student records."
        )
        
    with col_excel:
        verified_data = db.get_naac_export_data()
        if verified_data:
            df_export = pd.DataFrame(verified_data)
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Verified Students')
            
            st.download_button(
                label="📊 Download Full Excel Data",
                data=excel_buffer.getvalue(),
                file_name=f"Student_Directory_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Exports complete verified records into an editable Excel format."
            )

def main():
    if not st.session_state.user:
        login_page()
    elif st.session_state.user['password_changed'] == 0:
        with st.sidebar:
            if st.button("Logout"): logout()
        force_password_change()
    else:
        with st.sidebar:
            st.write(f"👤 **{st.session_state.user['name']}**")
            st.write(f"📧 {st.session_state.user['email']}")
            st.write(f"🏷️ Role: {st.session_state.user['role']}")
            if st.button("Logout"): logout()
        
        if st.session_state.user['role'] == 'Student':
            student_dashboard()
        elif st.session_state.user['role'] == 'Counsellor':
            counsellor_dashboard()

if __name__ == "__main__":
    main()
