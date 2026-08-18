import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("kits_counsellor_prod.db") # New DB file for the clean slate

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys for SQLite
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = connect()
    conn.executescript("""
    -- 1. CENTRAL USERS TABLE (Handles Google Login & Roles)
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        google_id TEXT UNIQUE,
        email TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'Student' CHECK(role IN ('Student', 'Counsellor', 'Admin')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_login TEXT
    );

    -- 2. STUDENT PROFILES (Handles the Draft -> Submit -> Verify workflow)
    CREATE TABLE IF NOT EXISTS student_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        roll_no TEXT UNIQUE,
        branch TEXT,
        batch_year TEXT, -- e.g., '2024-2028' (Future-proofing)
        current_year INTEGER CHECK(current_year BETWEEN 1 AND 4),
        current_semester INTEGER,
        phone TEXT,
        parent_name TEXT,
        parent_phone TEXT,
        
        -- Workflow & Verification
        status TEXT NOT NULL DEFAULT 'Draft' CHECK(status IN ('Draft', 'Submitted', 'Verified', 'Rejected')),
        counsellor_feedback TEXT, 
        assigned_counsellor_id INTEGER,
        
        -- Counselling Status
        risk_status TEXT NOT NULL DEFAULT 'Normal' CHECK(risk_status IN ('Normal', 'Watch', 'At Risk', 'Critical')),
        is_active INTEGER NOT NULL DEFAULT 1,
        
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(assigned_counsellor_id) REFERENCES users(id)
    );

    -- 3. COUNSELLING SESSIONS (Updated to link Counsellor & Student)
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

    -- 6. AUDIT LOGS (For Admin tracking & security)
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
def get_or_create_user(email, name, google_id=None, role="Student"):
    """Used during Google Login to fetch or register a user."""
    conn = connect()
    cursor = conn.cursor()
    
    user = cursor.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    
    if not user:
        cursor.execute(
            "INSERT INTO users (google_id, email, name, role, last_login) VALUES (?, ?, ?, ?, ?)",
            (google_id, email, name, role, datetime.now().isoformat())
        )
        conn.commit()
        user = cursor.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        
        # If it's a student, initialize an empty draft profile
        if role == "Student":
            cursor.execute(
                "INSERT INTO student_profiles (user_id, status) VALUES (?, 'Draft')", 
                (user['id'],)
            )
            conn.commit()
    else:
        cursor.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.now().isoformat(), user['id']))
        conn.commit()
        
    conn.close()
    return dict(user)

# ==========================================
# WORKFLOW METHODS (Draft -> Submit -> Verify)
# ==========================================
def get_student_profile(user_id):
    conn = connect()
    profile = conn.execute("SELECT * FROM student_profiles WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(profile) if profile else None

def save_student_draft(user_id, profile_data):
    """Saves data without changing status (Student saves progress)."""
    conn = connect()
    conn.execute("""
        UPDATE student_profiles 
        SET roll_no=?, branch=?, current_year=?, current_semester=?, 
            phone=?, parent_name=?, parent_phone=?, updated_at=?
        WHERE user_id=?
    """, (
        profile_data.get('roll_no'), profile_data.get('branch'), 
        profile_data.get('current_year'), profile_data.get('current_semester'),
        profile_data.get('phone'), profile_data.get('parent_name'), 
        profile_data.get('parent_phone'), datetime.now().isoformat(), user_id
    ))
    
    # Log the action
    conn.execute("INSERT INTO audit_logs (user_id, action, details) VALUES (?, ?, ?)", 
                 (user_id, "SAVE_DRAFT", "Student saved profile draft"))
    
    conn.commit()
    conn.close()

def submit_student_profile(user_id):
    """Changes status from Draft/Rejected to Submitted."""
    conn = connect()
    conn.execute("UPDATE student_profiles SET status = 'Submitted', updated_at = ? WHERE user_id = ?", 
                 (datetime.now().isoformat(), user_id))
    conn.execute("INSERT INTO audit_logs (user_id, action, details) VALUES (?, ?, ?)", 
                 (user_id, "SUBMIT_PROFILE", "Student submitted profile for review"))
    conn.commit()
    conn.close()

def review_student_profile(counsellor_id, profile_id, new_status, feedback=""):
    """Counsellor approves or rejects a profile."""
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

# ==========================================
# COUNSELLOR DASHBOARD QUERIES
# ==========================================
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
