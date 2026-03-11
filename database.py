import sqlite3
import json
from datetime import datetime
import hashlib
import os

DB_PATH = "sbd_portal.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'project_member',
        created_at TEXT NOT NULL,
        is_active INTEGER DEFAULT 1
    )
    """)
    
    # Questions table (managed by admin)
    c.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        description TEXT,
        question_type TEXT DEFAULT 'single_choice',
        options TEXT,
        weights TEXT,
        max_score INTEGER DEFAULT 10,
        category TEXT DEFAULT 'General',
        is_active INTEGER DEFAULT 1,
        order_index INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)
    
    # SBD Thresholds config
    c.execute("""
    CREATE TABLE IF NOT EXISTS sbd_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)
    
    # Requests table
    c.execute("""
    CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ref_number TEXT UNIQUE NOT NULL,
        project_name TEXT NOT NULL,
        project_description TEXT,
        created_by INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending_review',
        sbd_outcome TEXT,
        total_score REAL DEFAULT 0,
        architect_id INTEGER,
        architect_url TEXT,
        architect_notes TEXT,
        engineer_id INTEGER,
        assurance_id INTEGER,
        signoff_by INTEGER,
        is_locked INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        submitted_at TEXT,
        review_started_at TEXT,
        awaiting_assignment_at TEXT,
        architect_assigned_at TEXT,
        architect_completed_at TEXT,
        engineer_assigned_at TEXT,
        engineer_completed_at TEXT,
        assurance_assigned_at TEXT,
        assurance_completed_at TEXT,
        pending_signoff_at TEXT,
        signoff_received_at TEXT,
        FOREIGN KEY (created_by) REFERENCES users(id)
    )
    """)
    
    # Request answers
    c.execute("""
    CREATE TABLE IF NOT EXISTS request_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        answer TEXT NOT NULL,
        score REAL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (request_id) REFERENCES requests(id),
        FOREIGN KEY (question_id) REFERENCES questions(id)
    )
    """)
    
    # Request permissions (sharing)
    c.execute("""
    CREATE TABLE IF NOT EXISTS request_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        permission TEXT NOT NULL DEFAULT 'read',
        granted_by INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(request_id, user_id),
        FOREIGN KEY (request_id) REFERENCES requests(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)
    
    # Audit trail / status history
    c.execute("""
    CREATE TABLE IF NOT EXISTS status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL,
        from_status TEXT,
        to_status TEXT NOT NULL,
        changed_by INTEGER NOT NULL,
        notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (request_id) REFERENCES requests(id),
        FOREIGN KEY (changed_by) REFERENCES users(id)
    )
    """)
    
    conn.commit()
    
    # Seed default admin and users if not exist
    _seed_default_data(conn)
    
    conn.close()

def _seed_default_data(conn):
    c = conn.cursor()
    now = datetime.now().isoformat()
    
    # Default users
    default_users = [
        ("admin", "admin123", "System Admin", "admin@company.com", "admin"),
        ("sbd_manager", "manager123", "SbD Manager", "sbdmanager@company.com", "sbd_manager"),
        ("architect1", "arch123", "Alice Chen", "alice@company.com", "security_architect"),
        ("engineer1", "eng123", "Bob Smith", "bob@company.com", "security_engineer"),
        ("assurance1", "assur123", "Carol Davis", "carol@company.com", "assurance"),
        ("user1", "user123", "David Johnson", "david@company.com", "project_member"),
        ("user2", "user123", "Eve Wilson", "eve@company.com", "project_member"),
    ]
    
    for username, password, name, email, role in default_users:
        ph = hashlib.sha256(password.encode()).hexdigest()
        try:
            c.execute("""INSERT OR IGNORE INTO users (username, password_hash, name, email, role, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)""", (username, ph, name, email, role, now))
        except:
            pass
    
    # Default questions
    default_questions = [
        (
            "Does your project process, store, or transmit personal data (PII)?",
            "Personal Identifiable Information includes names, addresses, emails, etc.",
            "single_choice",
            json.dumps(["No", "Yes - minimal (name/email only)", "Yes - moderate (financial/health)", "Yes - extensive (sensitive categories)"]),
            json.dumps([0, 3, 7, 10]),
            10, "Data Privacy", 1
        ),
        (
            "What is the expected user base size?",
            "Approximate number of end users who will interact with the system.",
            "single_choice",
            json.dumps(["Internal only (<50 users)", "Small (<500 users)", "Medium (500-10,000)", "Large (>10,000 users)"]),
            json.dumps([0, 2, 5, 8]),
            8, "Scale & Exposure", 2
        ),
        (
            "Does the project involve external-facing components or APIs?",
            "Any components accessible from outside the corporate network.",
            "single_choice",
            json.dumps(["No, fully internal", "Limited internal API", "External API with auth", "Public-facing web/API"]),
            json.dumps([0, 2, 6, 10]),
            10, "Exposure", 3
        ),
        (
            "Does the project handle financial transactions or payment data?",
            "Includes card payments, bank transfers, financial records.",
            "single_choice",
            json.dumps(["No", "Indirect reference only", "Yes - internal transfers", "Yes - direct card/payment processing"]),
            json.dumps([0, 3, 7, 10]),
            10, "Financial Risk", 4
        ),
        (
            "What level of authentication does the system require?",
            "How users will verify their identity to access the system.",
            "single_choice",
            json.dumps(["No authentication required", "Username/password only", "MFA supported", "MFA mandatory + SSO"]),
            json.dumps([8, 5, 2, 0]),
            8, "Authentication", 5
        ),
        (
            "Does the project integrate with third-party systems or vendors?",
            "External APIs, SaaS products, data feeds from outside your organisation.",
            "single_choice",
            json.dumps(["No integrations", "1-2 trusted internal systems", "Several external systems", "Many external/untrusted systems"]),
            json.dumps([0, 2, 6, 10]),
            10, "Third-party Risk", 6
        ),
        (
            "What is the classification of data handled by the project?",
            "Based on your organisation's data classification policy.",
            "single_choice",
            json.dumps(["Public", "Internal use only", "Confidential", "Highly Confidential / Restricted"]),
            json.dumps([0, 2, 6, 10]),
            10, "Data Classification", 7
        ),
        (
            "What is the regulatory/compliance requirement for this project?",
            "E.g. GDPR, PCI-DSS, HIPAA, SOX, ISO27001.",
            "single_choice",
            json.dumps(["None identified", "General data protection", "Industry-specific (PCI/HIPAA)", "Multiple strict regulations"]),
            json.dumps([0, 3, 7, 10]),
            10, "Compliance", 8
        ),
    ]
    
    for q in default_questions:
        try:
            c.execute("""INSERT OR IGNORE INTO questions 
                        (text, description, question_type, options, weights, max_score, category, order_index, is_active, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                     (*q, now, now))
        except:
            pass
    
    # Default SBD config thresholds
    configs = [
        ("threshold_no_sbd", "20"),
        ("threshold_stage1", "40"),
        ("threshold_stage2", "65"),
        ("threshold_full_sbd", "100"),
    ]
    for key, value in configs:
        try:
            c.execute("INSERT OR IGNORE INTO sbd_config (key, value, updated_at) VALUES (?, ?, ?)", (key, value, now))
        except:
            pass
    
    conn.commit()

