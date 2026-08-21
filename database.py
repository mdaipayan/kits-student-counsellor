import psycopg2
import psycopg2.extras
import streamlit as st
from datetime import datetime

def connect():
    return psycopg2.connect(
        st.secrets["postgres"]["url"],
        cursor_factory=psycopg2.extras.RealDictCursor
    )

def init_db():
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'Student' CHECK(role IN ('Student', 'Counsellor', 'Admin')),
        password_hash TEXT, 
        password_changed INTEGER DEFAULT 0, 
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TEXT
    );

    CREATE TABLE IF NOT EXISTS student_profiles (
        id SERIAL PRIMARY KEY,
        user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        roll_no TEXT UNIQUE,
        branch TEXT,
        batch_year TEXT,
        current_year INTEGER CHECK(current_year BETWEEN 1 AND 4),
        current_semester INTEGER,
        cgpa REAL,
        dob TEXT,
        gender TEXT,
        blood_group TEXT,
        phone TEXT,
        parent_name TEXT,
        parent_phone TEXT,
        address TEXT,
        hostel_status TEXT,
        local_address TEXT,
        hostel_name TEXT,
        room_number TEXT,
        local_guardian_name TEXT,
        local_guardian_phone TEXT,
        local_guardian_relation TEXT,
        medical_history TEXT,
        photo TEXT,
        status TEXT NOT NULL DEFAULT 'Draft' CHECK(status IN ('Draft', 'Submitted', 'Verified', 'Rejected')),
        counsellor_feedback TEXT,
        assigned_counsellor_id INTEGER REFERENCES users(id),
        risk_status TEXT NOT NULL DEFAULT 'Normal' CHECK(risk_status IN ('Normal', 'Watch', 'At Risk', 'Critical')),
        is_active INTEGER NOT NULL DEFAULT 1,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS counselling_sessions (
        id SERIAL PRIMARY KEY,
        student_profile_id INTEGER NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
        counsellor_id INTEGER NOT NULL REFERENCES users(id),
        session_date TEXT NOT NULL,
        reason TEXT,
        student_concern TEXT,
        discussion TEXT,
        intervention TEXT,
        action_required TEXT,
        followup_date TEXT,
        status TEXT DEFAULT 'Open'
    );

    CREATE TABLE IF NOT EXISTS academic_records (
        id SERIAL PRIMARY KEY,
        student_profile_id INTEGER NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
        semester INTEGER NOT NULL,
        sgpa REAL,
        internal_average REAL,
        backlogs INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS attendance_records (
        id SERIAL PRIMARY KEY,
        student_profile_id INTEGER NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
        semester INTEGER NOT NULL,
        subject TEXT,
        attendance_percent REAL
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        action TEXT NOT NULL,
        details TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()

def get_user_by_email(email):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cur.fetchone()
    conn.close()
    return user

def create_initial_user(email, name, role):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (email, name, role, password_changed, last_login) VALUES (%s, %s, %s, 0, %s) RETURNING id",
        (email, name, role, datetime.now().isoformat())
    )
    user_id = cur.fetchone()['id']
    
    if role == "Student":
        cur.execute("INSERT INTO student_profiles (user_id, status) VALUES (%s, 'Draft')", (user_id,))
        
    conn.commit()
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    conn.close()
    return user

def update_user_password(user_id, hashed_password):
    conn = connect()
    cur = conn.cursor()
    cur.execute("UPDATE users SET password_hash = %s, password_changed = 1 WHERE id = %s", (hashed_password, user_id))
    conn.commit()
    conn.close()

def update_last_login(user_id):
    conn = connect()
    cur = conn.cursor()
    cur.execute("UPDATE users SET last_login = %s WHERE id = %s", (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

def get_student_profile(user_id):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM student_profiles WHERE user_id = %s", (user_id,))
    profile = cur.fetchone()
    conn.close()
    return profile
    
def create_blank_profile(user_id):
    conn = connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO student_profiles (user_id, status) VALUES (%s, 'Draft')", (user_id,))
    conn.commit()
    conn.close()

def save_student_draft(user_id, p_data):
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        UPDATE student_profiles 
        SET roll_no=%s, branch=%s, current_year=%s, current_semester=%s, cgpa=%s,
            dob=%s, gender=%s, blood_group=%s, 
            phone=%s, parent_name=%s, parent_phone=%s, 
            address=%s, hostel_status=%s, local_address=%s, hostel_name=%s, room_number=%s,
            local_guardian_name=%s, local_guardian_phone=%s, local_guardian_relation=%s,
            medical_history=%s, photo=%s, updated_at=%s
        WHERE user_id=%s
    """, (
        p_data.get('roll_no'), p_data.get('branch'), p_data.get('current_year'), p_data.get('current_semester'), p_data.get('cgpa'),
        p_data.get('dob'), p_data.get('gender'), p_data.get('blood_group'), 
        p_data.get('phone'), p_data.get('parent_name'), p_data.get('parent_phone'), 
        p_data.get('address'), p_data.get('hostel_status'), p_data.get('local_address'), p_data.get('hostel_name'), p_data.get('room_number'),
        p_data.get('local_guardian_name'), p_data.get('local_guardian_phone'), p_data.get('local_guardian_relation'),
        p_data.get('medical_history'), p_data.get('photo'), datetime.now().isoformat(), user_id
    ))
    cur.execute("INSERT INTO audit_logs (user_id, action, details) VALUES (%s, %s, %s)", 
                 (user_id, "SAVE_DRAFT", "Student saved profile draft"))
    conn.commit()
    conn.close()

def submit_student_profile(user_id):
    conn = connect()
    cur = conn.cursor()
    cur.execute("UPDATE student_profiles SET status = 'Submitted', updated_at = %s WHERE user_id = %s", 
                 (datetime.now().isoformat(), user_id))
    cur.execute("INSERT INTO audit_logs (user_id, action, details) VALUES (%s, %s, %s)", 
                 (user_id, "SUBMIT_PROFILE", "Student submitted profile for review"))
    conn.commit()
    conn.close()

def review_student_profile(counsellor_id, profile_id, new_status, feedback=""):
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        UPDATE student_profiles 
        SET status=%s, counsellor_feedback=%s, assigned_counsellor_id=%s, updated_at=%s 
        WHERE id=%s
    """, (new_status, feedback, counsellor_id, datetime.now().isoformat(), profile_id))
    cur.execute("INSERT INTO audit_logs (user_id, action, details) VALUES (%s, %s, %s)", 
                 (counsellor_id, f"REVIEW_{new_status.upper()}", f"Profile {profile_id} {new_status}"))
    conn.commit()
    conn.close()

def delete_student_record(counsellor_id, profile_id):
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM student_profiles WHERE id=%s", (profile_id,))
    cur.execute("INSERT INTO audit_logs (user_id, action, details) VALUES (%s, %s, %s)", 
                 (counsellor_id, "DELETE_PROFILE", f"Counsellor deleted profile ID {profile_id}"))
    conn.commit()
    conn.close()

def get_profiles_by_status(status):
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT sp.*, u.name, u.email 
        FROM student_profiles sp
        JOIN users u ON sp.user_id = u.id
        WHERE sp.status = %s
        ORDER BY sp.updated_at DESC
    """, (status,))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_counsellor_dashboard_stats():
    conn = connect()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) as count FROM student_profiles WHERE status='Submitted'")
    pending = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM student_profiles WHERE status='Verified' AND is_active=1")
    verified = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM student_profiles WHERE status='Draft'")
    drafts = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM student_profiles WHERE status='Verified' AND risk_status IN ('At Risk', 'Critical')")
    at_risk = cur.fetchone()['count']
    
    conn.close()
    return {
        "pending_reviews": pending,
        "verified_students": verified,
        "drafts_in_progress": drafts,
        "at_risk": at_risk
    }

def get_all_students():
    """Fetches every student in the database, regardless of their profile status."""
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.id as user_id, u.name, u.email, sp.roll_no, sp.branch, sp.current_year, sp.status
        FROM users u
        LEFT JOIN student_profiles sp ON u.id = sp.user_id
        WHERE u.role = 'Student'
        ORDER BY u.name ASC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def delete_student_completely(counsellor_id, student_user_id):
    """Wipes the user account. Postgres ON DELETE CASCADE will automatically erase their profile and sessions."""
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=%s", (student_user_id,))
    cur.execute("INSERT INTO audit_logs (user_id, action, details) VALUES (%s, %s, %s)", 
                 (counsellor_id, "DELETE_STUDENT", f"Deleted student user ID {student_user_id} completely"))
    conn.commit()
    conn.close()
