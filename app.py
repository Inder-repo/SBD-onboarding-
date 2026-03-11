import sys
import os
import sqlite3
import json
import hashlib
from datetime import datetime
import streamlit as st

st.set_page_config(
    page_title="Secure by Design Portal",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────────────────────

DB_PATH = "sbd_portal.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
        name TEXT NOT NULL, email TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'project_member',
        created_at TEXT NOT NULL, is_active INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL,
        description TEXT, question_type TEXT DEFAULT 'single_choice',
        options TEXT, weights TEXT, max_score INTEGER DEFAULT 10,
        category TEXT DEFAULT 'General', is_active INTEGER DEFAULT 1,
        order_index INTEGER DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS sbd_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL, value TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ref_number TEXT UNIQUE NOT NULL,
        project_name TEXT NOT NULL, project_description TEXT,
        created_by INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending_review',
        sbd_outcome TEXT, total_score REAL DEFAULT 0,
        architect_id INTEGER, architect_url TEXT, architect_notes TEXT,
        engineer_id INTEGER, assurance_id INTEGER, signoff_by INTEGER,
        is_locked INTEGER DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        submitted_at TEXT, review_started_at TEXT, awaiting_assignment_at TEXT,
        architect_assigned_at TEXT, architect_completed_at TEXT,
        engineer_assigned_at TEXT, engineer_completed_at TEXT,
        assurance_assigned_at TEXT, assurance_completed_at TEXT,
        pending_signoff_at TEXT, signoff_received_at TEXT,
        FOREIGN KEY (created_by) REFERENCES users(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS request_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL, answer TEXT NOT NULL, score REAL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (request_id) REFERENCES requests(id),
        FOREIGN KEY (question_id) REFERENCES questions(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS request_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL, permission TEXT NOT NULL DEFAULT 'read',
        granted_by INTEGER NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(request_id, user_id),
        FOREIGN KEY (request_id) REFERENCES requests(id),
        FOREIGN KEY (user_id) REFERENCES users(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER NOT NULL,
        from_status TEXT, to_status TEXT NOT NULL, changed_by INTEGER NOT NULL,
        notes TEXT, created_at TEXT NOT NULL,
        FOREIGN KEY (request_id) REFERENCES requests(id),
        FOREIGN KEY (changed_by) REFERENCES users(id))""")
    conn.commit()
    _seed_default_data(conn)
    conn.close()

def _seed_default_data(conn):
    c = conn.cursor()
    now = datetime.now().isoformat()
    default_users = [
        ("admin","admin123","System Admin","admin@company.com","admin"),
        ("sbd_manager","manager123","SbD Manager","sbdmanager@company.com","sbd_manager"),
        ("architect1","arch123","Alice Chen","alice@company.com","security_architect"),
        ("engineer1","eng123","Bob Smith","bob@company.com","security_engineer"),
        ("assurance1","assur123","Carol Davis","carol@company.com","assurance"),
        ("user1","user123","David Johnson","david@company.com","project_member"),
        ("user2","user123","Eve Wilson","eve@company.com","project_member"),
    ]
    for username, password, name, email, role in default_users:
        ph = hashlib.sha256(password.encode()).hexdigest()
        try:
            c.execute("INSERT OR IGNORE INTO users (username,password_hash,name,email,role,created_at) VALUES (?,?,?,?,?,?)",
                      (username,ph,name,email,role,now))
        except: pass
    default_questions = [
        ("Does your project process, store, or transmit personal data (PII)?",
         "Personal Identifiable Information includes names, addresses, emails, etc.",
         json.dumps(["No","Yes - minimal (name/email only)","Yes - moderate (financial/health)","Yes - extensive (sensitive categories)"]),
         json.dumps([0,3,7,10]),10,"Data Privacy",1),
        ("What is the expected user base size?",
         "Approximate number of end users who will interact with the system.",
         json.dumps(["Internal only (<50 users)","Small (<500 users)","Medium (500-10,000)","Large (>10,000 users)"]),
         json.dumps([0,2,5,8]),8,"Scale & Exposure",2),
        ("Does the project involve external-facing components or APIs?",
         "Any components accessible from outside the corporate network.",
         json.dumps(["No, fully internal","Limited internal API","External API with auth","Public-facing web/API"]),
         json.dumps([0,2,6,10]),10,"Exposure",3),
        ("Does the project handle financial transactions or payment data?",
         "Includes card payments, bank transfers, financial records.",
         json.dumps(["No","Indirect reference only","Yes - internal transfers","Yes - direct card/payment processing"]),
         json.dumps([0,3,7,10]),10,"Financial Risk",4),
        ("What level of authentication does the system require?",
         "How users will verify their identity to access the system.",
         json.dumps(["No authentication required","Username/password only","MFA supported","MFA mandatory + SSO"]),
         json.dumps([8,5,2,0]),8,"Authentication",5),
        ("Does the project integrate with third-party systems or vendors?",
         "External APIs, SaaS products, data feeds from outside your organisation.",
         json.dumps(["No integrations","1-2 trusted internal systems","Several external systems","Many external/untrusted systems"]),
         json.dumps([0,2,6,10]),10,"Third-party Risk",6),
        ("What is the classification of data handled by the project?",
         "Based on your organisation's data classification policy.",
         json.dumps(["Public","Internal use only","Confidential","Highly Confidential / Restricted"]),
         json.dumps([0,2,6,10]),10,"Data Classification",7),
        ("What is the regulatory/compliance requirement for this project?",
         "E.g. GDPR, PCI-DSS, HIPAA, SOX, ISO27001.",
         json.dumps(["None identified","General data protection","Industry-specific (PCI/HIPAA)","Multiple strict regulations"]),
         json.dumps([0,3,7,10]),10,"Compliance",8),
    ]
    for i,(text,desc,opts,wts,max_s,cat,order) in enumerate(default_questions):
        try:
            c.execute("""INSERT OR IGNORE INTO questions
                (text,description,question_type,options,weights,max_score,category,order_index,is_active,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,1,?,?)""",
                (text,desc,'single_choice',opts,wts,max_s,cat,order,now,now))
        except: pass
    configs = [("threshold_no_sbd","20"),("threshold_stage1","40"),("threshold_stage2","65"),("threshold_full_sbd","100")]
    for key,value in configs:
        try:
            c.execute("INSERT OR IGNORE INTO sbd_config (key,value,updated_at) VALUES (?,?,?)",(key,value,now))
        except: pass
    conn.commit()

def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()

def get_user_by_username(username):
    conn=get_connection(); row=conn.execute("SELECT * FROM users WHERE username=? AND is_active=1",(username,)).fetchone(); conn.close()
    return dict(row) if row else None

def get_user_by_id(uid):
    conn=get_connection(); row=conn.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone(); conn.close()
    return dict(row) if row else None

def get_all_users(role=None):
    conn=get_connection()
    rows=conn.execute("SELECT * FROM users WHERE role=? AND is_active=1",(role,)).fetchall() if role else conn.execute("SELECT * FROM users WHERE is_active=1").fetchall()
    conn.close(); return [dict(r) for r in rows]

def create_user(username,password,name,email,role):
    conn=get_connection(); now=datetime.now().isoformat(); ph=hash_password(password)
    try:
        conn.execute("INSERT INTO users (username,password_hash,name,email,role,created_at) VALUES (?,?,?,?,?,?)",(username,ph,name,email,role,now))
        conn.commit(); return True,"User created"
    except sqlite3.IntegrityError: return False,"Username already exists"
    finally: conn.close()

def update_user_role(uid,role):
    conn=get_connection(); conn.execute("UPDATE users SET role=? WHERE id=?",(role,uid)); conn.commit(); conn.close()

def deactivate_user(uid):
    conn=get_connection(); conn.execute("UPDATE users SET is_active=0 WHERE id=?",(uid,)); conn.commit(); conn.close()

def get_active_questions():
    conn=get_connection(); rows=conn.execute("SELECT * FROM questions WHERE is_active=1 ORDER BY order_index,id").fetchall(); conn.close()
    return [dict(r) for r in rows]

def get_all_questions():
    conn=get_connection(); rows=conn.execute("SELECT * FROM questions ORDER BY order_index,id").fetchall(); conn.close()
    return [dict(r) for r in rows]

def create_question(text,description,question_type,options,weights,max_score,category,order_index):
    conn=get_connection(); now=datetime.now().isoformat()
    conn.execute("""INSERT INTO questions (text,description,question_type,options,weights,max_score,category,order_index,is_active,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,1,?,?)""",(text,description,question_type,json.dumps(options),json.dumps(weights),max_score,category,order_index,now,now))
    conn.commit(); conn.close()

def update_question(qid,text,description,options,weights,max_score,category,order_index,is_active):
    conn=get_connection(); now=datetime.now().isoformat()
    conn.execute("""UPDATE questions SET text=?,description=?,options=?,weights=?,max_score=?,category=?,order_index=?,is_active=?,updated_at=? WHERE id=?""",
                (text,description,json.dumps(options),json.dumps(weights),max_score,category,order_index,is_active,now,qid))
    conn.commit(); conn.close()

def get_sbd_config():
    conn=get_connection(); rows=conn.execute("SELECT * FROM sbd_config").fetchall(); conn.close()
    return {r['key']:r['value'] for r in rows}

def update_sbd_config(key,value):
    conn=get_connection(); now=datetime.now().isoformat()
    conn.execute("INSERT OR REPLACE INTO sbd_config (key,value,updated_at) VALUES (?,?,?)",(key,value,now)); conn.commit(); conn.close()

def generate_ref_number():
    conn=get_connection(); count=conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]; conn.close()
    return f"SBD-{datetime.now().year}-{str(count+1).zfill(4)}"

def create_request(project_name,description,created_by):
    conn=get_connection(); now=datetime.now().isoformat(); ref=generate_ref_number()
    conn.execute("INSERT INTO requests (ref_number,project_name,project_description,created_by,status,created_at,updated_at,submitted_at) VALUES (?,?,?,?,?,?,?,?)",
                (ref,project_name,description,created_by,'pending_review',now,now,now))
    conn.commit()
    req_id=conn.execute("SELECT id FROM requests WHERE ref_number=?",(ref,)).fetchone()[0]
    conn.execute("INSERT INTO status_history (request_id,from_status,to_status,changed_by,notes,created_at) VALUES (?,?,?,?,?,?)",
                (req_id,None,'pending_review',created_by,'Request submitted',now))
    conn.commit(); conn.close(); return req_id,ref

def save_answers(request_id,answers_dict):
    conn=get_connection(); now=datetime.now().isoformat()
    conn.execute("DELETE FROM request_answers WHERE request_id=?",(request_id,))
    total_score=0
    for qid,ans_data in answers_dict.items():
        conn.execute("INSERT INTO request_answers (request_id,question_id,answer,score,created_at) VALUES (?,?,?,?,?)",
                    (request_id,qid,ans_data['answer'],ans_data['score'],now))
        total_score+=ans_data['score']
    conn.execute("UPDATE requests SET total_score=?,updated_at=? WHERE id=?",(total_score,now,request_id))
    conn.commit(); conn.close(); return total_score

def determine_sbd_outcome(total_score,max_possible_score,config):
    if max_possible_score==0: return "no_sbd"
    pct=(total_score/max_possible_score)*100
    t1=float(config.get('threshold_no_sbd',20)); t2=float(config.get('threshold_stage1',40)); t3=float(config.get('threshold_stage2',65))
    if pct<=t1: return "no_sbd"
    elif pct<=t2: return "sbd_stage1"
    elif pct<=t3: return "sbd_stage2"
    else: return "full_sbd"

def finalize_request(request_id,sbd_outcome,total_score,changed_by):
    conn=get_connection(); now=datetime.now().isoformat()
    new_status="no_sbd_needed" if sbd_outcome=="no_sbd" else "awaiting_assignment"
    old=conn.execute("SELECT status FROM requests WHERE id=?",(request_id,)).fetchone()
    old_status=old['status'] if old else None
    conn.execute("UPDATE requests SET status=?,sbd_outcome=?,total_score=?,updated_at=?,awaiting_assignment_at=? WHERE id=?",
                (new_status,sbd_outcome,total_score,now,now if new_status=='awaiting_assignment' else None,request_id))
    conn.execute("INSERT INTO status_history (request_id,from_status,to_status,changed_by,notes,created_at) VALUES (?,?,?,?,?,?)",
                (request_id,old_status,new_status,changed_by,f'Outcome: {sbd_outcome}, Score: {total_score:.1f}',now))
    conn.commit(); conn.close()

def update_request_status(request_id,new_status,changed_by,notes=None,extra_fields=None):
    conn=get_connection(); now=datetime.now().isoformat()
    old=conn.execute("SELECT status FROM requests WHERE id=?",(request_id,)).fetchone()
    old_status=old['status'] if old else None
    fields="status=?, updated_at=?"; values=[new_status,now]
    ts_map={'pending_review':'review_started_at','awaiting_assignment':'awaiting_assignment_at',
            'architect_assigned':'architect_assigned_at','architect_completed':'architect_completed_at',
            'engineer_assigned':'engineer_assigned_at','engineer_completed':'engineer_completed_at',
            'assurance_assigned':'assurance_assigned_at','assurance_completed':'assurance_completed_at',
            'pending_signoff':'pending_signoff_at','signoff_received':'signoff_received_at'}
    if new_status in ts_map:
        fields+=f", {ts_map[new_status]}=?"; values.append(now)
    if new_status=='signoff_received':
        fields+=", is_locked=1"
    if extra_fields:
        for k,v in extra_fields.items():
            fields+=f", {k}=?"; values.append(v)
    values.append(request_id)
    conn.execute(f"UPDATE requests SET {fields} WHERE id=?",values)
    conn.execute("INSERT INTO status_history (request_id,from_status,to_status,changed_by,notes,created_at) VALUES (?,?,?,?,?,?)",
                (request_id,old_status,new_status,changed_by,notes,now))
    conn.commit(); conn.close()

def get_request_by_id(rid):
    conn=get_connection(); row=conn.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone(); conn.close()
    return dict(row) if row else None

def get_request_answers(request_id):
    conn=get_connection()
    rows=conn.execute("""SELECT ra.*,q.text as question_text,q.category,q.options,q.weights
        FROM request_answers ra JOIN questions q ON ra.question_id=q.id WHERE ra.request_id=?""",(request_id,)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def get_user_requests(user_id):
    conn=get_connection()
    rows=conn.execute("""SELECT DISTINCT r.* FROM requests r
        LEFT JOIN request_permissions rp ON r.id=rp.request_id AND rp.user_id=?
        WHERE r.created_by=? OR rp.user_id=? ORDER BY r.created_at DESC""",(user_id,user_id,user_id)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def get_all_requests(status=None):
    conn=get_connection()
    rows=conn.execute("SELECT * FROM requests WHERE status=? ORDER BY created_at DESC",(status,)).fetchall() if status else conn.execute("SELECT * FROM requests ORDER BY created_at DESC").fetchall()
    conn.close(); return [dict(r) for r in rows]

def get_requests_by_status(status_list):
    conn=get_connection()
    ph=','.join('?'*len(status_list))
    rows=conn.execute(f"SELECT * FROM requests WHERE status IN ({ph}) ORDER BY created_at DESC",status_list).fetchall()
    conn.close(); return [dict(r) for r in rows]

def get_status_history(request_id):
    conn=get_connection()
    rows=conn.execute("""SELECT sh.*,u.name as changed_by_name FROM status_history sh
        JOIN users u ON sh.changed_by=u.id WHERE sh.request_id=? ORDER BY sh.created_at ASC""",(request_id,)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def add_permission(request_id,user_id,permission,granted_by):
    conn=get_connection(); now=datetime.now().isoformat()
    try:
        conn.execute("INSERT OR REPLACE INTO request_permissions (request_id,user_id,permission,granted_by,created_at) VALUES (?,?,?,?,?)",
                    (request_id,user_id,permission,granted_by,now))
        conn.commit(); return True
    except: return False
    finally: conn.close()

def get_permissions(request_id):
    conn=get_connection()
    rows=conn.execute("""SELECT rp.*,u.name,u.email,u.username FROM request_permissions rp
        JOIN users u ON rp.user_id=u.id WHERE rp.request_id=?""",(request_id,)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def remove_permission(request_id,user_id):
    conn=get_connection(); conn.execute("DELETE FROM request_permissions WHERE request_id=? AND user_id=?",(request_id,user_id)); conn.commit(); conn.close()

def can_user_access(request_id,user_id,require_write=False):
    conn=get_connection()
    req=conn.execute("SELECT created_by FROM requests WHERE id=?",(request_id,)).fetchone()
    if req and req['created_by']==user_id: conn.close(); return True
    perm=conn.execute("SELECT permission FROM request_permissions WHERE request_id=? AND user_id=?",(request_id,user_id)).fetchone()
    conn.close()
    if perm:
        return perm['permission']=='write' if require_write else True
    return False

def get_stats():
    conn=get_connection(); stats={}
    stats['total']=conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
    stats['pending_review']=conn.execute("SELECT COUNT(*) FROM requests WHERE status='pending_review'").fetchone()[0]
    stats['awaiting_assignment']=conn.execute("SELECT COUNT(*) FROM requests WHERE status='awaiting_assignment'").fetchone()[0]
    stats['in_progress']=conn.execute("SELECT COUNT(*) FROM requests WHERE status IN ('architect_assigned','architect_completed','engineer_assigned','engineer_completed','assurance_assigned','assurance_completed')").fetchone()[0]
    stats['pending_signoff']=conn.execute("SELECT COUNT(*) FROM requests WHERE status='pending_signoff'").fetchone()[0]
    stats['completed']=conn.execute("SELECT COUNT(*) FROM requests WHERE status='signoff_received'").fetchone()[0]
    stats['no_sbd']=conn.execute("SELECT COUNT(*) FROM requests WHERE status='no_sbd_needed'").fetchone()[0]
    for outcome in ['no_sbd','sbd_stage1','sbd_stage2','full_sbd']:
        stats[f'outcome_{outcome}']=conn.execute("SELECT COUNT(*) FROM requests WHERE sbd_outcome=?",(outcome,)).fetchone()[0]
    conn.close(); return stats

# ─────────────────────────────────────────────────────────────────────────────
# STYLES
# ─────────────────────────────────────────────────────────────────────────────

def inject_styles():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=DM+Sans:wght@300;400;500;600;700&display=swap');
    :root {
        --bg:#f8fafc;--surface:#ffffff;--border:#e2e8f0;--text:#0f172a;--text-muted:#64748b;
        --primary:#1e40af;--primary-light:#dbeafe;--accent:#0ea5e9;--success:#10b981;
        --warning:#f59e0b;--danger:#ef4444;--purple:#7c3aed;
        --mono:'JetBrains Mono',monospace;--sans:'DM Sans',sans-serif;
    }
    html,body,[class*="css"]{font-family:var(--sans)!important;}
    #MainMenu{visibility:hidden;}footer{visibility:hidden;}header{visibility:hidden;}
    [data-testid="stSidebar"]{background:#0f172a!important;border-right:1px solid #1e293b;}
    [data-testid="stSidebar"] *{color:#e2e8f0!important;}
    [data-testid="stSidebarContent"]{padding:0!important;}
    .sidebar-header{display:flex;align-items:center;gap:.75rem;padding:1.5rem 1.25rem 1rem;border-bottom:1px solid #1e293b;}
    .sidebar-logo{font-size:1.5rem;}.sidebar-title{font-family:var(--mono);font-weight:700;font-size:1.1rem;color:#f1f5f9!important;letter-spacing:-.02em;}
    .user-badge{display:flex;align-items:center;gap:.75rem;padding:1rem 1.25rem;background:#1e293b;margin:.75rem;border-radius:8px;}
    .user-avatar{width:36px;height:36px;background:#1e40af;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1rem;color:white!important;flex-shrink:0;line-height:36px;text-align:center;}
    .user-name{font-weight:600;font-size:.9rem;color:#f1f5f9!important;}.user-role{font-size:.75rem;color:#94a3b8!important;text-transform:uppercase;letter-spacing:.05em;}
    [data-testid="stSidebar"] .stButton button{background:transparent!important;border:none!important;color:#94a3b8!important;text-align:left!important;padding:.5rem 1.25rem!important;border-radius:6px!important;font-size:.9rem!important;transition:all .15s!important;margin:1px .5rem!important;width:calc(100% - 1rem)!important;}
    [data-testid="stSidebar"] .stButton button:hover{background:#1e293b!important;color:#f1f5f9!important;}
    [data-testid="stSidebar"] .stButton button[kind="primary"]{background:#1e40af!important;color:white!important;}
    .main .block-container{padding:1.5rem 2rem!important;max-width:1400px!important;}
    .card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1.5rem;margin-bottom:1rem;}
    .card-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:1rem;padding-bottom:.75rem;border-bottom:1px solid var(--border);}
    .badge{display:inline-flex;align-items:center;gap:.3rem;padding:.2rem .7rem;border-radius:999px;font-size:.75rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;}
    .badge-pending{background:#fef3c7;color:#92400e;}.badge-awaiting{background:#dbeafe;color:#1e40af;}
    .badge-active{background:#d1fae5;color:#065f46;}.badge-review{background:#ede9fe;color:#5b21b6;}
    .badge-complete{background:#d1fae5;color:#065f46;}.badge-no-sbd{background:#f1f5f9;color:#475569;}
    .stat-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1.25rem;text-align:center;}
    .stat-number{font-family:var(--mono);font-size:2.5rem;font-weight:700;color:var(--primary);line-height:1;margin-bottom:.25rem;}
    .stat-label{font-size:.8rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;}
    .timeline{position:relative;padding-left:2rem;}
    .timeline::before{content:'';position:absolute;left:.45rem;top:0;bottom:0;width:2px;background:var(--border);}
    .timeline-item{position:relative;margin-bottom:1.5rem;}
    .timeline-dot{position:absolute;left:-1.73rem;top:.25rem;width:14px;height:14px;border-radius:50%;background:var(--primary);border:2px solid white;box-shadow:0 0 0 2px var(--primary);}
    .timeline-dot.complete{background:var(--success);box-shadow:0 0 0 2px var(--success);}
    .timeline-dot.pending{background:var(--border);box-shadow:0 0 0 2px var(--border);}
    .pipeline{display:flex;align-items:center;gap:0;margin:1rem 0;overflow-x:auto;padding:.5rem 0;}
    .pipe-step{display:flex;flex-direction:column;align-items:center;flex:1;min-width:80px;}
    .pipe-dot{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.9rem;border:2px solid var(--border);background:white;position:relative;z-index:1;}
    .pipe-dot.active{border-color:var(--primary);background:var(--primary);color:white;}
    .pipe-dot.done{border-color:var(--success);background:var(--success);color:white;}
    .pipe-label{font-size:.65rem;text-align:center;margin-top:.3rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.04em;max-width:70px;line-height:1.3;}
    .pipe-line{flex:1;height:2px;background:var(--border);margin-top:-1.2rem;}.pipe-line.done{background:var(--success);}
    .page-header{margin-bottom:1.5rem;padding-bottom:1rem;border-bottom:1px solid var(--border);}
    .page-title{font-family:var(--mono);font-size:1.6rem;font-weight:700;color:var(--text);margin:0;}
    .page-subtitle{color:var(--text-muted);margin-top:.25rem;font-size:.9rem;}
    .ref-number{font-family:var(--mono);font-size:.8rem;color:var(--primary);background:var(--primary-light);padding:.15rem .5rem;border-radius:4px;font-weight:600;}
    .outcome-banner{border-radius:12px;padding:1.25rem 1.5rem;display:flex;align-items:center;gap:1rem;margin:1rem 0;}
    .outcome-no-sbd{background:#f1f5f9;border:2px solid #cbd5e1;}.outcome-stage1{background:#fefce8;border:2px solid #fde047;}
    .outcome-stage2{background:#fff7ed;border:2px solid #fb923c;}.outcome-full{background:#fef2f2;border:2px solid #f87171;}
    .question-card{background:#f8fafc;border:1px solid var(--border);border-left:3px solid var(--primary);border-radius:8px;padding:1rem 1.25rem;margin-bottom:1rem;}
    .question-number{font-family:var(--mono);font-size:.75rem;color:var(--primary);font-weight:700;margin-bottom:.3rem;}
    .question-text{font-weight:600;color:var(--text);margin-bottom:.3rem;}
    .question-desc{font-size:.83rem;color:var(--text-muted);margin-bottom:.5rem;}
    .alert{padding:.75rem 1rem;border-radius:8px;margin:.5rem 0;font-size:.88rem;}
    .alert-info{background:#dbeafe;border:1px solid #93c5fd;color:#1e40af;}
    .alert-warning{background:#fef3c7;border:1px solid #fcd34d;color:#92400e;}
    .alert-success{background:#d1fae5;border:1px solid #6ee7b7;color:#065f46;}
    .lock-banner{background:#1e293b;color:#f1f5f9;border-radius:8px;padding:.75rem 1.25rem;display:flex;align-items:center;gap:.75rem;font-weight:600;margin-bottom:1rem;}
    </style>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# UTILS
# ─────────────────────────────────────────────────────────────────────────────

STATUS_CONFIG = {
    'pending_review':      {'label':'Pending Review',      'badge':'badge-pending',  'icon':'⏳'},
    'no_sbd_needed':       {'label':'No SBD Needed',       'badge':'badge-no-sbd',   'icon':'✓'},
    'awaiting_assignment': {'label':'Awaiting Assignment', 'badge':'badge-awaiting', 'icon':'👤'},
    'architect_assigned':  {'label':'Architect Assigned',  'badge':'badge-active',   'icon':'🏗️'},
    'architect_completed': {'label':'Architect Done',      'badge':'badge-active',   'icon':'✅'},
    'engineer_assigned':   {'label':'Engineer Assigned',   'badge':'badge-active',   'icon':'⚙️'},
    'engineer_completed':  {'label':'Engineering Done',    'badge':'badge-active',   'icon':'✅'},
    'assurance_assigned':  {'label':'Assurance Assigned',  'badge':'badge-review',   'icon':'🔍'},
    'assurance_completed': {'label':'Assurance Done',      'badge':'badge-review',   'icon':'✅'},
    'pending_signoff':     {'label':'Pending Sign-off',    'badge':'badge-review',   'icon':'✍️'},
    'signoff_received':    {'label':'Sign-off Received',   'badge':'badge-complete', 'icon':'🎉'},
}
OUTCOME_CONFIG = {
    'no_sbd':   {'label':'No SBD Required',   'class':'outcome-no-sbd', 'icon':'✅','color':'#64748b'},
    'sbd_stage1':{'label':'SBD Stage 1',       'class':'outcome-stage1', 'icon':'⚠️','color':'#d97706'},
    'sbd_stage2':{'label':'SBD Stage 2',       'class':'outcome-stage2', 'icon':'🔶','color':'#ea580c'},
    'full_sbd':  {'label':'Full SBD Required', 'class':'outcome-full',   'icon':'🔴','color':'#dc2626'},
}

def status_badge(status):
    cfg=STATUS_CONFIG.get(status,{'label':status,'badge':'badge-pending','icon':'?'})
    return f'<span class="badge {cfg["badge"]}">{cfg["icon"]} {cfg["label"]}</span>'

def outcome_badge(outcome):
    if not outcome: return ''
    cfg=OUTCOME_CONFIG.get(outcome,{'label':outcome,'color':'#64748b','icon':'?'})
    return f'<span style="font-size:.75rem;font-weight:600;color:{cfg["color"]}">{cfg["icon"]} {cfg["label"]}</span>'

def format_date(dt_str):
    if not dt_str: return "—"
    try: return datetime.fromisoformat(dt_str).strftime("%d %b %Y, %H:%M")
    except: return dt_str

def get_status_pipeline():
    return [
        {'key':'pending_review',      'label':'Submitted', 'icon':'📋'},
        {'key':'awaiting_assignment', 'label':'Assessed',  'icon':'📊'},
        {'key':'architect_assigned',  'label':'Architect', 'icon':'🏗️'},
        {'key':'architect_completed', 'label':'Arch Done', 'icon':'✅'},
        {'key':'engineer_assigned',   'label':'Engineer',  'icon':'⚙️'},
        {'key':'engineer_completed',  'label':'Eng Done',  'icon':'✅'},
        {'key':'assurance_assigned',  'label':'Assurance', 'icon':'🔍'},
        {'key':'assurance_completed', 'label':'Assur Done','icon':'✅'},
        {'key':'pending_signoff',     'label':'Sign-off',  'icon':'✍️'},
        {'key':'signoff_received',    'label':'Complete',  'icon':'🎉'},
    ]

def render_pipeline(current_status):
    steps=get_status_pipeline()
    try: current_idx=next(i for i,s in enumerate(steps) if s['key']==current_status)
    except StopIteration: current_idx=-1
    html='<div class="pipeline">'
    for i,step in enumerate(steps):
        cls="done" if i<current_idx else ("active" if i==current_idx else "")
        icon="✓" if i<current_idx else (step['icon'] if i==current_idx else "○")
        if i>0:
            html+=f'<div class="pipe-line {"done" if i<=current_idx else ""}"></div>'
        html+=f'<div class="pipe-step"><div class="pipe-dot {cls}">{icon}</div><div class="pipe-label">{step["label"]}</div></div>'
    html+='</div>'; return html

# ─────────────────────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────────────────────

def login_page():
    st.markdown("""
    <div style="display:flex;flex-direction:column;align-items:center;padding-top:3rem;">
        <div style="text-align:center;margin-bottom:2rem;">
            <div style="font-size:4rem;">🔐</div>
            <h1 style="font-family:'Courier New',monospace;font-size:2.2rem;font-weight:900;color:#0f172a;margin:0;">SECURE BY DESIGN</h1>
            <p style="color:#64748b;font-size:1rem;margin-top:.5rem;letter-spacing:.1em;text-transform:uppercase;">Enterprise Security Portal</p>
        </div>
    </div>""", unsafe_allow_html=True)
    col1,col2,col3=st.columns([1,1.2,1])
    with col2:
        st.markdown("**Sign in to your account**")
        username=st.text_input("Username",placeholder="Enter your username")
        password=st.text_input("Password",type="password",placeholder="Enter your password")
        if st.button("Sign In →",use_container_width=True,type="primary"):
            if username and password:
                user=get_user_by_username(username)
                if user and user['password_hash']==hash_password(password):
                    st.session_state.authenticated=True; st.session_state.user=user; st.rerun()
                else: st.error("Invalid credentials.")
            else: st.warning("Please enter username and password.")
        st.markdown('<div style="text-align:center;margin-top:1rem;color:#94a3b8;font-size:.85rem;">Demo: admin/admin123 · sbd_manager/manager123 · user1/user123</div>',unsafe_allow_html=True)

def logout():
    st.session_state.authenticated=False; st.session_state.user=None; st.session_state.page="dashboard"

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

def show_dashboard(user):
    st.markdown('<div class="page-header"><div class="page-title">🏠 Dashboard</div><div class="page-subtitle">Overview of Secure by Design activities</div></div>',unsafe_allow_html=True)
    stats=get_stats()
    cols=st.columns(6)
    for col,(label,value,icon) in zip(cols,[("Total",stats['total'],"📋"),("Pending Review",stats['pending_review'],"⏳"),("Awaiting Assign",stats['awaiting_assignment'],"👤"),("In Progress",stats['in_progress'],"⚙️"),("Pending Sign-off",stats['pending_signoff'],"✍️"),("Completed",stats['completed'],"✅")]):
        with col:
            st.markdown(f'<div class="stat-card"><div style="font-size:1.5rem;">{icon}</div><div class="stat-number">{value}</div><div class="stat-label">{label}</div></div>',unsafe_allow_html=True)
    st.markdown("<br>",unsafe_allow_html=True)
    col_left,col_right=st.columns([3,2])
    with col_left:
        st.markdown("### Recent Requests")
        requests=(get_all_requests() if user['role'] in ['admin','sbd_manager'] else get_user_requests(user['id']))[:10]
        if not requests:
            st.markdown('<div class="card" style="text-align:center;padding:2rem;color:#94a3b8;"><div style="font-size:2rem;">📭</div>No requests yet.</div>',unsafe_allow_html=True)
        else:
            for req in requests:
                st.markdown(f"""<div class="card" style="margin-bottom:.75rem;padding:1rem 1.25rem;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem;">
                        <span class="ref-number">{req['ref_number']}</span>{status_badge(req['status'])}
                    </div>
                    <div style="font-weight:600;color:#0f172a;">{req['project_name']}</div>
                    <div style="font-size:.8rem;color:#64748b;">Created {format_date(req['created_at'])}</div>
                </div>""",unsafe_allow_html=True)
                if st.button(f"View {req['ref_number']}",key=f"dash_{req['id']}"):
                    st.session_state.selected_request_id=req['id']; st.session_state.page="request_detail"; st.rerun()
    with col_right:
        st.markdown("### SbD Outcomes")
        outcome_data=[("No SBD",stats['outcome_no_sbd'],"#94a3b8","🟢"),("Stage 1",stats['outcome_sbd_stage1'],"#fbbf24","🟡"),("Stage 2",stats['outcome_sbd_stage2'],"#f97316","🟠"),("Full SBD",stats['outcome_full_sbd'],"#ef4444","🔴")]
        total_out=sum(v for _,v,_,_ in outcome_data)
        for label,count,color,emoji in outcome_data:
            pct=(count/total_out*100) if total_out>0 else 0
            st.markdown(f'<div style="margin-bottom:.75rem;"><div style="display:flex;justify-content:space-between;margin-bottom:.25rem;"><span style="font-size:.85rem;">{emoji} {label}</span><span style="font-family:monospace;font-weight:700;">{count}</span></div><div style="background:#e2e8f0;border-radius:999px;height:6px;"><div style="background:{color};height:6px;border-radius:999px;width:{pct:.1f}%;"></div></div></div>',unsafe_allow_html=True)
        st.markdown("---")
        if st.button("➕ New SbD Request",use_container_width=True,type="primary"):
            st.session_state.page="new_request"; st.rerun()
        if user['role'] in ['admin','sbd_manager']:
            if st.button("📥 Review Pending",use_container_width=True):
                st.session_state.page="pending_review"; st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: MY REQUESTS
# ─────────────────────────────────────────────────────────────────────────────

def show_my_requests(user):
    st.markdown('<div class="page-header"><div class="page-title">📋 My Requests</div><div class="page-subtitle">All SbD requests you have access to</div></div>',unsafe_allow_html=True)
    requests=get_user_requests(user['id'])
    col1,col2,col3=st.columns([2,3,1])
    with col1: status_filter=st.selectbox("Filter",["All","Pending Review","Awaiting Assignment","In Progress","Pending Sign-off","Completed","No SBD"])
    with col2: search=st.text_input("Search",placeholder="Project name or ref...")
    with col3:
        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("➕ New",type="primary",use_container_width=True): st.session_state.page="new_request"; st.rerun()
    sm={'Pending Review':['pending_review'],'Awaiting Assignment':['awaiting_assignment'],'In Progress':['architect_assigned','architect_completed','engineer_assigned','engineer_completed','assurance_assigned','assurance_completed'],'Pending Sign-off':['pending_signoff'],'Completed':['signoff_received'],'No SBD':['no_sbd_needed']}
    filtered=requests
    if status_filter!="All": filtered=[r for r in filtered if r['status'] in sm.get(status_filter,[])]
    if search: s=search.lower(); filtered=[r for r in filtered if s in r['project_name'].lower() or s in r['ref_number'].lower()]
    if not filtered:
        st.markdown('<div class="card" style="text-align:center;padding:3rem;color:#94a3b8;"><div style="font-size:2.5rem;">📭</div><div style="font-weight:600;">No requests found</div></div>',unsafe_allow_html=True); return
    st.markdown(f"**{len(filtered)}** request(s)")
    for req in filtered:
        st.markdown(f"""<div class="card" style="margin-bottom:.75rem;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem;">
                <span class="ref-number">{req['ref_number']}</span>{status_badge(req['status'])}{f" {outcome_badge(req.get('sbd_outcome'))}" if req.get('sbd_outcome') else ""}
            </div>
            <div style="font-weight:600;">{req['project_name']}</div>
            <div style="font-size:.82rem;color:#64748b;">{format_date(req['created_at'])}</div>
        </div>""",unsafe_allow_html=True)
        st.markdown(render_pipeline(req['status']),unsafe_allow_html=True)
        if st.button("Open →",key=f"my_{req['id']}"):
            st.session_state.selected_request_id=req['id']; st.session_state.page="request_detail"; st.rerun()
        st.markdown("<hr style='margin:.5rem 0;border-color:#f1f5f9;'>",unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: NEW REQUEST (wizard)
# ─────────────────────────────────────────────────────────────────────────────

def show_new_request(user):
    st.markdown('<div class="page-header"><div class="page-title">➕ New SbD Request</div><div class="page-subtitle">Submit a new Secure by Design assessment</div></div>',unsafe_allow_html=True)
    for k,v in [('nr_step',1),('nr_request_id',None),('nr_answers',{}),('nr_project_name',""),('nr_project_desc',"")]:
        if k not in st.session_state: st.session_state[k]=v
    step=st.session_state.nr_step
    steps_info=["Project Details","Assessment Questions","Review & Submit","Outcome"]
    _render_stepper(steps_info,step)
    st.markdown("<br>",unsafe_allow_html=True)
    if step==1: _nr_step1(user)
    elif step==2: _nr_step2(user)
    elif step==3: _nr_step3(user)
    elif step==4: _nr_step4(user)

def _render_stepper(steps,current):
    html='<div style="display:flex;align-items:center;margin-bottom:1rem;">'
    for i,label in enumerate(steps,1):
        if i<current: dot_s="background:#10b981;color:white;border-color:#10b981;"; lc="#10b981"; icon="✓"
        elif i==current: dot_s="background:#1e40af;color:white;border-color:#1e40af;"; lc="#1e40af"; icon=str(i)
        else: dot_s="background:white;color:#94a3b8;border-color:#e2e8f0;"; lc="#94a3b8"; icon=str(i)
        html+=f'<div style="display:flex;flex-direction:column;align-items:center;flex:1;"><div style="width:32px;height:32px;border-radius:50%;border:2px solid;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.85rem;{dot_s}">{icon}</div><div style="font-size:.72rem;margin-top:.3rem;color:{lc};font-weight:500;text-align:center;">{label}</div></div>'
        if i<len(steps): html+=f'<div style="flex:2;height:2px;background:{"#10b981" if i<current else "#e2e8f0"};margin-bottom:1.3rem;"></div>'
    html+='</div>'; st.markdown(html,unsafe_allow_html=True)

def _nr_step1(user):
    st.markdown("### 📋 Project Information")
    with st.form("nr_form1"):
        pn=st.text_input("Project Name *",value=st.session_state.nr_project_name,placeholder="e.g. Customer Portal v2.0")
        pd=st.text_area("Project Description",value=st.session_state.nr_project_desc,placeholder="Describe the project...",height=120)
        if st.form_submit_button("Continue →",type="primary"):
            if not pn.strip(): st.error("Project name required.")
            else: st.session_state.nr_project_name=pn.strip(); st.session_state.nr_project_desc=pd.strip(); st.session_state.nr_step=2; st.rerun()

def _nr_step2(user):
    questions=get_active_questions()
    if not questions: st.warning("No questions configured. Contact admin."); return
    st.markdown(f"### 🔍 Security Assessment ({len(questions)} questions)")
    with st.form("nr_form2"):
        answers={}
        cats={}
        for q in questions: cats.setdefault(q.get('category','General'),[]).append(q)
        for cat,qs in cats.items():
            st.markdown(f"#### {cat}")
            for i,q in enumerate(qs):
                options=json.loads(q['options']) if isinstance(q['options'],str) else q['options']
                prev=st.session_state.nr_answers.get(str(q['id']),{}).get('answer')
                prev_idx=options.index(prev) if prev in options else 0
                q_desc_html = f'<div class="question-desc">{q["description"]}</div>' if q.get("description") else ""
                st.markdown(f'<div class="question-card"><div class="question-number">Q{i+1} · {cat}</div><div class="question-text">{q["text"]}</div>{q_desc_html}</div>',unsafe_allow_html=True)
                answers[q['id']]=st.radio("",options=options,index=prev_idx,key=f"qr_{q['id']}",label_visibility="collapsed")
                st.markdown("<br>",unsafe_allow_html=True)
        c1,c2=st.columns([1,4])
        with c1: back=st.form_submit_button("← Back")
        with c2: proceed=st.form_submit_button("Review →",type="primary")
        if back: st.session_state.nr_step=1; st.rerun()
        if proceed:
            scored={}
            for q in questions:
                answer=answers.get(q['id'])
                options=json.loads(q['options']) if isinstance(q['options'],str) else q['options']
                weights=json.loads(q['weights']) if isinstance(q['weights'],str) else q['weights']
                score=weights[options.index(answer)] if answer in options else 0
                scored[str(q['id'])]={'answer':answer,'score':score}
            st.session_state.nr_answers=scored; st.session_state.nr_step=3; st.rerun()

def _nr_step3(user):
    questions=get_active_questions(); config=get_sbd_config()
    total=sum(v['score'] for v in st.session_state.nr_answers.values())
    max_s=sum(q['max_score'] for q in questions); pct=(total/max_s*100) if max_s>0 else 0
    outcome=determine_sbd_outcome(total,max_s,config); ocfg=OUTCOME_CONFIG.get(outcome,{})
    score_color="#dc2626" if pct>=65 else ("#d97706" if pct>=40 else ("#f59e0b" if pct>=20 else "#16a34a"))
    score_bg="#fef2f2" if pct>=65 else ("#fffbeb" if pct>=40 else ("#fefce8" if pct>=20 else "#f0fdf4"))
    st.markdown("### 📝 Review Your Answers")
    col1,col2=st.columns([3,2])
    with col1:
        st.markdown(f'<div class="card"><div style="font-weight:600;">{st.session_state.nr_project_name}</div><div style="color:#64748b;font-size:.87rem;">{st.session_state.nr_project_desc or "No description"}</div></div>',unsafe_allow_html=True)
        for q in questions:
            ad=st.session_state.nr_answers.get(str(q['id']),{}); ans=ad.get('answer','—'); sc=ad.get('score',0); mx=q['max_score']
            sc_pct=(sc/mx*100) if mx>0 else 0; sc_col="#dc2626" if sc_pct>=70 else ("#d97706" if sc_pct>=40 else "#16a34a")
            st.markdown(f'<div style="border:1px solid #e2e8f0;border-radius:8px;padding:.75rem 1rem;margin-bottom:.5rem;display:flex;justify-content:space-between;align-items:center;"><div><div style="font-size:.8rem;color:#64748b;">{q["category"]}</div><div style="font-weight:500;font-size:.9rem;">{q["text"]}</div><div style="font-size:.85rem;color:#475569;">→ {ans}</div></div><div style="font-family:monospace;font-weight:700;color:{sc_col};">{sc}/{mx}</div></div>',unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div style="background:{score_bg};border:2px solid {score_color};border-radius:12px;padding:1.5rem;text-align:center;margin-bottom:1rem;"><div style="font-size:.8rem;font-weight:600;text-transform:uppercase;color:{score_color};margin-bottom:.5rem;">Risk Score</div><div style="font-family:monospace;font-size:3rem;font-weight:700;color:{score_color};line-height:1;">{pct:.0f}%</div><div style="font-size:.8rem;color:#64748b;">{total:.0f}/{max_s} points</div></div><div class="outcome-banner {ocfg.get("class","")}"><div style="font-size:1.5rem;">{ocfg.get("icon","?")}</div><div><div style="font-weight:700;font-size:.9rem;">Predicted Outcome</div><div style="font-weight:600;color:{ocfg.get("color","#000")};">{ocfg.get("label",outcome)}</div></div></div>',unsafe_allow_html=True)
    st.markdown("<br>",unsafe_allow_html=True)
    c1,_,c3=st.columns([1,1,2])
    with c1:
        if st.button("← Revise"): st.session_state.nr_step=2; st.rerun()
    with c3:
        if st.button("✅ Submit Request",type="primary",use_container_width=True):
            rid,ref=create_request(st.session_state.nr_project_name,st.session_state.nr_project_desc,user['id'])
            t=save_answers(rid,st.session_state.nr_answers)
            finalize_request(rid,outcome,t,user['id'])
            st.session_state.nr_request_id=rid; st.session_state.nr_ref=ref
            st.session_state.nr_outcome=outcome; st.session_state.nr_score=pct
            st.session_state.nr_step=4; st.rerun()

def _nr_step4(user):
    outcome=st.session_state.get('nr_outcome','no_sbd'); ref=st.session_state.get('nr_ref','')
    score=st.session_state.get('nr_score',0); rid=st.session_state.get('nr_request_id')
    ocfg=OUTCOME_CONFIG.get(outcome,{})
    st.markdown(f'<div style="text-align:center;padding:2rem 0;"><div style="font-size:4rem;">{ocfg.get("icon","📋")}</div><h2 style="font-family:monospace;color:#0f172a;">Request Submitted!</h2><div class="ref-number" style="font-size:1.1rem;display:inline-block;margin-bottom:1.5rem;">{ref}</div></div>',unsafe_allow_html=True)
    c1,c2,c3=st.columns([1,2,1])
    with c2:
        st.markdown(f'<div class="outcome-banner {ocfg.get("class","")}"><div style="font-size:2rem;">{ocfg.get("icon","?")}</div><div><div style="font-weight:600;font-size:.85rem;color:#64748b;">Preliminary Assessment</div><div style="font-weight:700;font-size:1.1rem;color:{ocfg.get("color","#000")};">{ocfg.get("label",outcome)}</div><div style="font-size:.8rem;color:#64748b;">Risk Score: {score:.0f}%</div></div></div>',unsafe_allow_html=True)
        ca,cb=st.columns(2)
        with ca:
            if st.button("View Request →",type="primary",use_container_width=True):
                st.session_state.selected_request_id=rid; st.session_state.page="request_detail"
                for k in ['nr_step','nr_request_id','nr_answers','nr_project_name','nr_project_desc','nr_ref','nr_outcome','nr_score']:
                    st.session_state.pop(k,None)
                st.rerun()
        with cb:
            if st.button("New Request",use_container_width=True):
                for k in ['nr_step','nr_request_id','nr_answers','nr_project_name','nr_project_desc','nr_ref','nr_outcome','nr_score']:
                    st.session_state.pop(k,None)
                st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: REQUEST DETAIL
# ─────────────────────────────────────────────────────────────────────────────

def show_request_detail(user):
    rid=st.session_state.get('selected_request_id')
    if not rid: st.error("No request selected."); return
    is_mgr=user['role'] in ['admin','sbd_manager']
    if not is_mgr and not can_user_access(rid,user['id']): st.error("🚫 Access denied."); return
    req=get_request_by_id(rid)
    if not req: st.error("Request not found."); return
    has_write=(req['created_by']==user['id'] or is_mgr or can_user_access(rid,user['id'],require_write=True))
    is_locked=bool(req.get('is_locked'))
    if st.button("← Back"): st.session_state.page="my_requests"; st.rerun()
    lock_html = '<div class="lock-banner">🔒 Locked — sign-off received. No changes allowed.</div>' if is_locked else ""
    st.markdown(f'<div class="page-header"><div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap;"><div class="page-title">{req["project_name"]}</div><span class="ref-number">{req["ref_number"]}</span>{status_badge(req["status"])}{outcome_badge(req.get("sbd_outcome")) if req.get("sbd_outcome") else ""}</div>{lock_html}</div>',unsafe_allow_html=True)
    st.markdown("### Progress")
    st.markdown(render_pipeline(req['status']),unsafe_allow_html=True)
    tabs=st.tabs(["📋 Overview","🔍 Assessment","👥 Team & Access","📜 Audit Trail"])
    with tabs[0]: _rd_overview(req,user,has_write,is_locked,is_mgr)
    with tabs[1]: _rd_assessment(req)
    with tabs[2]: _rd_team(req,user,has_write,is_locked,is_mgr)
    with tabs[3]: _rd_audit(req)

def _rd_overview(req,user,has_write,is_locked,is_mgr):
    c1,c2=st.columns([3,2])
    with c1:
        st.markdown(f'<div class="card"><div style="margin-bottom:.75rem;"><div style="font-size:.75rem;color:#94a3b8;text-transform:uppercase;">Project Name</div><div style="font-weight:600;font-size:1.05rem;">{req["project_name"]}</div></div><div style="margin-bottom:.75rem;"><div style="font-size:.75rem;color:#94a3b8;">Description</div><div style="color:#334155;">{req.get("project_description") or "Not provided"}</div></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:1rem;"><div><div style="font-size:.75rem;color:#94a3b8;">Submitted</div><div style="font-weight:500;">{format_date(req.get("submitted_at"))}</div></div><div><div style="font-size:.75rem;color:#94a3b8;">Risk Score</div><div style="font-weight:600;font-family:monospace;">{req.get("total_score",0):.1f} pts</div></div></div></div>',unsafe_allow_html=True)
        if req.get('sbd_outcome'):
            ocfg=OUTCOME_CONFIG.get(req['sbd_outcome'],{})
            st.markdown(f'<div class="outcome-banner {ocfg.get("class","")}"><div style="font-size:2rem;">{ocfg.get("icon","?")}</div><div><div style="font-weight:600;font-size:.85rem;">SbD Determination</div><div style="font-weight:700;font-size:1.1rem;color:{ocfg.get("color","#000")};">{ocfg.get("label",req["sbd_outcome"])}</div></div></div>',unsafe_allow_html=True)
        if req.get('architect_url'):
            arch_notes_html = f'<div style="margin-top:.5rem;color:#64748b;font-size:.85rem;">{req.get("architect_notes","")}</div>' if req.get('architect_notes') else ""
    st.markdown(f'<div class="card">🔗 <a href="{req["architect_url"]}" target="_blank" style="color:#1e40af;">View Architecture Document</a>{arch_notes_html}</div>',unsafe_allow_html=True)
    with c2:
        st.markdown("**Phase Timeline**")
        phases=[('submitted_at','Submitted','📋'),('awaiting_assignment_at','Assessment Done','📊'),('architect_assigned_at','Architect Assigned','🏗️'),('architect_completed_at','Architecture Done','✅'),('engineer_assigned_at','Engineer Assigned','⚙️'),('engineer_completed_at','Engineering Done','✅'),('assurance_assigned_at','Assurance Assigned','🔍'),('assurance_completed_at','Assurance Done','✅'),('pending_signoff_at','Pending Sign-off','✍️'),('signoff_received_at','Sign-off Received','🎉')]
        html='<div class="timeline">'
        for field,label,icon in phases:
            dt=req.get(field); cls="complete" if dt else "pending"; color="#065f46" if dt else "#94a3b8"
            html+=f'<div class="timeline-item"><div class="timeline-dot {cls}"></div><div style="display:flex;justify-content:space-between;"><span style="font-size:.85rem;font-weight:500;color:{"#0f172a" if dt else "#94a3b8"};">{icon} {label}</span><span style="font-size:.75rem;color:{color};font-family:monospace;">{format_date(dt) if dt else "Pending"}</span></div></div>'
        html+='</div>'; st.markdown(html,unsafe_allow_html=True)
        for rk,label,icon in [('architect_id','Security Architect','🏗️'),('engineer_id','Security Engineer','⚙️'),('assurance_id','Assurance','🔍')]:
            if req.get(rk):
                p=get_user_by_id(req[rk])
                if p: st.markdown(f'<div style="display:flex;align-items:center;gap:.5rem;padding:.5rem;border:1px solid #e2e8f0;border-radius:8px;margin-bottom:.5rem;">{icon} <div><div style="font-weight:600;font-size:.85rem;">{p["name"]}</div><div style="font-size:.75rem;color:#94a3b8;">{label}</div></div></div>',unsafe_allow_html=True)
    if not is_locked: _rd_actions(req,user,has_write,is_mgr)

def _rd_actions(req,user,has_write,is_mgr):
    status=req['status']; rid=req['id']
    st.markdown("---"); st.markdown("**Actions**")
    cols=st.columns(4); ci=0
    if is_mgr:
        if status=='pending_review':
            with cols[ci%4]:
                if st.button("✅ Confirm Review",type="primary",key="act_confirm"): update_request_status(rid,'awaiting_assignment',user['id'],'Review completed'); st.rerun()
            ci+=1
            with cols[ci%4]:
                if st.button("🚫 Mark Invalid",key="act_invalid"): update_request_status(rid,'no_sbd_needed',user['id'],'Marked invalid'); st.rerun()
            ci+=1
        if status=='architect_assigned':
            with cols[ci%4]:
                if st.button("✅ Architect Done",type="primary",key="act_archdone"): update_request_status(rid,'architect_completed',user['id'],'Architecture done'); st.rerun()
            ci+=1
        if status=='architect_completed':
            with cols[ci%4]:
                if st.button("➡️ Assign Engineer",type="primary",key="act_toeng"): update_request_status(rid,'engineer_assigned',user['id'],'Moving to engineer'); st.rerun()
            ci+=1
        if status=='engineer_assigned':
            with cols[ci%4]:
                if st.button("✅ Engineering Done",type="primary",key="act_engdone"): update_request_status(rid,'engineer_completed',user['id'],'Engineering done'); st.rerun()
            ci+=1
        if status=='engineer_completed':
            with cols[ci%4]:
                if st.button("➡️ Assign Assurance",type="primary",key="act_toassur"): update_request_status(rid,'assurance_assigned',user['id'],'Moving to assurance'); st.rerun()
            ci+=1
        if status=='assurance_assigned':
            with cols[ci%4]:
                if st.button("✅ Assurance Done",type="primary",key="act_assurdone"): update_request_status(rid,'assurance_completed',user['id'],'Assurance done'); st.rerun()
            ci+=1
        if status=='assurance_completed':
            with cols[ci%4]:
                if st.button("➡️ Move to Sign-off",type="primary",key="act_tosignoff"): update_request_status(rid,'pending_signoff',user['id'],'Moved to sign-off'); st.rerun()
            ci+=1
        if status=='pending_signoff':
            with cols[ci%4]:
                if st.button("🎉 Record Sign-off",type="primary",key="act_signoff"): update_request_status(rid,'signoff_received',user['id'],'Sign-off received',{'signoff_by':user['id']}); st.rerun()
            ci+=1
    if (req.get('architect_id')==user['id'] or is_mgr) and status in ['architect_assigned','architect_completed']:
        with st.expander("🔗 Add Architecture Document"):
            au=st.text_input("URL",value=req.get('architect_url',''))
            an=st.text_area("Notes",value=req.get('architect_notes',''),height=80)
            if st.button("Save",key="save_arch"):
                conn=get_connection(); conn.execute("UPDATE requests SET architect_url=?,architect_notes=? WHERE id=?",(au,an,rid)); conn.commit(); conn.close(); st.success("Saved!"); st.rerun()

def _rd_assessment(req):
    answers=get_request_answers(req['id'])
    if not answers: st.info("No answers found."); return
    st.markdown(f"**Total Risk Score: {req.get('total_score',0):.1f} points**")
    by_cat={}
    for a in answers: by_cat.setdefault(a['category'],[]).append(a)
    for cat,cat_answers in by_cat.items():
        st.markdown(f"#### {cat}")
        for a in cat_answers:
            wts=json.loads(a['weights']) if isinstance(a['weights'],str) else a['weights']
            mx=max(wts) if wts else 10; sc=a['score']; pct=(sc/mx*100) if mx>0 else 0
            bc="#ef4444" if pct>=70 else ("#f59e0b" if pct>=40 else "#10b981")
            st.markdown(f'<div style="border:1px solid #e2e8f0;border-radius:8px;padding:1rem;margin-bottom:.75rem;"><div style="font-weight:600;margin-bottom:.5rem;">{a["question_text"]}</div><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem;"><div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:6px;padding:.25rem .75rem;font-size:.88rem;color:#0c4a6e;">✓ {a["answer"]}</div><div style="font-family:monospace;font-weight:700;color:{bc};">{sc}/{mx}</div></div><div style="background:#f1f5f9;border-radius:999px;height:5px;"><div style="background:{bc};height:5px;border-radius:999px;width:{pct:.1f}%;"></div></div></div>',unsafe_allow_html=True)

def _rd_team(req,user,has_write,is_locked,is_mgr):
    st.markdown("#### Team Access")
    creator=get_user_by_id(req['created_by'])
    if creator:
        st.markdown(f'<div style="display:flex;align-items:center;gap:.75rem;padding:.75rem;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;margin-bottom:.75rem;"><div style="width:36px;height:36px;background:#1e40af;border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-weight:700;">{creator["name"][0]}</div><div style="flex:1;"><div style="font-weight:600;">{creator["name"]}</div><div style="font-size:.8rem;color:#64748b;">{creator["email"]}</div></div><span class="badge badge-active">Owner</span></div>',unsafe_allow_html=True)
    perms=get_permissions(req['id'])
    for p in perms:
        c1,c2=st.columns([5,1])
        with c1: st.markdown(f'<div style="display:flex;align-items:center;gap:.75rem;padding:.6rem;border:1px solid #e2e8f0;border-radius:8px;"><div style="width:30px;height:30px;background:#64748b;border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-size:.8rem;font-weight:700;">{p["name"][0]}</div><div><div style="font-weight:500;font-size:.9rem;">{p["name"]}</div><div style="font-size:.75rem;color:#94a3b8;">{p["email"]}</div></div><span class="badge {"badge-active" if p["permission"]=="write" else "badge-awaiting"}">{p["permission"].upper()}</span></div>',unsafe_allow_html=True)
        with c2:
            if (has_write or is_mgr) and not is_locked:
                if st.button("Remove",key=f"rm_{p['user_id']}"): remove_permission(req['id'],p['user_id']); st.rerun()
    if (has_write or is_mgr) and not is_locked:
        st.markdown("---"); st.markdown("**Grant Access**")
        all_u=get_all_users(); existing={p['user_id'] for p in perms}|{req['created_by']}
        avail=[u for u in all_u if u['id'] not in existing and u['id']!=user['id']]
        if avail:
            unames={u['id']:f"{u['name']} ({u['username']})" for u in avail}
            col1,col2,col3=st.columns([3,2,1])
            with col1: sel=st.selectbox("User",options=[u['id'] for u in avail],format_func=lambda x:unames[x])
            with col2: pl=st.selectbox("Permission",["read","write"])
            with col3:
                st.markdown("<br>",unsafe_allow_html=True)
                if st.button("Grant",type="primary"): add_permission(req['id'],sel,pl,user['id']); st.success("Granted!"); st.rerun()

def _rd_audit(req):
    history=get_status_history(req['id'])
    if not history: st.info("No history."); return
    html='<div class="timeline">'
    for item in reversed(history):
        item_notes_html = f'<div style="font-size:.8rem;color:#475569;font-style:italic;">{item["notes"]}</div>' if item.get("notes") else ""
        html+=f'<div class="timeline-item"><div class="timeline-dot complete"></div><div><div style="font-weight:600;font-size:.88rem;">{item.get("from_status","Created") or "Created"} → {item["to_status"]}</div><div style="font-size:.8rem;color:#64748b;">By {item["changed_by_name"]} · {format_date(item["created_at"])}</div>{item_notes_html}</div></div>'
    html+='</div>'; st.markdown(html,unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: PENDING REVIEW
# ─────────────────────────────────────────────────────────────────────────────

def show_pending_review(user):
    if user['role'] not in ['admin','sbd_manager']: st.error("Access denied."); return
    st.markdown('<div class="page-header"><div class="page-title">📥 Pending Review</div><div class="page-subtitle">Requests awaiting initial review</div></div>',unsafe_allow_html=True)
    requests=get_requests_by_status(['pending_review'])
    if not requests:
        st.markdown('<div class="card" style="text-align:center;padding:3rem;color:#94a3b8;"><div style="font-size:2.5rem;">✅</div><div style="font-weight:600;">All caught up!</div></div>',unsafe_allow_html=True); return
    st.markdown(f"**{len(requests)}** pending")
    for req in requests:
        c1,c2=st.columns([4,2])
        with c1:
            st.markdown(f'<div style="padding:.75rem;border:1px solid #e2e8f0;border-radius:8px;margin-bottom:.5rem;"><div style="display:flex;gap:.75rem;align-items:center;margin-bottom:.5rem;"><span class="ref-number">{req["ref_number"]}</span>{outcome_badge(req.get("sbd_outcome"))}</div><div style="font-weight:600;">{req["project_name"]}</div><div style="font-size:.82rem;color:#64748b;">Submitted {format_date(req["created_at"])} · Score: {req.get("total_score",0):.1f}</div></div>',unsafe_allow_html=True)
        with c2:
            st.markdown("<br>",unsafe_allow_html=True)
            b1,b2=st.columns(2)
            with b1:
                if st.button("View",key=f"pr_view_{req['id']}"): st.session_state.selected_request_id=req['id']; st.session_state.page="request_detail"; st.rerun()
            with b2:
                if st.button("✅ Confirm",key=f"pr_conf_{req['id']}",type="primary"): update_request_status(req['id'],'awaiting_assignment',user['id'],'Review completed'); st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: ASSIGN RESOURCES
# ─────────────────────────────────────────────────────────────────────────────

def show_assign_resources(user):
    if user['role'] not in ['admin','sbd_manager']: st.error("Access denied."); return
    st.markdown('<div class="page-header"><div class="page-title">👥 Assign Resources</div><div class="page-subtitle">Assign security professionals to requests</div></div>',unsafe_allow_html=True)
    requests=get_requests_by_status(['awaiting_assignment','architect_assigned','architect_completed','engineer_assigned','engineer_completed','assurance_assigned'])
    if not requests: st.info("No requests need assignment."); return
    architects=get_all_users('security_architect'); engineers=get_all_users('security_engineer'); assurance=get_all_users('assurance')
    for req in requests:
        status=req['status']
        if status=='awaiting_assignment': al,ai,needs='Assign Security Architect','🏗️','architect'
        elif status=='architect_completed': al,ai,needs='Assign Security Engineer','⚙️','engineer'
        elif status=='engineer_completed': al,ai,needs='Assign Assurance','🔍','assurance'
        else: al,ai,needs='In Progress','⚙️',None
        with st.expander(f"{ai} {req['ref_number']} — {req['project_name']} | {al}"):
            c1,c2=st.columns([3,2])
            with c1: st.markdown(f'<div style="margin-bottom:.75rem;"><span class="ref-number">{req["ref_number"]}</span> {status_badge(status)}</div><div style="font-weight:600;">{req["project_name"]}</div><div style="font-size:.82rem;color:#64748b;">{format_date(req["created_at"])} · Score: {req.get("total_score",0):.1f}</div>',unsafe_allow_html=True)
            with c2:
                if st.button("View",key=f"ar_view_{req['id']}"): st.session_state.selected_request_id=req['id']; st.session_state.page="request_detail"; st.rerun()
            people={'architect':architects,'engineer':engineers,'assurance':assurance}.get(needs,[])
            if needs and people:
                opts={p['id']:f"{p['name']} ({p['username']})" for p in people}
                cur=req.get(f'{needs}_id')
                col_a,col_b=st.columns([3,1])
                with col_a:
                    sel=st.selectbox(f"Select {needs.title()}",options=list(opts.keys()),format_func=lambda x:opts[x],key=f"sel_{needs}_{req['id']}",index=list(opts.keys()).index(cur) if cur in opts else 0)
                with col_b:
                    st.markdown("<br>",unsafe_allow_html=True)
                    if st.button("Assign →",key=f"assign_{needs}_{req['id']}",type="primary"):
                        conn=get_connection(); conn.execute(f"UPDATE requests SET {needs}_id=? WHERE id=?",(sel,req['id'])); conn.commit(); conn.close()
                        ns={'architect':'architect_assigned','engineer':'engineer_assigned','assurance':'assurance_assigned'}[needs]
                        update_request_status(req['id'],ns,user['id'],f'{needs.title()} assigned: {opts[sel]}'); st.success("Assigned!"); st.rerun()
            elif needs: st.warning(f"No {needs} users found. Add via User Management.")

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: SIGN-OFF QUEUE
# ─────────────────────────────────────────────────────────────────────────────

def show_signoff_queue(user):
    if user['role'] not in ['admin','sbd_manager']: st.error("Access denied."); return
    st.markdown('<div class="page-header"><div class="page-title">✅ Sign-Off Queue</div><div class="page-subtitle">Requests awaiting final sign-off</div></div>',unsafe_allow_html=True)
    requests=get_requests_by_status(['assurance_completed','pending_signoff'])
    if not requests: st.info("No requests in sign-off queue."); return
    for req in requests:
        c1,c2,c3=st.columns([4,2,2])
        with c1: st.markdown(f'<div style="padding:.75rem;border:1px solid #e2e8f0;border-radius:8px;"><span class="ref-number">{req["ref_number"]}</span> {status_badge(req["status"])} {outcome_badge(req.get("sbd_outcome"))}<div style="font-weight:600;margin-top:.25rem;">{req["project_name"]}</div><div style="font-size:.82rem;color:#64748b;">{format_date(req["created_at"])}</div></div>',unsafe_allow_html=True)
        with c2:
            st.markdown("<br>",unsafe_allow_html=True)
            if req['status']=='assurance_completed':
                if st.button("➡️ Move to Sign-off",key=f"so_move_{req['id']}",type="primary"): update_request_status(req['id'],'pending_signoff',user['id'],'Moved to sign-off'); st.rerun()
        with c3:
            st.markdown("<br>",unsafe_allow_html=True)
            b1,b2=st.columns(2)
            with b1:
                if st.button("View",key=f"so_view_{req['id']}"): st.session_state.selected_request_id=req['id']; st.session_state.page="request_detail"; st.rerun()
            with b2:
                if req['status']=='pending_signoff':
                    if st.button("🎉 Sign Off",key=f"so_{req['id']}",type="primary"): update_request_status(req['id'],'signoff_received',user['id'],'Sign-off received',{'signoff_by':user['id']}); st.success("Done!"); st.rerun()
        st.markdown("<hr style='margin:.5rem 0;'>",unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: ALL REQUESTS
# ─────────────────────────────────────────────────────────────────────────────

def show_all_requests(user):
    if user['role'] not in ['admin','sbd_manager']: st.error("Access denied."); return
    st.markdown('<div class="page-header"><div class="page-title">📊 All Requests</div><div class="page-subtitle">Complete view of all SbD requests</div></div>',unsafe_allow_html=True)
    c1,c2=st.columns([2,3])
    with c1: sf=st.selectbox("Status",["All","pending_review","awaiting_assignment","architect_assigned","architect_completed","engineer_assigned","engineer_completed","assurance_assigned","assurance_completed","pending_signoff","signoff_received","no_sbd_needed"])
    with c2: search=st.text_input("Search",placeholder="Project name or ref...")
    requests=get_all_requests(sf if sf!="All" else None)
    if search: s=search.lower(); requests=[r for r in requests if s in r['project_name'].lower() or s in r['ref_number'].lower()]
    st.markdown(f"**{len(requests)}** requests")
    for req in requests:
        c1,c2,c3,c4,c5=st.columns([2,4,2,2,1])
        with c1: st.markdown(f'<span class="ref-number">{req["ref_number"]}</span>',unsafe_allow_html=True)
        with c2: st.markdown(f"**{req['project_name'][:40]}**"); st.caption(format_date(req['created_at']))
        with c3: st.markdown(status_badge(req['status']),unsafe_allow_html=True)
        with c4:
            if req.get('sbd_outcome'): st.markdown(outcome_badge(req['sbd_outcome']),unsafe_allow_html=True)
            st.caption(f"Score: {req.get('total_score',0):.0f}")
        with c5:
            if st.button("→",key=f"all_{req['id']}"): st.session_state.selected_request_id=req['id']; st.session_state.page="request_detail"; st.rerun()
        st.markdown("<hr style='margin:.25rem 0;border-color:#f8fafc;'>",unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: ADMIN PANEL
# ─────────────────────────────────────────────────────────────────────────────

def show_admin_panel(user):
    if user['role']!='admin': st.error("Admin only."); return
    st.markdown('<div class="page-header"><div class="page-title">⚙️ Admin Panel</div><div class="page-subtitle">Manage questions and configuration</div></div>',unsafe_allow_html=True)
    tab1,tab2=st.tabs(["📝 Questions","⚖️ Scoring Thresholds"])
    with tab1: _admin_questions(user)
    with tab2: _admin_thresholds()

def _admin_questions(user):
    questions=get_all_questions()
    c1,c2=st.columns([4,1])
    with c1: st.markdown(f"**{len(questions)}** questions ({sum(1 for q in questions if q['is_active'])} active)")
    with c2:
        if st.button("➕ Add",type="primary",use_container_width=True): st.session_state.show_add_q=True
    if st.session_state.get('show_add_q'):
        with st.expander("➕ New Question",expanded=True): _q_form(None)
    st.markdown("---")
    for q in questions:
        opts=json.loads(q['options']) if isinstance(q['options'],str) else (q['options'] or [])
        wts=json.loads(q['weights']) if isinstance(q['weights'],str) else (q['weights'] or [])
        with st.expander(f"{'🟢' if q['is_active'] else '🔴'} Q{q['order_index']} — {q['text'][:60]}... | {q['category']}"):
            c1,c2=st.columns([3,1])
            with c1:
                st.markdown(f"**Category:** {q['category']} | **Max Score:** {q['max_score']} | **Active:** {'Yes' if q['is_active'] else 'No'}")
                for opt,wt in zip(opts,wts):
                    sc_col="#ef4444" if wt/q['max_score']>=.7 else ("#f59e0b" if wt/q['max_score']>=.4 else "#10b981") if q['max_score'] else "#10b981"
                    st.markdown(f'<div style="display:flex;justify-content:space-between;padding:.3rem .5rem;border-bottom:1px solid #f1f5f9;"><span style="font-size:.85rem;">{opt}</span><span style="font-family:monospace;font-size:.8rem;color:{sc_col};font-weight:700;">{wt} pts</span></div>',unsafe_allow_html=True)
            with c2:
                if st.button("✏️ Edit",key=f"edit_{q['id']}"): st.session_state[f"eq_{q['id']}"]=True
                if st.button("🗑️ Deactivate" if q['is_active'] else "✅ Activate",key=f"tog_{q['id']}"):
                    update_question(q['id'],q['text'],q.get('description',''),opts,wts,q['max_score'],q['category'],q['order_index'],0 if q['is_active'] else 1); st.rerun()
            if st.session_state.get(f"eq_{q['id']}"): _q_form(q)

def _q_form(q):
    is_edit=q is not None; pfx=f"q_{q['id']}_" if is_edit else "new_"
    with st.form(f"qform_{pfx}"):
        text=st.text_input("Question *",value=q['text'] if is_edit else "")
        desc=st.text_input("Help Text",value=q.get('description','') if is_edit else "")
        c1,c2,c3=st.columns(3)
        with c1: cat=st.text_input("Category",value=q.get('category','General') if is_edit else "General")
        with c2: order=st.number_input("Order",value=q.get('order_index',0) if is_edit else 0,min_value=0)
        with c3: active=st.checkbox("Active",value=bool(q.get('is_active',1)) if is_edit else True)
        ex_opts=json.loads(q['options']) if is_edit and isinstance(q['options'],str) else (q['options'] if is_edit else ["Option 1","Option 2","Option 3","Option 4"])
        ex_wts=json.loads(q['weights']) if is_edit and isinstance(q['weights'],str) else (q['weights'] if is_edit else [0,3,6,10])
        num=st.number_input("# Options",min_value=2,max_value=8,value=len(ex_opts),key=f"num_{pfx}")
        new_opts=[]; new_wts=[]
        for i in range(int(num)):
            co,cw=st.columns([4,1])
            with co: new_opts.append(st.text_input(f"Option {i+1}",value=ex_opts[i] if i<len(ex_opts) else "",key=f"o_{pfx}{i}"))
            with cw: new_wts.append(st.number_input("Score",value=int(ex_wts[i]) if i<len(ex_wts) else 0,min_value=0,max_value=100,key=f"w_{pfx}{i}"))
        cs,cc=st.columns([1,3])
        with cs: saved=st.form_submit_button("💾 Save",type="primary")
        with cc: cancel=st.form_submit_button("Cancel")
        if saved:
            if not text.strip(): st.error("Question required.")
            elif not all(o.strip() for o in new_opts): st.error("All options need text.")
            else:
                ms=max(new_wts) if new_wts else 10
                if is_edit: update_question(q['id'],text,desc,new_opts,new_wts,ms,cat,order,int(active)); st.session_state[f"eq_{q['id']}"]=False
                else: create_question(text,desc,'single_choice',new_opts,new_wts,ms,cat,order); st.session_state.show_add_q=False
                st.success("Saved!"); st.rerun()
        if cancel:
            if is_edit: st.session_state[f"eq_{q['id']}"]=False
            else: st.session_state.show_add_q=False
            st.rerun()

def _admin_thresholds():
    config=get_sbd_config()
    st.markdown("### SbD Scoring Thresholds")
    st.markdown('<div class="alert alert-info">ℹ️ Thresholds are percentage-based. The system calculates what % of the maximum possible score a project achieved.</div>',unsafe_allow_html=True)
    with st.form("thresh_form"):
        t1=st.slider("🟢 No SBD Required — scores up to (%)",5,50,int(config.get('threshold_no_sbd',20)))
        t2=st.slider("🟡 SBD Stage 1 — scores up to (%)",10,60,int(config.get('threshold_stage1',40)))
        t3=st.slider("🟠 SBD Stage 2 — scores up to (%)",30,90,int(config.get('threshold_stage2',65)))
        st.markdown(f'<div class="card"><div style="font-weight:600;margin-bottom:.75rem;">Preview</div><div style="display:flex;gap:.5rem;flex-wrap:wrap;"><span style="background:#f1f5f9;color:#475569;padding:.3rem .75rem;border-radius:999px;font-size:.8rem;font-weight:600;">0–{t1}% → No SBD</span><span style="background:#fefce8;color:#713f12;padding:.3rem .75rem;border-radius:999px;font-size:.8rem;font-weight:600;">{t1+1}–{t2}% → Stage 1</span><span style="background:#fff7ed;color:#7c2d12;padding:.3rem .75rem;border-radius:999px;font-size:.8rem;font-weight:600;">{t2+1}–{t3}% → Stage 2</span><span style="background:#fef2f2;color:#7f1d1d;padding:.3rem .75rem;border-radius:999px;font-size:.8rem;font-weight:600;">{t3+1}–100% → Full SBD</span></div></div>',unsafe_allow_html=True)
        if st.form_submit_button("💾 Save Thresholds",type="primary"):
            if t1<t2<t3: update_sbd_config('threshold_no_sbd',str(t1)); update_sbd_config('threshold_stage1',str(t2)); update_sbd_config('threshold_stage2',str(t3)); st.success("Saved!"); st.rerun()
            else: st.error("Thresholds must be ascending.")

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: USER MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

ROLES=['project_member','security_architect','security_engineer','assurance','sbd_manager','admin']
ROLE_LABELS={'project_member':'👤 Project Member','security_architect':'🏗️ Security Architect','security_engineer':'⚙️ Security Engineer','assurance':'🔍 Assurance','sbd_manager':'📋 SbD Manager','admin':'⚙️ Admin'}

def show_user_management(user):
    if user['role']!='admin': st.error("Admin only."); return
    st.markdown('<div class="page-header"><div class="page-title">👤 User Management</div><div class="page-subtitle">Manage system users and roles</div></div>',unsafe_allow_html=True)
    tab1,tab2=st.tabs(["👥 Users","➕ Add User"])
    with tab1:
        users=get_all_users(); rf=st.selectbox("Filter",["All"]+ROLES)
        if rf!="All": users=[u for u in users if u['role']==rf]
        st.markdown(f"**{len(users)}** users")
        for u in users:
            c1,c2,c3,c4=st.columns([3,2,2,1])
            with c1: st.markdown(f'<div style="display:flex;align-items:center;gap:.5rem;"><div style="width:32px;height:32px;background:#1e40af;border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-weight:700;font-size:.85rem;flex-shrink:0;">{u["name"][0]}</div><div><div style="font-weight:600;font-size:.9rem;">{u["name"]}</div><div style="font-size:.75rem;color:#94a3b8;">@{u["username"]}</div></div></div>',unsafe_allow_html=True)
            with c2: st.caption(u['email'])
            with c3:
                nr=st.selectbox("Role",options=ROLES,index=ROLES.index(u['role']) if u['role'] in ROLES else 0,key=f"r_{u['id']}",format_func=lambda r:ROLE_LABELS.get(r,r),label_visibility="collapsed")
                if nr!=u['role']:
                    if st.button("Save",key=f"sr_{u['id']}"): update_user_role(u['id'],nr); st.success("Updated!"); st.rerun()
            with c4:
                if u['id']!=user['id']:
                    if st.button("🗑️",key=f"du_{u['id']}"): deactivate_user(u['id']); st.rerun()
            st.markdown("<hr style='margin:.25rem 0;border-color:#f8fafc;'>",unsafe_allow_html=True)
    with tab2:
        with st.form("add_user"):
            c1,c2=st.columns(2)
            with c1: name=st.text_input("Full Name *"); username=st.text_input("Username *")
            with c2: email=st.text_input("Email *"); password=st.text_input("Password *",type="password")
            role=st.selectbox("Role",options=ROLES,format_func=lambda r:ROLE_LABELS.get(r,r))
            if st.form_submit_button("➕ Create User",type="primary"):
                if not all([name,username,email,password]): st.error("All fields required.")
                elif '@' not in email: st.error("Invalid email.")
                elif len(password)<6: st.error("Password min 6 chars.")
                else:
                    ok,msg=create_user(username,password,name,email,role)
                    st.success(f"User '{name}' created!") if ok else st.error(msg)

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

init_db()
inject_styles()

for k,v in [("authenticated",False),("user",None),("page","dashboard")]:
    if k not in st.session_state: st.session_state[k]=v

if not st.session_state.authenticated:
    login_page()
else:
    user=st.session_state.user
    with st.sidebar:
        st.markdown(f'<div class="sidebar-header"><div class="sidebar-logo">🔐</div><div class="sidebar-title">SbD Portal</div></div>',unsafe_allow_html=True)
        st.markdown(f'<div class="user-badge"><span class="user-avatar">{user["name"][0].upper()}</span><div><div class="user-name">{user["name"]}</div><div class="user-role">{user["role"].replace("_"," ").title()}</div></div></div>',unsafe_allow_html=True)
        st.markdown("---")
        nav=[("🏠","Dashboard","dashboard"),("📋","My Requests","my_requests"),("➕","New Request","new_request")]
        if user['role'] in ['sbd_manager','admin']:
            nav+=[("📥","Pending Review","pending_review"),("👥","Assign Resources","assign_resources"),("✅","Sign-Off Queue","signoff_queue"),("📊","All Requests","all_requests")]
        if user['role']=='admin':
            nav+=[("⚙️","Admin Panel","admin_panel"),("👤","User Management","user_management")]
        for icon,label,pk in nav:
            if st.button(f"{icon}  {label}",key=f"nav_{pk}",use_container_width=True,type="primary" if st.session_state.page==pk else "secondary"):
                st.session_state.page=pk; st.rerun()
        st.markdown("---")
        if st.button("🚪  Logout",use_container_width=True): logout(); st.rerun()

    page=st.session_state.page
    if page=="dashboard": show_dashboard(user)
    elif page=="my_requests": show_my_requests(user)
    elif page=="new_request": show_new_request(user)
    elif page=="pending_review": show_pending_review(user)
    elif page=="assign_resources": show_assign_resources(user)
    elif page=="signoff_queue": show_signoff_queue(user)
    elif page=="all_requests": show_all_requests(user)
    elif page=="admin_panel": show_admin_panel(user)
    elif page=="user_management": show_user_management(user)
    elif page=="request_detail": show_request_detail(user)