# ---- CRUD helpers ----

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_user_by_username(username):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE username=? AND is_active=1", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(user_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_users(role=None):
    conn = get_connection()
    if role:
        rows = conn.execute("SELECT * FROM users WHERE role=? AND is_active=1", (role,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM users WHERE is_active=1").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_user(username, password, name, email, role):
    conn = get_connection()
    now = datetime.now().isoformat()
    ph = hash_password(password)
    try:
        conn.execute("INSERT INTO users (username, password_hash, name, email, role, created_at) VALUES (?,?,?,?,?,?)",
                    (username, ph, name, email, role, now))
        conn.commit()
        return True, "User created"
    except sqlite3.IntegrityError:
        return False, "Username already exists"
    finally:
        conn.close()

def update_user_role(user_id, role):
    conn = get_connection()
    now = datetime.now().isoformat()
    conn.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
    conn.commit()
    conn.close()

def deactivate_user(user_id):
    conn = get_connection()
    conn.execute("UPDATE users SET is_active=0 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

def get_active_questions():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM questions WHERE is_active=1 ORDER BY order_index, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_questions():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM questions ORDER BY order_index, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_question(text, description, question_type, options, weights, max_score, category, order_index):
    conn = get_connection()
    now = datetime.now().isoformat()
    conn.execute("""INSERT INTO questions (text, description, question_type, options, weights, max_score, category, order_index, is_active, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,1,?,?)""",
                (text, description, question_type, json.dumps(options), json.dumps(weights), max_score, category, order_index, now, now))
    conn.commit()
    conn.close()

def update_question(q_id, text, description, options, weights, max_score, category, order_index, is_active):
    conn = get_connection()
    now = datetime.now().isoformat()
    conn.execute("""UPDATE questions SET text=?, description=?, options=?, weights=?, max_score=?, category=?, 
                   order_index=?, is_active=?, updated_at=? WHERE id=?""",
                (text, description, json.dumps(options), json.dumps(weights), max_score, category, order_index, is_active, now, q_id))
    conn.commit()
    conn.close()

def delete_question(q_id):
    conn = get_connection()
    conn.execute("UPDATE questions SET is_active=0 WHERE id=?", (q_id,))
    conn.commit()
    conn.close()

def get_sbd_config():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM sbd_config").fetchall()
    conn.close()
    return {r['key']: r['value'] for r in rows}

def update_sbd_config(key, value):
    conn = get_connection()
    now = datetime.now().isoformat()
    conn.execute("INSERT OR REPLACE INTO sbd_config (key, value, updated_at) VALUES (?,?,?)", (key, value, now))
    conn.commit()
    conn.close()

def generate_ref_number():
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
    conn.close()
    year = datetime.now().year
    return f"SBD-{year}-{str(count+1).zfill(4)}"

def create_request(project_name, description, created_by):
    conn = get_connection()
    now = datetime.now().isoformat()
    ref = generate_ref_number()
    conn.execute("""INSERT INTO requests (ref_number, project_name, project_description, created_by, status, created_at, updated_at, submitted_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (ref, project_name, description, created_by, 'pending_review', now, now, now))
    conn.commit()
    req_id = conn.execute("SELECT id FROM requests WHERE ref_number=?", (ref,)).fetchone()[0]
    # Log status
    conn.execute("INSERT INTO status_history (request_id, from_status, to_status, changed_by, notes, created_at) VALUES (?,?,?,?,?,?)",
                (req_id, None, 'pending_review', created_by, 'Request submitted', now))
    conn.commit()
    conn.close()
    return req_id, ref

def save_answers(request_id, answers_dict):
    """answers_dict: {question_id: {'answer': str, 'score': float}}"""
    conn = get_connection()
    now = datetime.now().isoformat()
    conn.execute("DELETE FROM request_answers WHERE request_id=?", (request_id,))
    total_score = 0
    for qid, ans_data in answers_dict.items():
        conn.execute("INSERT INTO request_answers (request_id, question_id, answer, score, created_at) VALUES (?,?,?,?,?)",
                    (request_id, qid, ans_data['answer'], ans_data['score'], now))
        total_score += ans_data['score']
    # Update total score on request
    conn.execute("UPDATE requests SET total_score=?, updated_at=? WHERE id=?", (total_score, now, request_id))
    conn.commit()
    conn.close()
    return total_score

def determine_sbd_outcome(total_score, max_possible_score, config):
    if max_possible_score == 0:
        return "no_sbd"
    pct = (total_score / max_possible_score) * 100
    t1 = float(config.get('threshold_no_sbd', 20))
    t2 = float(config.get('threshold_stage1', 40))
    t3 = float(config.get('threshold_stage2', 65))
    if pct <= t1:
        return "no_sbd"
    elif pct <= t2:
        return "sbd_stage1"
    elif pct <= t3:
        return "sbd_stage2"
    else:
        return "full_sbd"

def finalize_request(request_id, sbd_outcome, total_score, changed_by):
    conn = get_connection()
    now = datetime.now().isoformat()
    if sbd_outcome == "no_sbd":
        new_status = "no_sbd_needed"
    else:
        new_status = "awaiting_assignment"
    
    old = conn.execute("SELECT status FROM requests WHERE id=?", (request_id,)).fetchone()
    old_status = old['status'] if old else None
    
    conn.execute("""UPDATE requests SET status=?, sbd_outcome=?, total_score=?, updated_at=?,
                   awaiting_assignment_at=? WHERE id=?""",
                (new_status, sbd_outcome, total_score, now, 
                 now if new_status == 'awaiting_assignment' else None, request_id))
    conn.execute("INSERT INTO status_history (request_id, from_status, to_status, changed_by, notes, created_at) VALUES (?,?,?,?,?,?)",
                (request_id, old_status, new_status, changed_by, f'Outcome: {sbd_outcome}, Score: {total_score:.1f}', now))
    conn.commit()
    conn.close()

def update_request_status(request_id, new_status, changed_by, notes=None, extra_fields=None):
    conn = get_connection()
    now = datetime.now().isoformat()
    old = conn.execute("SELECT status FROM requests WHERE id=?", (request_id,)).fetchone()
    old_status = old['status'] if old else None
    
    # Build update query
    fields = "status=?, updated_at=?"
    values = [new_status, now]
    
    # Map status to timestamp field
    ts_map = {
        'pending_review': 'review_started_at',
        'awaiting_assignment': 'awaiting_assignment_at',
        'architect_assigned': 'architect_assigned_at',
        'architect_completed': 'architect_completed_at',
        'engineer_assigned': 'engineer_assigned_at',
        'engineer_completed': 'engineer_completed_at',
        'assurance_assigned': 'assurance_assigned_at',
        'assurance_completed': 'assurance_completed_at',
        'pending_signoff': 'pending_signoff_at',
        'signoff_received': 'signoff_received_at',
    }
    
    if new_status in ts_map:
        fields += f", {ts_map[new_status]}=?"
        values.append(now)
    
    if new_status == 'signoff_received':
        fields += ", is_locked=1"
    
    if extra_fields:
        for k, v in extra_fields.items():
            fields += f", {k}=?"
            values.append(v)
    
    values.append(request_id)
    conn.execute(f"UPDATE requests SET {fields} WHERE id=?", values)
    conn.execute("INSERT INTO status_history (request_id, from_status, to_status, changed_by, notes, created_at) VALUES (?,?,?,?,?,?)",
                (request_id, old_status, new_status, changed_by, notes, now))
    conn.commit()
    conn.close()

def get_request_by_id(request_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_request_answers(request_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT ra.*, q.text as question_text, q.category, q.options, q.weights
        FROM request_answers ra
        JOIN questions q ON ra.question_id = q.id
        WHERE ra.request_id=?
    """, (request_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_user_requests(user_id):
    conn = get_connection()
    # Requests created by user OR shared with user
    rows = conn.execute("""
        SELECT DISTINCT r.* FROM requests r
        LEFT JOIN request_permissions rp ON r.id = rp.request_id AND rp.user_id=?
        WHERE r.created_by=? OR rp.user_id=?
        ORDER BY r.created_at DESC
    """, (user_id, user_id, user_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_requests(status=None):
    conn = get_connection()
    if status:
        rows = conn.execute("SELECT * FROM requests WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM requests ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_requests_by_status(status_list):
    conn = get_connection()
    placeholders = ','.join('?' * len(status_list))
    rows = conn.execute(f"SELECT * FROM requests WHERE status IN ({placeholders}) ORDER BY created_at DESC", status_list).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_status_history(request_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT sh.*, u.name as changed_by_name
        FROM status_history sh
        JOIN users u ON sh.changed_by = u.id
        WHERE sh.request_id=?
        ORDER BY sh.created_at ASC
    """, (request_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_permission(request_id, user_id, permission, granted_by):
    conn = get_connection()
    now = datetime.now().isoformat()
    try:
        conn.execute("""INSERT OR REPLACE INTO request_permissions (request_id, user_id, permission, granted_by, created_at)
                       VALUES (?,?,?,?,?)""", (request_id, user_id, permission, granted_by, now))
        conn.commit()
        return True
    except Exception as e:
        return False
    finally:
        conn.close()

def get_permissions(request_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT rp.*, u.name, u.email, u.username
        FROM request_permissions rp
        JOIN users u ON rp.user_id = u.id
        WHERE rp.request_id=?
    """, (request_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def remove_permission(request_id, user_id):
    conn = get_connection()
    conn.execute("DELETE FROM request_permissions WHERE request_id=? AND user_id=?", (request_id, user_id))
    conn.commit()
    conn.close()

def can_user_access(request_id, user_id, require_write=False):
    conn = get_connection()
    req = conn.execute("SELECT created_by FROM requests WHERE id=?", (request_id,)).fetchone()
    if req and req['created_by'] == user_id:
        conn.close()
        return True
    perm = conn.execute("SELECT permission FROM request_permissions WHERE request_id=? AND user_id=?",
                       (request_id, user_id)).fetchone()
    conn.close()
    if perm:
        if require_write:
            return perm['permission'] == 'write'
        return True
    return False

def get_stats():
    conn = get_connection()
    stats = {}
    stats['total'] = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
    stats['pending_review'] = conn.execute("SELECT COUNT(*) FROM requests WHERE status='pending_review'").fetchone()[0]
    stats['awaiting_assignment'] = conn.execute("SELECT COUNT(*) FROM requests WHERE status='awaiting_assignment'").fetchone()[0]
    stats['in_progress'] = conn.execute("""SELECT COUNT(*) FROM requests 
        WHERE status IN ('architect_assigned','architect_completed','engineer_assigned',
                        'engineer_completed','assurance_assigned','assurance_completed')""").fetchone()[0]
    stats['pending_signoff'] = conn.execute("SELECT COUNT(*) FROM requests WHERE status='pending_signoff'").fetchone()[0]
    stats['completed'] = conn.execute("SELECT COUNT(*) FROM requests WHERE status='signoff_received'").fetchone()[0]
    stats['no_sbd'] = conn.execute("SELECT COUNT(*) FROM requests WHERE status='no_sbd_needed'").fetchone()[0]
    
    # By outcome
    for outcome in ['no_sbd', 'sbd_stage1', 'sbd_stage2', 'full_sbd']:
        stats[f'outcome_{outcome}'] = conn.execute(
            "SELECT COUNT(*) FROM requests WHERE sbd_outcome=?", (outcome,)).fetchone()[0]
    
    conn.close()
    return stats
