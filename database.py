import sqlite3
from pathlib import Path
from datetime import datetime

# Updated to v4 for the expanded address and guardian schema
DB_PATH = Path("kits_counsellor_v4.db")

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = connect()
    conn.executescript("""
    -- 1. CENTRAL USERS TABLE
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'Student' CHECK(role IN ('Student', 'Counsellor', 'Admin')),
        password_hash TEXT, 
        password_changed INTEGER DEFAULT 0, 
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_login TEXT
    );

    -- 2. FULL STUDENT PROFILES (Expanded with Local Guardian & Hostel Info)
    CREATE TABLE IF NOT EXISTS student_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        
        -- Academic Info
        roll_no TEXT UNIQUE,
        branch TEXT,
        batch_year TEXT,
        current_year INTEGER CHECK(current_year BETWEEN 1 AND 4),
        current_semester INTEGER,
        cgpa REAL,
        
        -- Personal Info
        dob TEXT,
        gender TEXT,
        blood_group TEXT,
        
        -- Contact & Logistics
        phone TEXT,
        parent_name TEXT,
        parent_phone TEXT,
        
        -- Address & Living Data (NEW)
        address TEXT, -- Permanent Home Address
        hostel_status TEXT, -- 'Day Scholar' or 'Hosteller'
        local_address TEXT, -- For Day Scholars
        hostel_name TEXT, -- For Hostellers
        room_number TEXT, -- For Hostellers
        
        -- Local Guardian Data (NEW)
        local_guardian_name TEXT,
        local_guardian_phone TEXT,
        local_guardian_relation TEXT,
        
        -- Health
        medical_history TEXT,
        photo TEXT, 
        
        -- Workflow & Status
        status TEXT NOT NULL DEFAULT 'Draft' CHECK(status IN ('Draft', 'Submitted', 'Verified', 'Rejected')),
        counsellor_feedback TEXT, 
        assigned_counsellor_id INTEGER,
        risk_status TEXT NOT NULL DEFAULT 'Normal' CHECK(risk_status IN ('Normal', 'Watch', 'At Risk', 'Critical')),
        is_active INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(assigned_counsellor_id) REFERENCES users(id)
    );

    -- 3. COUNSELLING SESSIONS
    CREATE TABLE IF NOT EXISTS counselling_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_profile_id INTEGER NOT NULL,
        counsellor_id INTEGER NOT NULL,
        session_date TEXT NOT NULL,
        reason TEXT,
        student_concern TEXT,
        discussion TEXT,
        intervention TEXT,
        action_required TEXT,
        followup_date TEXT,
        status TEXT DEFAULT 'Open',
        FOREIGN KEY(student_profile_id) REFERENCES student_profiles(id),
        FOREIGN KEY(counsellor_id) REFERENCES users(id)
    );

    -- 4. ACADEMIC RECORDS
    CREATE TABLE IF NOT EXISTS academic_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_profile_id INTEGER NOT NULL,
        semester INTEGER NOT NULL,
        sgpa REAL,
        internal_average REAL,
        backlogs INTEGER DEFAULT 0,
        FOREIGN KEY(student_profile_id) REFERENCES student_profiles(id)
    );

    -- 5. ATTENDANCE RECORDS
    CREATE TABLE IF NOT EXISTS attendance_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_profile_id INTEGER NOT NULL,
        semester INTEGER NOT NULL,
        subject TEXT,
        attendance_percent REAL,
        FOREIGN KEY(student_profile_id) REFERENCES student_profiles(id)
    );

    -- 6. AUDIT LOGS
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        details TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    conn.commit()
    conn.close()

# ==========================================
# USER & AUTHENTICATION METHODS
# ==========================================
def get_user_by_email(email):
    conn = connect()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(user) if user else None

def create_initial_user(email, name, role):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (email, name, role, password_changed, last_login) VALUES (?, ?, ?, 0, ?)",
        (email, name, role, datetime.now().isoformat())
    )
    conn.commit()
    user_id = cursor.lastrowid
    
    if role == "Student":
        cursor.execute("INSERT INTO student_profiles (user_id, status) VALUES (?, 'Draft')", (user_id,))
        conn.commit()
        
    user = cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user)

def update_user_password(user_id, hashed_password):
    conn = connect()
    conn.execute("UPDATE users SET password_hash = ?, password_changed = 1 WHERE id = ?", (hashed_password, user_id))
    conn.commit()
    conn.close()

def update_last_login(user_id):
    conn = connect()
    conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

# ==========================================
# WORKFLOW METHODS 
# ==========================================
def get_student_profile(user_id):
    conn = connect()
    profile = conn.execute("SELECT * FROM student_profiles WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(profile) if profile else None

def save_student_draft(user_id, p_data):
    conn = connect()
    conn.execute("""
        UPDATE student_profiles 
        SET roll_no=?, branch=?, current_year=?, current_semester=?, cgpa=?,
            dob=?, gender=?, blood_group=?, 
            phone=?, parent_name=?, parent_phone=?, 
            address=?, hostel_status=?, local_address=?, hostel_name=?, room_number=?,
            local_guardian_name=?, local_guardian_phone=?, local_guardian_relation=?,
            medical_history=?, photo=?, updated_at=?
        WHERE user_id=?
    """, (
        p_data.get('roll_no'), p_data.get('branch'), p_data.get('current_year'), p_data.get('current_semester'), p_data.get('cgpa'),
        p_data.get('dob'), p_data.get('gender'), p_data.get('blood_group'), 
        p_data.get('phone'), p_data.get('parent_name'), p_data.get('parent_phone'), 
        p_data.get('address'), p_data.get('hostel_status'), p_data.get('local_address'), p_data.get('hostel_name'), p_data.get('room_number'),
        p_data.get('local_guardian_name'), p_data.get('local_guardian_phone'), p_data.get('local_guardian_relation'),
        p_data.get('medical_history'), p_data.get('photo'), datetime.now().isoformat(), user_id
    ))
    conn.execute("INSERT INTO audit_logs (user_id, action, details) VALUES (?, ?, ?)", 
                 (user_id, "SAVE_DRAFT", "Student saved profile draft"))
    conn.commit()
    conn.close()

def submit_student_profile(user_id):
    conn = connect()
    conn.execute("UPDATE student_profiles SET status = 'Submitted', updated_at = ? WHERE user_id = ?", 
                 (datetime.now().isoformat(), user_id))
    conn.execute("INSERT INTO audit_logs (user_id, action, details) VALUES (?, ?, ?)", 
                 (user_id, "SUBMIT_PROFILE", "Student submitted profile for review"))
    conn.commit()
    conn.close()

def review_student_profile(counsellor_id, profile_id, new_status, feedback=""):
    conn = connect()
    conn.execute("""
        UPDATE student_profiles 
        SET status=?, counsellor_feedback=?, assigned_counsellor_id=?, updated_at=? 
        WHERE id=?
    """, (new_status, feedback, counsellor_id, datetime.now().isoformat(), profile_id))
    conn.execute("INSERT INTO audit_logs (user_id, action, details) VALUES (?, ?, ?)", 
                 (counsellor_id, f"REVIEW_{new_status.upper()}", f"Profile {profile_id} {new_status}"))
    conn.commit()
    conn.close()

def delete_student_record(counsellor_id, profile_id):
    conn = connect()
    conn.execute("DELETE FROM counselling_sessions WHERE student_profile_id=?", (profile_id,))
    conn.execute("DELETE FROM academic_records WHERE student_profile_id=?", (profile_id,))
    conn.execute("DELETE FROM attendance_records WHERE student_profile_id=?", (profile_id,))
    conn.execute("DELETE FROM student_profiles WHERE id=?", (profile_id,))
    conn.execute("INSERT INTO audit_logs (user_id, action, details) VALUES (?, ?, ?)", 
                 (counsellor_id, "DELETE_PROFILE", f"Counsellor deleted profile ID {profile_id}"))
    conn.commit()
    conn.close()

def get_profiles_by_status(status):
    conn = connect()
    rows = conn.execute("""
        SELECT sp.*, u.name, u.email 
        FROM student_profiles sp
        JOIN users u ON sp.user_id = u.id
        WHERE sp.status = ?
        ORDER BY sp.updated_at DESC
    """, (status,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_counsellor_dashboard_stats():
    conn = connect()
    stats = {
        "pending_reviews": conn.execute("SELECT COUNT(*) FROM student_profiles WHERE status='Submitted'").fetchone()[0],
        "verified_students": conn.execute("SELECT COUNT(*) FROM student_profiles WHERE status='Verified' AND is_active=1").fetchone()[0],
        "drafts_in_progress": conn.execute("SELECT COUNT(*) FROM student_profiles WHERE status='Draft'").fetchone()[0],
        "at_risk": conn.execute("SELECT COUNT(*) FROM student_profiles WHERE status='Verified' AND risk_status IN ('At Risk', 'Critical')").fetchone()[0]
    }
    conn.close()
    return stats
