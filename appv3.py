import sqlite3, json, hashlib
from datetime import datetime
import streamlit as st

st.set_page_config(page_title="SbD Portal", page_icon="🔐", layout="wide",
                   initial_sidebar_state="expanded")

# ══════════════════════════════════════════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════════════════════════════════════════

DB = "sbd_portal.db"

def _conn():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    c = _conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
        name TEXT NOT NULL, email TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'project_member',
        department TEXT, created_at TEXT NOT NULL, is_active INTEGER DEFAULT 1);

    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL, description TEXT, hint TEXT,
        options TEXT NOT NULL, weights TEXT NOT NULL,
        max_score INTEGER DEFAULT 10,
        category TEXT DEFAULT 'General',
        parent_question_id INTEGER DEFAULT NULL,
        trigger_answer TEXT DEFAULT NULL,
        is_active INTEGER DEFAULT 1,
        order_index INTEGER DEFAULT 0,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        FOREIGN KEY (parent_question_id) REFERENCES questions(id));

    CREATE TABLE IF NOT EXISTS sbd_config (
        key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);

    CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ref_number TEXT UNIQUE NOT NULL,
        project_name TEXT NOT NULL,
        project_description TEXT,
        business_owner TEXT, project_type TEXT, go_live_date TEXT,
        created_by INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft',
        sbd_outcome TEXT,
        total_score REAL DEFAULT 0, max_possible_score REAL DEFAULT 0,
        score_pct REAL DEFAULT 0,
        architect_id INTEGER, architect_url TEXT, architect_notes TEXT,
        engineer_id INTEGER, engineer_notes TEXT,
        assurance_id INTEGER, assurance_notes TEXT,
        signoff_by INTEGER,
        is_locked INTEGER DEFAULT 0,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        submitted_at TEXT,
        architect_assigned_at TEXT, architect_completed_at TEXT,
        engineer_assigned_at TEXT, engineer_completed_at TEXT,
        assurance_assigned_at TEXT, assurance_completed_at TEXT,
        pending_signoff_at TEXT, signoff_received_at TEXT,
        FOREIGN KEY (created_by) REFERENCES users(id));

    CREATE TABLE IF NOT EXISTS request_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL, question_id INTEGER NOT NULL,
        answer TEXT NOT NULL, score REAL DEFAULT 0,
        FOREIGN KEY (request_id) REFERENCES requests(id),
        FOREIGN KEY (question_id) REFERENCES questions(id));

    CREATE TABLE IF NOT EXISTS request_permissions (
        request_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        permission TEXT NOT NULL DEFAULT 'read',
        granted_by INTEGER NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY (request_id, user_id));

    CREATE TABLE IF NOT EXISTS status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL, from_status TEXT, to_status TEXT NOT NULL,
        changed_by INTEGER NOT NULL, notes TEXT, created_at TEXT NOT NULL);

    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        text TEXT NOT NULL, is_internal INTEGER DEFAULT 0,
        created_at TEXT NOT NULL);
    """)
    c.commit()
    _seed(c)
    c.close()

def _seed(c):
    now = datetime.now().isoformat()
    for un,pw,name,email,role,dept in [
        ("admin","admin123","System Administrator","admin@company.com","admin","IT Security"),
        ("sbd_manager","manager123","SbD Programme Manager","sbdmanager@company.com","sbd_manager","Cyber Security"),
        ("architect1","arch123","Alice Chen","alice.chen@company.com","security_architect","Enterprise Architecture"),
        ("architect2","arch123","James Wright","james.wright@company.com","security_architect","Enterprise Architecture"),
        ("engineer1","eng123","Bob Smith","bob.smith@company.com","security_engineer","Security Engineering"),
        ("engineer2","eng123","Sarah Park","sarah.park@company.com","security_engineer","Security Engineering"),
        ("assurance1","assur123","Carol Davis","carol.davis@company.com","assurance","GRC"),
        ("assurance2","assur123","Michael Torres","michael.torres@company.com","assurance","GRC"),
        ("user1","user123","David Johnson","david.johnson@company.com","project_member","Digital Products"),
        ("user2","user123","Eve Wilson","eve.wilson@company.com","project_member","Finance Technology"),
    ]:
        ph = hashlib.sha256(pw.encode()).hexdigest()
        try: c.execute("INSERT OR IGNORE INTO users (username,password_hash,name,email,role,department,created_at) VALUES (?,?,?,?,?,?,?)",(un,ph,name,email,role,dept,now))
        except: pass

    # Questions: (order, text, desc, hint, options_list, weights_list, max_score, category, parent_id, trigger_answer)
    # parent_id references order_index for seeding simplicity — resolved below
    raw_qs = [
        # ── ROOT QUESTIONS (parent_id=None) ─────────────────────────────────
        (1, "What type of project is this?",
         "Select the category that best describes your initiative.",
         None,
         ["Internal tooling / process improvement",
          "New internal application",
          "Customer-facing digital product",
          "Platform / infrastructure change",
          "Third-party SaaS onboarding"],
         [0, 3, 8, 5, 6], 8, "Project Scope", None, None),

        (2, "Does your project process, store, or transmit personal data (PII)?",
         "Includes names, emails, addresses, health records, financial data, or any data that identifies an individual.",
         "Think about all data flows including logs and analytics.",
         ["No personal data involved",
          "Minimal — employee data (internal only)",
          "Moderate — customer names and contact details",
          "Significant — financial or health-related data",
          "Extensive — special category data (biometric, political, etc.)"],
         [0, 2, 5, 8, 10], 10, "Data & Privacy", None, None),

        (3, "What is the data classification of information handled?",
         "Use your organisation's data classification policy as a guide.",
         None,
         ["Public", "Internal Use Only", "Confidential",
          "Highly Confidential", "Restricted / Secret"],
         [0, 1, 4, 7, 10], 10, "Data & Privacy", None, None),

        (4, "What is the expected scale of users or transactions?",
         "Consider peak usage, not just average load.",
         None,
         ["< 50 internal users", "50–500 users", "500–10,000 users",
          "10,000–100,000 users", "> 100,000 users / high-volume transactions"],
         [0, 2, 4, 7, 10], 10, "Exposure & Scale", None, None),

        (5, "Is the project externally accessible (internet-facing)?",
         "Any component reachable from outside the corporate network.",
         None,
         ["No — fully internal network only",
          "Internal with VPN access required",
          "Externally accessible but authenticated only",
          "Fully public-facing (no authentication required)"],
         [0, 2, 7, 10], 10, "Exposure & Scale", None, None),

        (6, "Does the project involve third-party integrations or vendor products?",
         "APIs, SaaS platforms, data feeds, or any software not built in-house.",
         None,
         ["No third-party integrations",
          "1–2 trusted, well-established vendors",
          "3–5 external systems",
          "Many external / less-vetted third parties"],
         [0, 2, 5, 10], 10, "Third-party Risk", None, None),

        (7, "What authentication mechanism does the system use?",
         "For all user-facing entry points into the system.",
         None,
         ["No authentication required",
          "Username and password only",
          "SSO / SAML with corporate IdP",
          "MFA enforced for all users",
          "Passwordless / hardware token"],
         [10, 7, 3, 1, 0], 10, "Access Control", None, None),

        (8, "What regulatory or compliance requirements apply?",
         "Select the most stringent applicable framework.",
         "If multiple apply, select the highest.",
         ["None identified", "Internal policy only",
          "GDPR / data protection legislation",
          "PCI-DSS (payment card data)",
          "HIPAA / clinical data",
          "Multiple strict frameworks (SOX, ISO27001, etc.)"],
         [0, 1, 4, 7, 8, 10], 10, "Compliance", None, None),

        (9, "Does the project involve financial transactions?",
         "Direct handling of payments, transfers, or financial records.",
         None,
         ["No financial data",
          "Financial reporting / read-only",
          "Internal financial workflows",
          "Customer-facing payment processing"],
         [0, 2, 5, 10], 10, "Financial Risk", None, None),

        (10, "What is the business impact if this system is unavailable for 24 hours?",
         "Consider revenue loss, regulatory breach, and reputational damage.",
         None,
         ["Minimal — workarounds exist",
          "Moderate — some business disruption",
          "Significant — major operational impact",
          "Critical — regulatory breach or severe financial loss"],
         [0, 3, 6, 10], 10, "Business Impact", None, None),

        # ── CHILD QUESTIONS (triggered by specific parent answers) ────────────
        # Parent Q5: external access → ask about protections
        (11, "You indicated external access. What perimeter protections are in place?",
         "Describe the controls protecting your externally accessible components.",
         "WAF, DDoS protection, and rate limiting are expected for public-facing systems.",
         ["No perimeter controls in place",
          "Basic firewall rules only",
          "WAF deployed",
          "WAF + DDoS protection + rate limiting",
          "Full Zero Trust / SASE architecture"],
         [10, 7, 4, 2, 0], 10, "Exposure & Scale", 5, "Externally accessible but authenticated only"),

        (12, "You indicated fully public access. Is a Web Application Firewall (WAF) deployed?",
         "Public endpoints without a WAF represent critical unmitigated risk.",
         None,
         ["No WAF",
          "WAF in detection mode only",
          "WAF in active prevention mode",
          "WAF + Bot management + DDoS protection"],
         [10, 6, 3, 0], 10, "Exposure & Scale", 5, "Fully public-facing (no authentication required)"),

        # Parent Q2: significant PII → encryption
        (13, "You indicated significant personal data. Is data encrypted at rest?",
         "Encryption at rest is a baseline requirement for sensitive personal data.",
         None,
         ["No encryption at rest",
          "Partial encryption",
          "Full encryption using managed keys",
          "Full encryption using customer-managed keys (CMK)"],
         [10, 6, 2, 0], 10, "Data & Privacy", 2, "Significant — financial or health-related data"),

        # Parent Q2: special category data → data minimisation
        (14, "You indicated special category data. Is data minimisation enforced?",
         "Special category data requires additional safeguards under GDPR Article 9.",
         None,
         ["No — all data retained indefinitely",
          "Retention policies exist but not enforced",
          "Retention policies enforced with automated purge",
          "Strict minimisation with privacy-by-design review"],
         [10, 6, 3, 0], 10, "Data & Privacy", 2, "Extensive — special category data (biometric, political, etc.)"),

        # Parent Q9: payment processing → PCI scope
        (15, "You indicated payment processing. Is PCI-DSS compliance in scope?",
         "Any system that stores, processes or transmits cardholder data must meet PCI-DSS.",
         None,
         ["Not yet assessed",
          "Assessment in progress",
          "PCI-DSS compliant (SAQ)",
          "PCI-DSS compliant (QSA-audited)",
          "Tokenisation used — cardholder data never stored"],
         [10, 6, 3, 1, 0], 10, "Compliance", 9, "Customer-facing payment processing"),

        # Parent Q6: many third parties → vendor risk
        (16, "You indicated many external integrations. Is a vendor risk assessment completed?",
         "Third-party risk assessments should be performed for all significant external integrations.",
         None,
         ["No vendor assessments performed",
          "Informal checks only",
          "Formal vendor risk assessment for key suppliers",
          "Full third-party risk management programme in place"],
         [10, 6, 3, 0], 10, "Third-party Risk", 6, "Many external / less-vetted third parties"),

        # Parent Q7: no auth → justify
        (17, "You indicated no authentication is required. Please explain why.",
         "No-authentication systems require explicit risk acceptance.",
         None,
         ["No justification — this is an oversight",
          "System only serves static/public content",
          "Network-level controls compensate (IP allowlist, VPN-only)",
          "Risk formally accepted and documented by CISO"],
         [10, 4, 2, 0], 10, "Access Control", 7, "No authentication required"),

        # Parent Q8: GDPR → DPIA
        (18, "You indicated GDPR applies. Has a Data Protection Impact Assessment (DPIA) been completed?",
         "A DPIA is required under GDPR Article 35 for high-risk processing activities.",
         None,
         ["No — not started",
          "Scoping in progress",
          "DPIA in progress",
          "DPIA completed and approved by DPO"],
         [8, 5, 2, 0], 8, "Compliance", 8, "GDPR / data protection legislation"),

        # Parent Q10: critical business impact → DR plan
        (19, "You indicated critical business impact. Is a Disaster Recovery plan in place?",
         "Critical systems require a tested DR plan with defined RTO and RPO.",
         None,
         ["No DR plan exists",
          "DR plan drafted but untested",
          "DR plan tested annually",
          "DR plan tested with automated failover and defined RTO/RPO"],
         [10, 6, 3, 0], 10, "Business Impact", 10, "Critical — regulatory breach or severe financial loss"),

        # Parent Q3: highly confidential → access controls
        (20, "You indicated highly confidential data. Are role-based access controls (RBAC) enforced?",
         "Highly confidential data requires strict need-to-know access controls.",
         None,
         ["No access controls beyond system login",
          "Broad role-based groups (e.g. admin / user)",
          "Granular RBAC with least-privilege principle applied",
          "RBAC enforced with PAM tooling and access reviews"],
         [10, 6, 3, 0], 10, "Data & Privacy", 3, "Highly Confidential"),
    ]

    # First pass: insert root questions (no parent) and capture their IDs
    order_to_id = {}
    for (order, text, desc, hint, opts, wts, max_s, cat, parent_order, trigger) in raw_qs:
        if parent_order is None:
            try:
                c.execute("""INSERT OR IGNORE INTO questions
                    (text,description,hint,options,weights,max_score,category,
                     parent_question_id,trigger_answer,is_active,order_index,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,NULL,NULL,1,?,?,?)""",
                    (text, desc, hint, json.dumps(opts), json.dumps(wts),
                     max_s, cat, order, now, now))
            except: pass

    # Get the IDs of root questions by order_index
    rows = c.execute("SELECT id, order_index FROM questions").fetchall()
    for row in rows:
        order_to_id[row['order_index']] = row['id']

    # Second pass: insert child questions with correct parent_id
    for (order, text, desc, hint, opts, wts, max_s, cat, parent_order, trigger) in raw_qs:
        if parent_order is not None:
            parent_id = order_to_id.get(parent_order)
            if parent_id:
                try:
                    c.execute("""INSERT OR IGNORE INTO questions
                        (text,description,hint,options,weights,max_score,category,
                         parent_question_id,trigger_answer,is_active,order_index,created_at,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?,1,?,?,?)""",
                        (text, desc, hint, json.dumps(opts), json.dumps(wts),
                         max_s, cat, parent_id, trigger, order, now, now))
                except: pass

    for k,v in [("threshold_no_sbd","20"),("threshold_stage1","40"),
                ("threshold_stage2","65"),("org_name","Acme Corporation")]:
        try: c.execute("INSERT OR IGNORE INTO sbd_config VALUES (?,?,?)",(k,v,now))
        except: pass
    c.commit()

# ── DB helpers ───────────────────────────────────────────────────────────────

def _hp(p): return hashlib.sha256(p.encode()).hexdigest()

def _qry(sql, params=(), one=False):
    c = _conn(); rows = c.execute(sql, params).fetchall(); c.close()
    if one: return dict(rows[0]) if rows else None
    return [dict(r) for r in rows]

def _exe(sql, params=()):
    c = _conn(); c.execute(sql, params); c.commit(); c.close()

def _exe_id(sql, params=()):
    c = _conn(); c.execute(sql, params)
    lid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.commit(); c.close(); return lid

def get_user(username): return _qry("SELECT * FROM users WHERE username=? AND is_active=1",(username,),one=True)
def get_user_id(uid): return _qry("SELECT * FROM users WHERE id=?",(uid,),one=True)
def all_users(role=None):
    if role: return _qry("SELECT * FROM users WHERE role=? AND is_active=1 ORDER BY name",(role,))
    return _qry("SELECT * FROM users WHERE is_active=1 ORDER BY name")

def root_questions():
    """Return only root (non-child) active questions ordered."""
    return _qry("SELECT * FROM questions WHERE is_active=1 AND parent_question_id IS NULL ORDER BY order_index, id")

def child_questions_for(parent_id):
    """Return active child questions for a given parent."""
    return _qry("SELECT * FROM questions WHERE is_active=1 AND parent_question_id=? ORDER BY order_index, id",(parent_id,))

def all_questions_flat():
    return _qry("SELECT * FROM questions ORDER BY order_index, id")

def get_cfg(): return {r['key']:r['value'] for r in _qry("SELECT * FROM sbd_config")}
def set_cfg(k,v): _exe("INSERT OR REPLACE INTO sbd_config VALUES (?,?,?)",(k,v,datetime.now().isoformat()))

def _new_ref():
    n = _qry("SELECT COUNT(*) as c FROM requests",one=True)['c']
    return f"SBD-{datetime.now().year}-{str(n+1).zfill(4)}"

def create_request(name, desc, owner, ptype, golive, uid):
    now = datetime.now().isoformat(); ref = _new_ref()
    rid = _exe_id("""INSERT INTO requests
        (ref_number,project_name,project_description,business_owner,project_type,
         go_live_date,created_by,status,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,'draft',?,?)""",(ref,name,desc,owner,ptype,golive,uid,now,now))
    _exe("INSERT INTO status_history (request_id,from_status,to_status,changed_by,notes,created_at) VALUES (?,?,?,?,?,?)",
         (rid,None,'draft',uid,'Request created',now))
    return rid, ref

def save_answers(rid, answers_dict):
    """answers_dict: {qid_str: {'answer': str, 'score': float}}"""
    now = datetime.now().isoformat()
    _exe("DELETE FROM request_answers WHERE request_id=?",(rid,))
    all_qs = {q['id']:q for q in all_questions_flat()}
    total = 0; max_total = 0
    for qid_s, ad in answers_dict.items():
        qid = int(qid_s)
        _exe("INSERT INTO request_answers (request_id,question_id,answer,score) VALUES (?,?,?,?)",
             (rid, qid, ad['answer'], ad['score']))
        total += ad['score']
        if qid in all_qs: max_total += all_qs[qid]['max_score']
    pct = (total/max_total*100) if max_total>0 else 0
    _exe("UPDATE requests SET total_score=?,max_possible_score=?,score_pct=?,updated_at=? WHERE id=?",
         (total,max_total,pct,now,rid))
    return total, max_total, pct

def calc_outcome(pct, cfg):
    t1=float(cfg.get('threshold_no_sbd',20)); t2=float(cfg.get('threshold_stage1',40)); t3=float(cfg.get('threshold_stage2',65))
    if pct<=t1: return "no_sbd"
    elif pct<=t2: return "sbd_stage1"
    elif pct<=t3: return "sbd_stage2"
    else: return "full_sbd"

def submit_request(rid, outcome, uid):
    """Move draft → pending_review and lock answers."""
    now = datetime.now().isoformat()
    old = _qry("SELECT status FROM requests WHERE id=?",(rid,),one=True)
    _exe("UPDATE requests SET status='pending_review',sbd_outcome=?,is_locked=1,submitted_at=?,updated_at=? WHERE id=?",
         (outcome,now,now,rid))
    _exe("INSERT INTO status_history (request_id,from_status,to_status,changed_by,notes,created_at) VALUES (?,?,?,?,?,?)",
         (rid,old['status'],'pending_review',uid,f'Submitted for review. Preliminary outcome: {outcome}',now))

def return_to_draft(rid, uid, reason):
    """SbD manager sends request back to draft for editing."""
    now = datetime.now().isoformat()
    _exe("UPDATE requests SET status='draft',is_locked=0,sbd_outcome=NULL,updated_at=? WHERE id=?",(now,rid))
    _exe("INSERT INTO status_history (request_id,from_status,to_status,changed_by,notes,created_at) VALUES (?,?,?,?,?,?)",
         (rid,'pending_review','draft',uid,f'Returned for revision: {reason}',now))

def update_status(rid, new_s, uid, notes=None, extras=None):
    now = datetime.now().isoformat()
    old = _qry("SELECT status FROM requests WHERE id=?",(rid,),one=True)
    ts = {'architect_assigned':'architect_assigned_at','architect_completed':'architect_completed_at',
          'engineer_assigned':'engineer_assigned_at','engineer_completed':'engineer_completed_at',
          'assurance_assigned':'assurance_assigned_at','assurance_completed':'assurance_completed_at',
          'pending_signoff':'pending_signoff_at','signoff_received':'signoff_received_at'}
    c = _conn()
    c.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?",(new_s,now,rid))
    if new_s in ts: c.execute(f"UPDATE requests SET {ts[new_s]}=? WHERE id=?",(now,rid))
    if new_s=='awaiting_assignment': c.execute("UPDATE requests SET is_locked=1 WHERE id=?",(rid,))
    if new_s=='signoff_received': c.execute("UPDATE requests SET is_locked=1,signoff_by=? WHERE id=?",(uid,rid))
    if extras:
        for k,v in extras.items(): c.execute(f"UPDATE requests SET {k}=? WHERE id=?",(v,rid))
    c.execute("INSERT INTO status_history (request_id,from_status,to_status,changed_by,notes,created_at) VALUES (?,?,?,?,?,?)",
              (rid,old['status'] if old else None,new_s,uid,notes,now))
    c.commit(); c.close()

def get_req(rid): return _qry("SELECT * FROM requests WHERE id=?",(rid,),one=True)
def req_answers(rid):
    return _qry("""SELECT ra.*,q.text as qtxt,q.category,q.options,q.weights,q.description as qdesc,
                          q.parent_question_id
                   FROM request_answers ra JOIN questions q ON ra.question_id=q.id
                   WHERE ra.request_id=? ORDER BY q.order_index,q.id""",(rid,))
def user_reqs(uid):
    return _qry("""SELECT DISTINCT r.* FROM requests r
        LEFT JOIN request_permissions rp ON r.id=rp.request_id AND rp.user_id=?
        WHERE r.created_by=? OR rp.user_id=? ORDER BY r.created_at DESC""",(uid,uid,uid))
def assigned_reqs(uid, field):
    return _qry(f"SELECT * FROM requests WHERE {field}=? ORDER BY created_at DESC",(uid,))
def all_reqs(status=None):
    if status: return _qry("SELECT * FROM requests WHERE status=? ORDER BY created_at DESC",(status,))
    return _qry("SELECT * FROM requests ORDER BY created_at DESC")
def reqs_by_status(sl):
    ph=','.join('?'*len(sl))
    return _qry(f"SELECT * FROM requests WHERE status IN ({ph}) ORDER BY created_at DESC",sl)
def status_hist(rid):
    return _qry("""SELECT sh.*,u.name as by_name FROM status_history sh
        JOIN users u ON sh.changed_by=u.id WHERE sh.request_id=? ORDER BY sh.created_at""",(rid,))
def add_perm(rid,uid,perm,by): _exe("INSERT OR REPLACE INTO request_permissions VALUES (?,?,?,?,?)",(rid,uid,perm,by,datetime.now().isoformat()))
def get_perms(rid): return _qry("SELECT rp.*,u.name,u.email,u.username,u.role FROM request_permissions rp JOIN users u ON rp.user_id=u.id WHERE rp.request_id=?",(rid,))
def del_perm(rid,uid): _exe("DELETE FROM request_permissions WHERE request_id=? AND user_id=?",(rid,uid))
def can_access(rid,uid,write=False):
    r=_qry("SELECT created_by FROM requests WHERE id=?",(rid,),one=True)
    if r and r['created_by']==uid: return True
    p=_qry("SELECT permission FROM request_permissions WHERE request_id=? AND user_id=?",(rid,uid),one=True)
    if p: return p['permission']=='write' if write else True
    return False
def is_assigned_to(rid,uid):
    r=get_req(rid)
    return bool(r and uid in [r.get('architect_id'),r.get('engineer_id'),r.get('assurance_id')])
def add_comment(rid,uid,text,internal=False):
    _exe("INSERT INTO comments (request_id,user_id,text,is_internal,created_at) VALUES (?,?,?,?,?)",
         (rid,uid,text,int(internal),datetime.now().isoformat()))
def get_comments(rid, show_internal=False):
    if show_internal:
        return _qry("SELECT c.*,u.name,u.role FROM comments c JOIN users u ON c.user_id=u.id WHERE c.request_id=? ORDER BY c.created_at DESC",(rid,))
    return _qry("SELECT c.*,u.name,u.role FROM comments c JOIN users u ON c.user_id=u.id WHERE c.request_id=? AND c.is_internal=0 ORDER BY c.created_at DESC",(rid,))
def create_user(un,pw,name,email,role,dept=""):
    try: _exe("INSERT INTO users (username,password_hash,name,email,role,department,created_at) VALUES (?,?,?,?,?,?,?)",(un,_hp(pw),name,email,role,dept,datetime.now().isoformat())); return True,"OK"
    except sqlite3.IntegrityError: return False,"Username already exists"
def get_stats():
    s={}
    s['total']=_qry("SELECT COUNT(*) as c FROM requests",one=True)['c']
    for k,v in [('draft',"status='draft'"),('pending_review',"status='pending_review'"),
                ('awaiting',"status='awaiting_assignment'"),
                ('in_progress',"status IN ('architect_assigned','architect_completed','engineer_assigned','engineer_completed','assurance_assigned','assurance_completed')"),
                ('signoff',"status='pending_signoff'"),('complete',"status='signoff_received'"),
                ('no_sbd',"status='no_sbd_needed'")]:
        s[k]=_qry(f"SELECT COUNT(*) as c FROM requests WHERE {v}",one=True)['c']
    for o in ['no_sbd','sbd_stage1','sbd_stage2','full_sbd']:
        s[f'o_{o}']=_qry("SELECT COUNT(*) as c FROM requests WHERE sbd_outcome=?",(o,),one=True)['c']
    return s

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

STATUS_CFG = {
    'draft':               ('Draft',                '#94A3B8','#F8FAFC','✏️'),
    'pending_review':      ('Pending Review',       '#F59E0B','#FFFBEB','⏳'),
    'no_sbd_needed':       ('No SBD Required',      '#6B7280','#F3F4F6','—'),
    'awaiting_assignment': ('Awaiting Assignment',  '#3B82F6','#EFF6FF','👤'),
    'architect_assigned':  ('Architect Assigned',   '#8B5CF6','#F5F3FF','🏗'),
    'architect_completed': ('Architecture Done',    '#10B981','#ECFDF5','✓'),
    'engineer_assigned':   ('Engineer Assigned',    '#F97316','#FFF7ED','⚙'),
    'engineer_completed':  ('Engineering Done',     '#10B981','#ECFDF5','✓'),
    'assurance_assigned':  ('Assurance Assigned',   '#EC4899','#FDF2F8','🔍'),
    'assurance_completed': ('Assurance Done',       '#10B981','#ECFDF5','✓'),
    'pending_signoff':     ('Pending Sign-off',     '#6366F1','#EEF2FF','✍'),
    'signoff_received':    ('Signed Off',           '#059669','#ECFDF5','🎉'),
}

OUTCOME_CFG = {
    'no_sbd':    ('No SBD Required','#6B7280','#F9FAFB','#E5E7EB','✅',
                  'Low risk — no formal SbD engagement required. The SbD team will confirm.'),
    'sbd_stage1':('SBD Stage 1',    '#D97706','#FFFBEB','#FDE68A','⚠️',
                  'Light-touch engagement: architecture review and written sign-off required.'),
    'sbd_stage2':('SBD Stage 2',    '#DC2626','#FEF2F2','#FECACA','🔶',
                  'Standard engagement: architecture, engineering review, and assurance required.'),
    'full_sbd':  ('Full SBD',       '#7C3AED','#F5F3FF','#DDD6FE','🔴',
                  'Full engagement required: all phases including penetration testing.'),
}

PIPELINE = [
    ('pending_review','Submitted','📋'),
    ('awaiting_assignment','Assessed','📊'),
    ('architect_assigned','Architect','🏗'),
    ('architect_completed','Arch ✓','✅'),
    ('engineer_assigned','Engineer','⚙'),
    ('engineer_completed','Eng ✓','✅'),
    ('assurance_assigned','Assurance','🔍'),
    ('assurance_completed','Assur ✓','✅'),
    ('pending_signoff','Sign-off','✍'),
    ('signoff_received','Complete','🎉'),
]

ROLES = ['project_member','security_architect','security_engineer','assurance','sbd_manager','admin']
ROLE_LABELS = {
    'project_member':'Project Member','security_architect':'Security Architect',
    'security_engineer':'Security Engineer','assurance':'Assurance Analyst',
    'sbd_manager':'SbD Programme Manager','admin':'System Administrator'
}

def fdate(s):
    if not s: return "—"
    try: return datetime.fromisoformat(s).strftime("%d %b %Y %H:%M")
    except: return s

def fdates(s):
    if not s: return "—"
    try: return datetime.fromisoformat(s).strftime("%d %b %Y")
    except: return s

# ══════════════════════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════════════════════

def inject_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap');
:root{--navy:#0A0F1E;--navy2:#111827;--navy3:#1F2937;--accent:#3B82F6;--success:#10B981;
  --warning:#F59E0B;--danger:#EF4444;--purple:#8B5CF6;--surface:#fff;--surface2:#F8FAFC;
  --surface3:#F1F5F9;--border:#E2E8F0;--border2:#CBD5E1;--text:#0F172A;--text2:#334155;
  --text3:#64748B;--text4:#94A3B8;--mono:'JetBrains Mono',monospace;--sans:'Inter',sans-serif;
  --r:10px;--r2:6px;--sh:0 1px 3px rgba(0,0,0,.08),0 1px 2px rgba(0,0,0,.06);}
*,*::before,*::after{box-sizing:border-box;}
html,body,[class*="css"]{font-family:var(--sans)!important;}
#MainMenu,footer,header{visibility:hidden;}
[data-testid="stSidebar"]{background:var(--navy)!important;border-right:1px solid rgba(255,255,255,.06)!important;}
[data-testid="stSidebar"] *{color:#CBD5E1!important;}
[data-testid="stSidebarContent"]{padding:0!important;}
.sb-brand{padding:1.5rem 1.25rem 1.25rem;border-bottom:1px solid rgba(255,255,255,.06);display:flex;align-items:center;gap:.75rem;}
.sb-icon{width:38px;height:38px;background:linear-gradient(135deg,#3B82F6,#8B5CF6);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0;}
.sb-title{font-weight:700;font-size:.95rem;color:#F1F5F9!important;letter-spacing:-.01em;}
.sb-sub{font-size:.68rem;color:#64748B!important;text-transform:uppercase;letter-spacing:.08em;}
.sb-user{margin:.75rem;padding:.875rem 1rem;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06);border-radius:var(--r);display:flex;align-items:center;gap:.75rem;}
.sb-av{width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#3B82F6,#8B5CF6);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.9rem;color:white!important;flex-shrink:0;}
.sb-un{font-weight:600;font-size:.85rem;color:#F1F5F9!important;}
.sb-ur{font-size:.7rem;color:#64748B!important;text-transform:uppercase;letter-spacing:.06em;}
.sb-sec{padding:.375rem 1.25rem .25rem;font-size:.65rem;font-weight:700;color:#475569!important;text-transform:uppercase;letter-spacing:.1em;margin-top:.5rem;}
[data-testid="stSidebar"] .stButton button{background:transparent!important;border:none!important;border-radius:var(--r2)!important;color:#94A3B8!important;padding:.45rem 1rem!important;font-size:.83rem!important;font-weight:500!important;text-align:left!important;transition:background .15s,color .15s!important;margin:1px .5rem!important;width:calc(100% - 1rem)!important;}
[data-testid="stSidebar"] .stButton button:hover{background:rgba(255,255,255,.06)!important;color:#F1F5F9!important;}
[data-testid="stSidebar"] .stButton button[kind="primary"]{background:rgba(59,130,246,.2)!important;color:#93C5FD!important;border-left:2px solid #3B82F6!important;}
.main .block-container{padding:1.75rem 2.25rem!important;max-width:1360px!important;}
.pg-hdr{margin-bottom:1.75rem;padding-bottom:1.25rem;border-bottom:1px solid var(--border);}
.pg-title{font-size:1.5rem;font-weight:800;color:var(--text);letter-spacing:-.025em;margin:0;}
.pg-sub{color:var(--text3);font-size:.85rem;margin-top:.2rem;}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:1.5rem;box-shadow:var(--sh);}
.card-sm{padding:1rem 1.25rem;}
.badge{display:inline-flex;align-items:center;gap:.3rem;padding:.2rem .65rem;border-radius:999px;font-size:.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap;}
.bdot{width:6px;height:6px;border-radius:50%;flex-shrink:0;}
.ref{font-family:var(--mono);font-size:.78rem;font-weight:600;color:var(--accent);background:#EFF6FF;padding:.18rem .55rem;border-radius:var(--r2);}
.stat-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:1.25rem;box-shadow:var(--sh);}
.stat-val{font-family:var(--mono);font-size:2rem;font-weight:700;line-height:1;}
.stat-lbl{font-size:.72rem;color:var(--text3);text-transform:uppercase;letter-spacing:.06em;margin-top:.25rem;}
.pipeline{display:flex;align-items:center;margin:.75rem 0;overflow-x:auto;padding-bottom:.25rem;}
.pipe-step{display:flex;flex-direction:column;align-items:center;flex:1;min-width:64px;}
.pipe-node{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.72rem;z-index:1;}
.pn-todo{background:var(--surface3);border:2px solid var(--border2);color:var(--text4);}
.pn-done{background:var(--success);border:2px solid var(--success);color:white;}
.pn-now{background:var(--accent);border:2px solid var(--accent);color:white;box-shadow:0 0 0 4px rgba(59,130,246,.2);}
.pipe-lbl{font-size:.58rem;text-align:center;margin-top:.3rem;color:var(--text3);text-transform:uppercase;letter-spacing:.04em;max-width:60px;line-height:1.3;}
.pl{flex:1;height:2px;margin-bottom:.85rem;}
.pl-todo{background:var(--border);}
.pl-done{background:var(--success);}
.tl{position:relative;padding-left:1.75rem;}
.tl::before{content:'';position:absolute;left:.45rem;top:4px;bottom:4px;width:2px;background:var(--border);border-radius:2px;}
.tl-item{position:relative;margin-bottom:1.25rem;}
.tl-dot{position:absolute;left:-1.5rem;top:.2rem;width:12px;height:12px;border-radius:50%;border:2px solid white;}
.td-done{background:var(--success);box-shadow:0 0 0 2px var(--success);}
.td-now{background:var(--accent);box-shadow:0 0 0 3px rgba(59,130,246,.3);}
.td-todo{background:var(--border2);box-shadow:0 0 0 2px var(--border2);}
.tl-t{font-size:.85rem;font-weight:600;color:var(--text);}
.tl-m{font-size:.75rem;color:var(--text3);margin-top:.1rem;}
.tl-n{font-size:.78rem;color:var(--text2);font-style:italic;margin-top:.2rem;}
/* Question cards */
.qcard{background:var(--surface2);border:1px solid var(--border);border-left:3px solid var(--accent);border-radius:var(--r);padding:1rem 1.25rem;margin-bottom:.5rem;}
.qcard.nested{border-left-color:var(--purple);background:#FEFBFF;margin-left:2rem;}
.qnum{font-family:var(--mono);font-size:.7rem;color:var(--accent);font-weight:700;margin-bottom:.2rem;}
.qnum.nested{color:var(--purple);}
.qtxt{font-weight:600;font-size:.92rem;color:var(--text);margin-bottom:.2rem;}
.qdesc{font-size:.8rem;color:var(--text3);}
.qhint{font-size:.75rem;color:var(--text4);font-style:italic;margin-top:.2rem;}
.nested-trigger{display:inline-flex;align-items:center;gap:.4rem;background:#F5F3FF;border:1px solid #DDD6FE;color:#6D28D9;font-size:.72rem;font-weight:600;padding:.2rem .6rem;border-radius:4px;margin-bottom:.5rem;}
/* Outcome banner */
.obanner{border-radius:var(--r);padding:1.25rem 1.5rem;display:flex;align-items:flex-start;gap:1rem;border:1px solid;}
.oicon{font-size:2rem;flex-shrink:0;margin-top:.1rem;}
.otitle{font-weight:700;font-size:1.05rem;}
.odesc{font-size:.82rem;margin-top:.2rem;}
.lock-banner{background:var(--navy2);color:#F1F5F9;border-radius:var(--r);padding:.75rem 1.25rem;display:flex;align-items:center;gap:.75rem;font-weight:600;font-size:.88rem;margin-bottom:1rem;}
.alert{padding:.75rem 1rem;border-radius:var(--r2);margin:.5rem 0;font-size:.84rem;}
.ai{background:#EFF6FF;border:1px solid #BFDBFE;color:#1E40AF;}
.aw{background:#FFFBEB;border:1px solid #FDE68A;color:#92400E;}
.as{background:#ECFDF5;border:1px solid #A7F3D0;color:#065F46;}
.ad{background:#FEF2F2;border:1px solid #FECACA;color:#991B1B;}
.stTabs [data-baseweb="tab-list"]{border-bottom:2px solid var(--border)!important;gap:0!important;}
.stTabs [data-baseweb="tab"]{font-size:.83rem!important;font-weight:500!important;padding:.6rem 1.25rem!important;border-bottom:2px solid transparent!important;margin-bottom:-2px!important;}
.stTabs [aria-selected="true"]{border-bottom-color:var(--accent)!important;color:var(--accent)!important;font-weight:600!important;}
::-webkit-scrollbar{width:5px;height:5px;}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px;}
</style>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def sbadge(status):
    if status not in STATUS_CFG: return f'<span class="badge" style="background:#F3F4F6;color:#6B7280;">{status}</span>'
    label,color,bg,_ = STATUS_CFG[status]
    return f'<span class="badge" style="background:{bg};color:{color};"><span class="bdot" style="background:{color};"></span>{label}</span>'

def obadge(o):
    if not o or o not in OUTCOME_CFG: return ''
    label,color,bg,_,icon,_ = OUTCOME_CFG[o]
    return f'<span class="badge" style="background:{bg};color:{color};">{icon} {label}</span>'

def pipeline_html(current):
    try: ci = next(i for i,(k,_,__) in enumerate(PIPELINE) if k==current)
    except: ci = -1
    html = '<div class="pipeline">'
    for i,(key,label,icon) in enumerate(PIPELINE):
        nc = 'pn-done' if i<ci else ('pn-now' if i==ci else 'pn-todo')
        ni = '✓' if i<ci else (icon if i==ci else '')
        if i>0: html += f'<div class="pl {"pl-done" if i<=ci else "pl-todo"}"></div>'
        html += f'<div class="pipe-step"><div class="pipe-node {nc}">{ni}</div><div class="pipe-lbl">{label}</div></div>'
    return html+'</div>'

def phase_tl(req):
    phases = [('submitted_at','Submitted','📋'),('architect_assigned_at','Architect Assigned','🏗'),
              ('architect_completed_at','Architecture Done','✅'),('engineer_assigned_at','Engineer Assigned','⚙'),
              ('engineer_completed_at','Engineering Done','✅'),('assurance_assigned_at','Assurance Assigned','🔍'),
              ('assurance_completed_at','Assurance Done','✅'),('pending_signoff_at','Pending Sign-off','✍'),
              ('signoff_received_at','Signed Off','🎉')]
    html='<div class="tl">'; done_phase=True
    for field,label,icon in phases:
        dt=req.get(field)
        if dt: cls='td-done'
        elif done_phase: cls='td-now'; done_phase=False
        else: cls='td-todo'
        html+=f'<div class="tl-item"><div class="tl-dot {cls}"></div><div class="tl-t">{icon} {label}</div><div class="tl-m">{fdate(dt) if dt else "<span style=\'color:#CBD5E1\'>Pending</span>"}</div></div>'
    return html+'</div>'

def stepper(steps, cur):
    html='<div style="display:flex;align-items:center;margin-bottom:1.25rem;">'
    for i,label in enumerate(steps,1):
        if i<cur: ds="background:#10B981;color:white;border:2px solid #10B981;"; lc="#10B981"; icon="✓"
        elif i==cur: ds="background:#3B82F6;color:white;border:2px solid #3B82F6;box-shadow:0 0 0 3px rgba(59,130,246,.2);"; lc="#3B82F6"; icon=str(i)
        else: ds="background:#F8FAFC;color:#94A3B8;border:2px solid #E2E8F0;"; lc="#94A3B8"; icon=str(i)
        html+=f'<div style="display:flex;flex-direction:column;align-items:center;flex:1;"><div style="width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.8rem;{ds}">{icon}</div><div style="font-size:.7rem;margin-top:.3rem;color:{lc};font-weight:{"600" if i==cur else "400"};text-align:center;">{label}</div></div>'
        if i<len(steps): html+=f'<div style="flex:2;height:2px;background:{"#10B981" if i<cur else "#E2E8F0"};margin-bottom:1.1rem;"></div>'
    st.markdown(html+'</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════════

def login_page():
    cfg = get_cfg()
    _,c,_ = st.columns([1,1.1,1])
    with c:
        st.markdown(f"""<div style="text-align:center;padding:3rem 0 2rem;">
          <div style="width:64px;height:64px;background:linear-gradient(135deg,#3B82F6,#8B5CF6);
               border-radius:18px;display:inline-flex;align-items:center;justify-content:center;
               font-size:2rem;margin-bottom:1.25rem;box-shadow:0 8px 24px rgba(59,130,246,.3);">🔐</div>
          <div style="font-size:1.6rem;font-weight:800;color:#0F172A;letter-spacing:-.03em;">SbD Portal</div>
          <div style="font-size:.82rem;color:#64748B;margin-top:.3rem;">{cfg.get('org_name','')} · Secure by Design Programme</div>
        </div>""", unsafe_allow_html=True)
        st.markdown('<div style="font-weight:700;font-size:.92rem;margin-bottom:.75rem;">Sign in</div>', unsafe_allow_html=True)
        un = st.text_input("Username", placeholder="Username", label_visibility="collapsed")
        pw = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed")
        st.markdown("<div style='margin-top:.25rem;'></div>", unsafe_allow_html=True)
        if st.button("Sign In →", use_container_width=True, type="primary"):
            u = get_user(un)
            if u and u['password_hash']==_hp(pw):
                st.session_state.authenticated=True; st.session_state.user=u; st.rerun()
            else: st.error("Invalid username or password.")
        st.markdown("""<div style="text-align:center;margin-top:1rem;color:#94A3B8;font-size:.76rem;line-height:1.9;">
          <strong style="color:#64748B;">Demo accounts</strong><br>
          admin / admin123 &nbsp;·&nbsp; sbd_manager / manager123<br>
          architect1 / arch123 &nbsp;·&nbsp; engineer1 / eng123<br>
          assurance1 / assur123 &nbsp;·&nbsp; user1 / user123
        </div>""", unsafe_allow_html=True)

def logout():
    for k in list(st.session_state.keys()): del st.session_state[k]

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

def render_sidebar(user):
    role = user['role']
    with st.sidebar:
        st.markdown(f'<div class="sb-brand"><div class="sb-icon">🔐</div><div><div class="sb-title">SbD Portal</div><div class="sb-sub">Secure by Design</div></div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sb-user"><div class="sb-av">{user["name"][0]}</div><div><div class="sb-un">{user["name"]}</div><div class="sb-ur">{ROLE_LABELS.get(role,role)}</div></div></div>', unsafe_allow_html=True)
        st.markdown('<div class="sb-sec">Navigation</div>', unsafe_allow_html=True)
        nav = [("🏠","Dashboard","dashboard"),("📋","My Requests","my_requests"),("➕","New Request","new_request")]
        if role in ['security_architect','security_engineer','assurance']:
            nav.append(("📌","Assigned to Me","assigned"))
        if role in ['sbd_manager','admin']:
            st.markdown('<div class="sb-sec">Management</div>', unsafe_allow_html=True)
            nav += [("📥","Review Queue","pending_review"),("👥","Assign Resources","assign_resources"),
                    ("✅","Sign-Off Queue","signoff_queue"),("📊","All Requests","all_requests")]
        if role=='admin':
            st.markdown('<div class="sb-sec">Administration</div>', unsafe_allow_html=True)
            nav += [("⚙️","Question Builder","admin_panel"),("👤","User Management","user_management")]
        pg = st.session_state.get('page','dashboard')
        for icon,label,pk in nav:
            if st.button(f"{icon}  {label}", key=f"nav_{pk}", use_container_width=True,
                         type="primary" if pg==pk else "secondary"):
                st.session_state.page=pk; st.rerun()
        st.markdown("---")
        if st.button("🚪  Sign Out", use_container_width=True): logout(); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def page_dashboard(user):
    role = user['role']; stats = get_stats(); cfg = get_cfg()
    st.markdown(f'<div class="pg-hdr"><div class="pg-title">Welcome back, {user["name"].split()[0]}</div><div class="pg-sub">{cfg.get("org_name","")} · Secure by Design Programme</div></div>', unsafe_allow_html=True)
    cols = st.columns(6)
    for col,(icon,lbl,val,color) in zip(cols,[
        ("📋","Total",stats['total'],"#3B82F6"),("⏳","Pending Review",stats['pending_review'],"#F59E0B"),
        ("👤","Awaiting Assign",stats['awaiting'],"#8B5CF6"),("⚙","In Progress",stats['in_progress'],"#F97316"),
        ("✍","Pending Sign-off",stats['signoff'],"#6366F1"),("🎉","Completed",stats['complete'],"#10B981")]):
        with col:
            st.markdown(f'<div class="stat-card" style="border-top:3px solid {color};"><div style="font-size:1.4rem;">{icon}</div><div class="stat-val" style="color:{color};">{val}</div><div class="stat-lbl">{lbl}</div></div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    cl,cr = st.columns([3,2])
    with cl:
        st.markdown('<div style="font-weight:700;font-size:1rem;margin-bottom:.875rem;">Recent Activity</div>', unsafe_allow_html=True)
        if role in ['admin','sbd_manager']: reqs = all_reqs()[:8]
        elif role in ['security_architect','security_engineer','assurance']:
            fm = {'security_architect':'architect_id','security_engineer':'engineer_id','assurance':'assurance_id'}
            reqs = assigned_reqs(user['id'],fm[role])[:8]
        else: reqs = user_reqs(user['id'])[:8]
        if not reqs:
            st.markdown('<div class="card" style="text-align:center;padding:2.5rem;color:#94A3B8;"><div style="font-size:2.5rem;">📭</div><div style="font-weight:600;margin-top:.5rem;">No requests yet</div></div>', unsafe_allow_html=True)
        for req in reqs:
            _,color,_,_ = STATUS_CFG.get(req['status'],('','#6B7280','','?'))
            st.markdown(f'<div class="card card-sm" style="margin-bottom:.625rem;border-left:3px solid {color};"><div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;margin-bottom:.25rem;"><span class="ref">{req["ref_number"]}</span>{sbadge(req["status"])}{obadge(req.get("sbd_outcome"))}</div><div style="font-weight:600;font-size:.9rem;">{req["project_name"]}</div><div style="font-size:.75rem;color:#94A3B8;">{fdates(req["created_at"])}</div></div>', unsafe_allow_html=True)
            if st.button(f"Open {req['ref_number']}", key=f"dsh_{req['id']}"):
                st.session_state.selected_req=req['id']; st.session_state.page="request_detail"; st.rerun()
    with cr:
        st.markdown('<div style="font-weight:700;font-size:1rem;margin-bottom:.875rem;">SbD Outcomes</div>', unsafe_allow_html=True)
        od=[('no_sbd','No SBD Required',stats['o_no_sbd']),('sbd_stage1','SBD Stage 1',stats['o_sbd_stage1']),
            ('sbd_stage2','SBD Stage 2',stats['o_sbd_stage2']),('full_sbd','Full SBD',stats['o_full_sbd'])]
        tot=sum(v for _,_,v in od) or 1
        st.markdown('<div class="card">', unsafe_allow_html=True)
        for o,lbl,cnt in od:
            _,color,_,_,icon,_ = OUTCOME_CFG[o]; pct=cnt/tot*100
            st.markdown(f'<div style="margin-bottom:1rem;"><div style="display:flex;justify-content:space-between;margin-bottom:.3rem;"><span style="font-size:.82rem;font-weight:500;">{icon} {lbl}</span><span style="font-family:var(--mono);font-size:.82rem;font-weight:700;color:{color};">{cnt}</span></div><div style="background:#F1F5F9;border-radius:999px;height:5px;"><div style="background:{color};height:5px;border-radius:999px;width:{pct:.1f}%;"></div></div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕  New SbD Request", use_container_width=True, type="primary"):
            st.session_state.page="new_request"; st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: NEW REQUEST  — dynamic question nesting WITHOUT a wrapping st.form
# ══════════════════════════════════════════════════════════════════════════════

def page_new_request(user):
    st.markdown('<div class="pg-hdr"><div class="pg-title">New SbD Request</div><div class="pg-sub">Complete all sections to submit your security assessment</div></div>', unsafe_allow_html=True)
    for k,v in [('nrq_step',1),('nrq_rid',None),('nrq_ref',None),('nrq_ans',{}),
                ('nrq_name',''),('nrq_desc',''),('nrq_owner',''),('nrq_type','New Application'),('nrq_golive','')]:
        if k not in st.session_state: st.session_state[k]=v
    step=st.session_state.nrq_step
    stepper(["Project Info","Assessment","Review & Submit","Outcome"], step)
    st.markdown("<br>", unsafe_allow_html=True)
    if step==1: _nrq_s1(user)
    elif step==2: _nrq_s2(user)
    elif step==3: _nrq_s3(user)
    elif step==4: _nrq_s4(user)

def _nrq_s1(user):
    c1,c2 = st.columns([2,1])
    with c1:
        with st.form("nrq_s1"):
            name = st.text_input("Project Name *", value=st.session_state.nrq_name)
            desc = st.text_area("Project Description", value=st.session_state.nrq_desc, height=100,
                                 placeholder="Describe the purpose, technology stack and key data flows...")
            ca,cb = st.columns(2)
            with ca: owner=st.text_input("Business Owner", value=st.session_state.nrq_owner)
            with cb:
                ptypes=["New Application","Platform Change","Third-party Integration","Data Analytics","Infrastructure","Process Automation"]
                ptype=st.selectbox("Project Type", ptypes, index=ptypes.index(st.session_state.nrq_type) if st.session_state.nrq_type in ptypes else 0)
            golive=st.text_input("Target Go-Live Date", value=st.session_state.nrq_golive, placeholder="e.g. Q3 2026")
            if st.form_submit_button("Continue to Assessment →", type="primary"):
                if not name.strip(): st.error("Project name is required.")
                else:
                    st.session_state.nrq_name=name.strip(); st.session_state.nrq_desc=desc.strip()
                    st.session_state.nrq_owner=owner.strip(); st.session_state.nrq_type=ptype
                    st.session_state.nrq_golive=golive.strip(); st.session_state.nrq_step=2; st.rerun()
    with c2:
        st.markdown('<div class="card ai" style="border:1px solid #BFDBFE;"><div style="font-weight:700;font-size:.82rem;color:#1E40AF;margin-bottom:.75rem;">ℹ️ About this process</div><div style="font-size:.78rem;color:#1E3A5F;line-height:1.6;">Your answers determine the level of SbD engagement required.<br><br>Some questions will only appear based on your previous answers.<br><br>Takes approximately <strong>5–10 minutes</strong>.</div></div>', unsafe_allow_html=True)

def _nrq_s2(user):
    """
    Dynamic question rendering WITHOUT st.form.
    Each answer is stored in session state immediately via on_change.
    Child questions appear only when the parent answer matches the trigger.
    """
    roots = root_questions()
    ans = st.session_state.nrq_ans  # {str(qid): {'answer': str, 'score': float}}

    st.markdown('<div style="font-weight:700;font-size:.95rem;margin-bottom:1rem;">🔍 Security Assessment</div>', unsafe_allow_html=True)
    st.markdown('<div class="alert ai">Answer each question. Additional follow-up questions will appear automatically based on your responses.</div>', unsafe_allow_html=True)

    qnum = 0
    all_qs_map = {q['id']:q for q in all_questions_flat()}

    for q in roots:
        qnum += 1
        qid_s = str(q['id'])
        opts = json.loads(q['options'])
        cur_ans = ans.get(qid_s, {}).get('answer', opts[0])
        if cur_ans not in opts: cur_ans = opts[0]

        desc_h = f'<div class="qdesc">{q["description"]}</div>' if q.get('description') else ''
        hint_h = f'<div class="qhint">💡 {q["hint"]}</div>' if q.get('hint') else ''
        st.markdown(f'<div class="qcard"><div class="qnum">Q{qnum}</div><div class="qtxt">{q["text"]}</div>{desc_h}{hint_h}</div>', unsafe_allow_html=True)

        selected = st.radio(
            f"q{q['id']}",
            options=opts,
            index=opts.index(cur_ans),
            key=f"radio_{q['id']}",
            label_visibility="collapsed"
        )
        # Persist answer immediately
        wts = json.loads(q['weights'])
        score = wts[opts.index(selected)] if selected in opts else 0
        st.session_state.nrq_ans[qid_s] = {'answer': selected, 'score': score}

        # ── Render child questions if this answer triggers them ──────────────
        children = child_questions_for(q['id'])
        for child in children:
            if child.get('trigger_answer') and selected == child['trigger_answer']:
                qnum += 1
                cid_s = str(child['id'])
                c_opts = json.loads(child['options'])
                c_cur = ans.get(cid_s, {}).get('answer', c_opts[0])
                if c_cur not in c_opts: c_cur = c_opts[0]

                c_desc_h = f'<div class="qdesc">{child["description"]}</div>' if child.get('description') else ''
                st.markdown(f'<div class="nested-trigger">↳ Follow-up based on your answer above</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="qcard nested"><div class="qnum nested">Q{qnum} — Follow-up</div><div class="qtxt">{child["text"]}</div>{c_desc_h}</div>', unsafe_allow_html=True)

                c_selected = st.radio(
                    f"q{child['id']}",
                    options=c_opts,
                    index=c_opts.index(c_cur),
                    key=f"radio_{child['id']}",
                    label_visibility="collapsed"
                )
                c_wts = json.loads(child['weights'])
                c_score = c_wts[c_opts.index(c_selected)] if c_selected in c_opts else 0
                st.session_state.nrq_ans[cid_s] = {'answer': c_selected, 'score': c_score}
            else:
                # Remove stale child answer if trigger no longer matches
                cid_s = str(child['id'])
                if cid_s in st.session_state.nrq_ans:
                    del st.session_state.nrq_ans[cid_s]

        st.markdown("<div style='margin-bottom:.25rem;'></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    cb1,_,cb2 = st.columns([1,3,1])
    with cb1:
        if st.button("← Back"): st.session_state.nrq_step=1; st.rerun()
    with cb2:
        if st.button("Review Answers →", type="primary", use_container_width=True):
            if not st.session_state.nrq_ans:
                st.error("Please answer the questions before continuing.")
            else:
                st.session_state.nrq_step=3; st.rerun()

def _nrq_s3(user):
    ans = st.session_state.nrq_ans
    all_qs_map = {q['id']:q for q in all_questions_flat()}
    cfg = get_cfg()
    total = sum(v['score'] for v in ans.values())
    max_s = sum(all_qs_map[int(qid)]['max_score'] for qid in ans if int(qid) in all_qs_map)
    pct = (total/max_s*100) if max_s>0 else 0
    outcome = calc_outcome(pct, cfg)
    o_label,o_color,o_bg,o_border,o_icon,o_desc = OUTCOME_CFG[outcome]

    st.markdown('<div style="font-weight:700;font-size:.95rem;margin-bottom:1rem;">📝 Review & Submit</div>', unsafe_allow_html=True)
    c1,c2 = st.columns([3,2])
    with c1:
        st.markdown(f'<div class="card card-sm" style="margin-bottom:1rem;"><div style="font-weight:700;font-size:1rem;">{st.session_state.nrq_name}</div><div style="font-size:.82rem;color:#64748B;margin-top:.2rem;">{st.session_state.nrq_desc or "No description"}</div><div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:.75rem;margin-top:.875rem;"><div><div style="font-size:.65rem;color:#94A3B8;text-transform:uppercase;font-weight:600;">Owner</div><div style="font-size:.82rem;font-weight:500;">{st.session_state.nrq_owner or "—"}</div></div><div><div style="font-size:.65rem;color:#94A3B8;text-transform:uppercase;font-weight:600;">Type</div><div style="font-size:.82rem;font-weight:500;">{st.session_state.nrq_type}</div></div><div><div style="font-size:.65rem;color:#94A3B8;text-transform:uppercase;font-weight:600;">Go-Live</div><div style="font-size:.82rem;font-weight:500;">{st.session_state.nrq_golive or "—"}</div></div></div></div>', unsafe_allow_html=True)

        # Show answers grouped by category — NO scores
        by_cat = {}
        for qid_s, ad in ans.items():
            q = all_qs_map.get(int(qid_s))
            if q: by_cat.setdefault(q['category'],[]).append((q, ad['answer']))

        for cat, items in by_cat.items():
            st.markdown(f'<div style="font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#94A3B8;margin:.75rem 0 .4rem;">{cat}</div>', unsafe_allow_html=True)
            for q, ans_text in items:
                indent = "margin-left:1rem;border-left:2px solid #DDD6FE;" if q.get('parent_question_id') else ""
                st.markdown(f'<div style="padding:.5rem .75rem;border:1px solid #F1F5F9;border-radius:8px;margin-bottom:.3rem;{indent}"><div style="font-size:.78rem;color:#64748B;">{q["text"]}</div><div style="font-size:.85rem;font-weight:600;color:#0F172A;margin-top:.15rem;">→ {ans_text}</div></div>', unsafe_allow_html=True)

    with c2:
        # Show outcome — NO score percentage
        st.markdown(f'<div class="obanner" style="background:{o_bg};border-color:{o_border};margin-bottom:1rem;"><div class="oicon">{o_icon}</div><div><div class="otitle" style="color:{o_color};">Preliminary Outcome</div><div style="font-size:.95rem;font-weight:700;color:{o_color};margin-top:.15rem;">{o_label}</div><div class="odesc" style="color:#64748B;">{o_desc}</div></div></div>', unsafe_allow_html=True)
        st.markdown('<div class="alert ai" style="font-size:.78rem;">Once submitted, your answers are locked for review. The SbD team may return the request if revisions are needed.</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    cb1,_,cb3 = st.columns([1,1,2])
    with cb1:
        if st.button("← Revise"): st.session_state.nrq_step=2; st.rerun()
    with cb3:
        if st.button("✅  Submit for Review", type="primary", use_container_width=True):
            # If a draft request exists, reuse it; otherwise create new
            if st.session_state.nrq_rid:
                rid = st.session_state.nrq_rid
                _exe("UPDATE requests SET project_name=?,project_description=?,business_owner=?,project_type=?,go_live_date=?,updated_at=? WHERE id=?",
                     (st.session_state.nrq_name, st.session_state.nrq_desc, st.session_state.nrq_owner,
                      st.session_state.nrq_type, st.session_state.nrq_golive, datetime.now().isoformat(), rid))
            else:
                rid, ref = create_request(st.session_state.nrq_name, st.session_state.nrq_desc,
                                          st.session_state.nrq_owner, st.session_state.nrq_type,
                                          st.session_state.nrq_golive, user['id'])
                st.session_state.nrq_rid=rid; st.session_state.nrq_ref=ref
            _,__,pct = save_answers(rid, st.session_state.nrq_ans)
            outcome = calc_outcome(pct, get_cfg())
            submit_request(rid, outcome, user['id'])
            st.session_state.nrq_outcome=outcome; st.session_state.nrq_step=4; st.rerun()

def _nrq_s4(user):
    outcome=st.session_state.get('nrq_outcome','no_sbd'); rid=st.session_state.get('nrq_rid')
    ref=st.session_state.get('nrq_ref',''); o_label,o_color,o_bg,o_border,o_icon,o_desc=OUTCOME_CFG[outcome]
    _,c,_ = st.columns([1,2,1])
    with c:
        st.markdown(f'<div style="text-align:center;padding:2rem 0 1.5rem;"><div style="font-size:3.5rem;">{o_icon}</div><div style="font-size:1.4rem;font-weight:800;color:#0F172A;margin-top:.5rem;">Request Submitted</div><div style="margin-top:.5rem;"><span class="ref" style="font-size:.9rem;">{ref}</span></div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="obanner" style="background:{o_bg};border-color:{o_border};margin-bottom:1.25rem;"><div class="oicon">{o_icon}</div><div><div style="font-size:.72rem;font-weight:600;color:#64748B;text-transform:uppercase;">Preliminary Assessment</div><div class="otitle" style="color:{o_color};margin-top:.15rem;">{o_label}</div><div class="odesc" style="color:#64748B;">{o_desc}</div></div></div>', unsafe_allow_html=True)
        st.markdown('<div class="alert aw">Your answers are now locked. The SbD team will review within 5 business days. You will be notified if your request is returned for revision.</div>', unsafe_allow_html=True)
        ca,cb=st.columns(2)
        with ca:
            if st.button("View Request →",type="primary",use_container_width=True):
                st.session_state.selected_req=rid; st.session_state.page="request_detail"
                for k in ['nrq_step','nrq_rid','nrq_ref','nrq_ans','nrq_name','nrq_desc','nrq_owner','nrq_type','nrq_golive','nrq_outcome']: st.session_state.pop(k,None)
                st.rerun()
        with cb:
            if st.button("New Request",use_container_width=True):
                for k in ['nrq_step','nrq_rid','nrq_ref','nrq_ans','nrq_name','nrq_desc','nrq_owner','nrq_type','nrq_golive','nrq_outcome']: st.session_state.pop(k,None)
                st.rerun()

# Edit existing draft (when returned by manager)
def page_edit_request(user):
    rid = st.session_state.get('selected_req')
    req = get_req(rid) if rid else None
    if not req or req['status']!='draft' or req['created_by']!=user['id']:
        st.error("This request cannot be edited."); return

    st.markdown(f'<div class="pg-hdr"><div class="pg-title">Edit Request</div><div class="pg-sub"><span class="ref">{req["ref_number"]}</span> — returned for revision</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="alert aw">This request was returned by the SbD team for revision. Update your answers and resubmit.</div>', unsafe_allow_html=True)

    # Pre-fill session state from existing request
    for k,v in [('nrq_step',2),('nrq_rid',rid),('nrq_ref',req['ref_number']),
                ('nrq_name',req.get('project_name','')),('nrq_desc',req.get('project_description','')),
                ('nrq_owner',req.get('business_owner','')),('nrq_type',req.get('project_type','New Application')),
                ('nrq_golive',req.get('go_live_date',''))]:
        if k not in st.session_state: st.session_state[k]=v

    # Load existing answers into nrq_ans if not already set
    if 'nrq_ans' not in st.session_state or not st.session_state.nrq_ans:
        existing = req_answers(rid)
        st.session_state.nrq_ans = {str(a['question_id']): {'answer':a['answer'],'score':a['score']} for a in existing}

    stepper(["Project Info","Assessment","Review & Submit","Outcome"], st.session_state.nrq_step)
    st.markdown("<br>", unsafe_allow_html=True)
    step = st.session_state.nrq_step
    if step==1: _nrq_s1(user)
    elif step==2: _nrq_s2(user)
    elif step==3: _nrq_s3(user)
    elif step==4: _nrq_s4(user)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: MY REQUESTS / ASSIGNED
# ══════════════════════════════════════════════════════════════════════════════

def page_my_requests(user):
    st.markdown('<div class="pg-hdr"><div class="pg-title">My Requests</div><div class="pg-sub">SbD requests you have created or been granted access to</div></div>', unsafe_allow_html=True)
    _req_list(user, user_reqs(user['id']))

def page_assigned(user):
    fm = {'security_architect':'architect_id','security_engineer':'engineer_id','assurance':'assurance_id'}
    field = fm.get(user['role'])
    if not field: st.error("Not applicable."); return
    st.markdown(f'<div class="pg-hdr"><div class="pg-title">Assigned to Me</div><div class="pg-sub">Requests where you are the assigned {ROLE_LABELS.get(user["role"],"")}</div></div>', unsafe_allow_html=True)
    _req_list(user, assigned_reqs(user['id'], field))

def _req_list(user, reqs):
    cf1,cf2,cf3=st.columns([2,3,1])
    with cf1: sf=st.selectbox("Status",["All","Draft","Pending Review","Awaiting Assignment","In Progress","Pending Sign-off","Completed","No SBD"])
    with cf2: search=st.text_input("Search","",placeholder="Project name or reference...")
    with cf3:
        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("➕ New",type="primary",use_container_width=True): st.session_state.page="new_request"; st.rerun()
    sm={"Draft":['draft'],"Pending Review":['pending_review'],"Awaiting Assignment":['awaiting_assignment'],
        "In Progress":['architect_assigned','architect_completed','engineer_assigned','engineer_completed','assurance_assigned','assurance_completed'],
        "Pending Sign-off":['pending_signoff'],"Completed":['signoff_received'],"No SBD":['no_sbd_needed']}
    filtered=reqs
    if sf!="All": filtered=[r for r in filtered if r['status'] in sm.get(sf,[])]
    if search: s=search.lower(); filtered=[r for r in filtered if s in r['project_name'].lower() or s in r['ref_number'].lower()]
    if not filtered:
        st.markdown('<div class="card" style="text-align:center;padding:3rem;color:#94A3B8;"><div style="font-size:2rem;">📭</div><div style="font-weight:600;margin-top:.5rem;">No requests found</div></div>', unsafe_allow_html=True); return
    st.markdown(f'<div style="font-size:.78rem;color:#64748B;margin-bottom:.875rem;"><strong style="color:#0F172A;">{len(filtered)}</strong> request(s)</div>', unsafe_allow_html=True)
    for req in filtered:
        _,color,_,_ = STATUS_CFG.get(req['status'],('','#6B7280','','?'))
        is_draft = req['status']=='draft'
        ptype_str = f" · {req['project_type']}" if req.get('project_type') else ""
        st.markdown(f'<div class="card card-sm" style="margin-bottom:.75rem;border-left:3px solid {color};"><div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:.5rem;"><div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;"><span class="ref">{req["ref_number"]}</span>{sbadge(req["status"])}{obadge(req.get("sbd_outcome"))}</div></div><div style="font-weight:700;font-size:.92rem;">{req["project_name"]}</div><div style="font-size:.75rem;color:#94A3B8;">{fdates(req["created_at"])}{ptype_str}</div></div>', unsafe_allow_html=True)
        if req['status'] not in ['draft','no_sbd_needed']:
            st.markdown(pipeline_html(req['status']), unsafe_allow_html=True)
        bc1,bc2=st.columns([2,1])
        with bc1:
            if st.button("Open →",key=f"lst_{req['id']}"):
                st.session_state.selected_req=req['id']; st.session_state.page="request_detail"; st.rerun()
        with bc2:
            if is_draft and req['created_by']==user['id']:
                if st.button("✏️ Continue Editing",key=f"edit_{req['id']}"):
                    st.session_state.selected_req=req['id']; st.session_state.page="edit_request"
                    for k in ['nrq_step','nrq_rid','nrq_ref','nrq_ans','nrq_name','nrq_desc','nrq_owner','nrq_type','nrq_golive','nrq_outcome']: st.session_state.pop(k,None)
                    st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: REQUEST DETAIL
# ══════════════════════════════════════════════════════════════════════════════

def page_request_detail(user):
    rid=st.session_state.get('selected_req')
    if not rid: st.error("No request selected."); return
    role=user['role']; is_mgr=role in ['admin','sbd_manager']
    req=get_req(rid)
    if not req: st.error("Request not found."); return
    assigned=is_assigned_to(rid,user['id'])
    has_access=is_mgr or can_access(rid,user['id']) or assigned
    if not has_access: st.error("🚫 Access denied."); return
    has_write=is_mgr or can_access(rid,user['id'],write=True) or assigned
    is_locked=bool(req.get('is_locked'))
    is_submitter=req['created_by']==user['id']

    if st.button("← Back"):
        st.session_state.page="assigned" if (assigned and not can_access(rid,user['id'])) else "my_requests"
        st.rerun()

    _,color,_,_ = STATUS_CFG.get(req['status'],('','#6B7280','','?'))
    _,color,_,_ = STATUS_CFG.get(req['status'],('','#6B7280','','?'))
    _owner = f"Owner: {req['business_owner']} · " if req.get('business_owner') else ""
    _ptype = f"Type: {req['project_type']} · " if req.get('project_type') else ""
    st.markdown(f'''<div class="pg-hdr"><div><div style="display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;margin-bottom:.4rem;"><div class="pg-title">{req["project_name"]}</div><span class="ref">{req["ref_number"]}</span>'''+sbadge(req["status"])+obadge(req.get("sbd_outcome"))+f'''</div><div class="pg-sub">{_owner}{_ptype}Submitted {fdates(req.get("submitted_at"))}</div></div></div>''', unsafe_allow_html=True)

    if is_locked and req['status']!='draft':
        st.markdown('<div class="lock-banner">🔒 Answers are locked. This request is under review.</div>', unsafe_allow_html=True)

    if req['status'] not in ['draft','no_sbd_needed']:
        st.markdown(pipeline_html(req['status']), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

    tabs=st.tabs(["📋 Overview","🔍 Assessment","👥 Team & Access","💬 Comments","📜 Audit Trail"])
    with tabs[0]: _rd_overview(req,user,has_write,is_locked,is_mgr,assigned,is_submitter)
    with tabs[1]: _rd_assessment(req,user,is_mgr,is_submitter)
    with tabs[2]: _rd_team(req,user,has_write,is_locked,is_mgr)
    with tabs[3]: _rd_comments(req,user,is_mgr)
    with tabs[4]: _rd_audit(req)

def _rd_overview(req,user,has_write,is_locked,is_mgr,assigned,is_submitter):
    c1,c2=st.columns([3,2])
    with c1:
        outcome=req.get('sbd_outcome')
        if outcome:
            o_label,o_color,o_bg,o_border,o_icon,o_desc=OUTCOME_CFG.get(outcome,OUTCOME_CFG['no_sbd'])
            st.markdown(f'<div class="obanner" style="background:{o_bg};border-color:{o_border};margin-bottom:1rem;"><div class="oicon">{o_icon}</div><div><div class="otitle" style="color:{o_color};">{o_label}</div><div class="odesc" style="color:#64748B;">{o_desc}</div></div></div>', unsafe_allow_html=True)

        _desc_block = f'<div style="margin-top:.875rem;padding-top:.875rem;border-top:1px solid #F1F5F9;"><div style="font-size:.65rem;color:#94A3B8;text-transform:uppercase;font-weight:600;">Description</div><div style="font-size:.85rem;color:#334155;margin-top:.15rem;">{req["project_description"]}</div></div>' if req.get('project_description') else ''
        st.markdown('<div class="card card-sm" style="margin-bottom:1rem;"><div style="display:grid;grid-template-columns:1fr 1fr;gap:.875rem;">'
            '<div><div style="font-size:.65rem;color:#94A3B8;text-transform:uppercase;font-weight:600;">Business Owner</div>'
            f'<div style="font-size:.87rem;font-weight:500;margin-top:.15rem;">{req.get("business_owner") or "—"}</div></div>'
            '<div><div style="font-size:.65rem;color:#94A3B8;text-transform:uppercase;font-weight:600;">Project Type</div>'
            f'<div style="font-size:.87rem;font-weight:500;margin-top:.15rem;">{req.get("project_type") or "—"}</div></div>'
            '<div><div style="font-size:.65rem;color:#94A3B8;text-transform:uppercase;font-weight:600;">Go-Live Target</div>'
            f'<div style="font-size:.87rem;font-weight:500;margin-top:.15rem;">{req.get("go_live_date") or "—"}</div></div>'
            '<div><div style="font-size:.65rem;color:#94A3B8;text-transform:uppercase;font-weight:600;">Submitted</div>'
            f'<div style="font-size:.87rem;font-weight:500;margin-top:.15rem;">{fdates(req.get("submitted_at"))}</div></div>'
            f'</div>{_desc_block}</div>', unsafe_allow_html=True)

        if req.get('architect_url'):
            _anotes = f'<div style="font-size:.8rem;color:#047857;margin-top:.4rem;">{req["architect_notes"]}</div>' if req.get('architect_notes') else ''
            st.markdown(f'<div class="card card-sm" style="background:#F0FDF4;border-color:#A7F3D0;">'
                '<div style="font-size:.65rem;font-weight:700;text-transform:uppercase;color:#065F46;">Architecture Document</div>'
                f'<a href="{req["architect_url"]}" target="_blank" style="color:#059669;font-weight:600;font-size:.88rem;">🔗 View Document</a>'
                f'{_anotes}</div>', unsafe_allow_html=True)

        if req.get('engineer_notes'):
            st.markdown(f'<div class="card card-sm" style="margin-top:.75rem;"><div style="font-size:.65rem;font-weight:700;text-transform:uppercase;color:#64748B;">Engineering Notes</div><div style="font-size:.85rem;margin-top:.3rem;">{req["engineer_notes"]}</div></div>', unsafe_allow_html=True)

        if req.get('assurance_notes'):
            st.markdown(f'<div class="card card-sm" style="margin-top:.75rem;"><div style="font-size:.65rem;font-weight:700;text-transform:uppercase;color:#64748B;">Assurance Notes</div><div style="font-size:.85rem;margin-top:.3rem;">{req["assurance_notes"]}</div></div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div style="font-size:.72rem;font-weight:700;text-transform:uppercase;color:#64748B;margin-bottom:.75rem;">Phase Timeline</div>', unsafe_allow_html=True)
        st.markdown(phase_tl(req), unsafe_allow_html=True)

        # Show assigned team members
        assigned_html=""
        for fld,lbl,icon in [('architect_id','Security Architect','🏗'),('engineer_id','Security Engineer','⚙'),('assurance_id','Assurance Analyst','🔍')]:
            if req.get(fld):
                p=get_user_id(req[fld])
                if p: assigned_html+=f'<div style="display:flex;align-items:center;gap:.625rem;padding:.5rem 0;border-bottom:1px solid #F8FAFC;"><span>{icon}</span><div><div style="font-weight:600;font-size:.82rem;">{p["name"]}</div><div style="font-size:.72rem;color:#94A3B8;">{lbl}</div></div></div>'
        if assigned_html:
            st.markdown(f'<div class="card card-sm" style="margin-top:1rem;"><div style="font-size:.72rem;font-weight:700;text-transform:uppercase;color:#64748B;margin-bottom:.5rem;">Assigned Team</div>{assigned_html}</div>', unsafe_allow_html=True)

    # ── Actions ──────────────────────────────────────────────────────────────
    if not (is_locked and req['status']=='signoff_received'):
        _rd_actions(req,user,is_mgr,assigned)

def _rd_actions(req,user,is_mgr,assigned):
    status=req['status']; rid=req['id']
    st.markdown("---")
    st.markdown('<div style="font-weight:700;font-size:.9rem;margin-bottom:.75rem;">Actions</div>', unsafe_allow_html=True)
    cols=st.columns(5); ci=[0]

    def btn(label,key,primary=True):
        with cols[ci[0]%5]:
            r=st.button(label,key=key,type="primary" if primary else "secondary",use_container_width=True)
        ci[0]+=1; return r

    if is_mgr:
        if status=='pending_review':
            if btn("✅ Confirm & Assess","act_confirm"):
                update_status(rid,'awaiting_assignment',user['id'],'Review confirmed — awaiting resource assignment'); st.rerun()
            # Return to draft with reason
            with cols[ci[0]%5]:
                st.markdown('<div style="font-size:.72rem;color:#64748B;margin-bottom:.2rem;">Return for revision:</div>', unsafe_allow_html=True)
            ci[0]+=1
            reason_key=f"return_reason_{rid}"
            if reason_key not in st.session_state: st.session_state[reason_key]=""
            with cols[ci[0]%5]:
                reason=st.text_input("Reason",key=f"ri_{rid}",label_visibility="collapsed",placeholder="Reason for returning...")
            ci[0]+=1
            if btn("↩ Return to Applicant","act_return",primary=False):
                if reason.strip():
                    return_to_draft(rid,user['id'],reason.strip())
                    add_comment(rid,user['id'],f"Request returned for revision: {reason.strip()}",internal=False)
                    st.success("Request returned to applicant for revision."); st.rerun()
                else: st.error("Please provide a reason.")
        if status=='awaiting_assignment': pass  # handled in assign_resources page
        if status=='architect_assigned':
            if btn("✅ Architecture Done","act_archdone"): update_status(rid,'architect_completed',user['id'],'Architecture review completed'); st.rerun()
        if status=='architect_completed':
            if btn("➡ Move to Engineer","act_toeng"): update_status(rid,'engineer_assigned',user['id'],'Assigned to engineering phase'); st.rerun()
        if status=='engineer_assigned':
            if btn("✅ Engineering Done","act_engdone"): update_status(rid,'engineer_completed',user['id'],'Engineering work completed'); st.rerun()
        if status=='engineer_completed':
            if btn("➡ Move to Assurance","act_toassur"): update_status(rid,'assurance_assigned',user['id'],'Assigned to assurance phase'); st.rerun()
        if status=='assurance_assigned':
            if btn("✅ Assurance Done","act_assurdone"): update_status(rid,'assurance_completed',user['id'],'Assurance review completed'); st.rerun()
        if status=='assurance_completed':
            if btn("➡ Move to Sign-off","act_tosignoff"): update_status(rid,'pending_signoff',user['id'],'Moved to sign-off queue'); st.rerun()
        if status=='pending_signoff':
            if btn("🎉 Record Sign-off","act_signoff"): update_status(rid,'signoff_received',user['id'],'Sign-off received',{'signoff_by':user['id']}); st.rerun()

    # Architect: add doc link
    if (assigned and req.get('architect_id')==user['id']) or is_mgr:
        if status in ['architect_assigned','architect_completed','engineer_assigned','engineer_completed',
                      'assurance_assigned','assurance_completed','pending_signoff','signoff_received']:
            with st.expander("🔗 Architecture Document"):
                au=st.text_input("Document URL",value=req.get('architect_url',''),key="arch_url")
                an=st.text_area("Notes",value=req.get('architect_notes',''),key="arch_notes",height=70)
                if st.button("Save",key="save_arch",type="primary"):
                    c2=_conn(); c2.execute("UPDATE requests SET architect_url=?,architect_notes=? WHERE id=?",(au,an,rid)); c2.commit(); c2.close()
                    st.success("Saved."); st.rerun()

    # Engineer: notes
    if (assigned and req.get('engineer_id')==user['id']) or is_mgr:
        if status in ['engineer_assigned','engineer_completed','assurance_assigned','assurance_completed','pending_signoff']:
            with st.expander("⚙ Engineering Notes"):
                en=st.text_area("Notes",value=req.get('engineer_notes',''),key="eng_notes",height=100)
                if st.button("Save Notes",key="save_eng",type="primary"):
                    c2=_conn(); c2.execute("UPDATE requests SET engineer_notes=? WHERE id=?",(en,rid)); c2.commit(); c2.close()
                    st.success("Saved."); st.rerun()

    # Assurance: notes
    if (assigned and req.get('assurance_id')==user['id']) or is_mgr:
        if status in ['assurance_assigned','assurance_completed','pending_signoff']:
            with st.expander("🔍 Assurance Notes"):
                asn=st.text_area("Notes",value=req.get('assurance_notes',''),key="assur_notes",height=100)
                if st.button("Save Notes",key="save_assur",type="primary"):
                    c2=_conn(); c2.execute("UPDATE requests SET assurance_notes=? WHERE id=?",(asn,rid)); c2.commit(); c2.close()
                    st.success("Saved."); st.rerun()

def _rd_assessment(req,user,is_mgr,is_submitter):
    answers=req_answers(req['id'])
    if not answers: st.info("No assessment answers on record."); return

    # Submitters NEVER see scores, percentages, or score indicators
    show_scores = is_mgr and not is_submitter

    if is_submitter:
        st.markdown('<div class="alert ai">Your submitted answers are shown below. Individual scores are not visible to applicants.</div>', unsafe_allow_html=True)
    elif is_mgr:
        st.markdown('<div class="alert as">Full scoring detail visible to SbD team only.</div>', unsafe_allow_html=True)

    by_cat={}
    for a in answers: by_cat.setdefault(a['category'],[]).append(a)

    for cat,items in by_cat.items():
        st.markdown(f'<div style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#64748B;margin:.875rem 0 .5rem;">{cat}</div>', unsafe_allow_html=True)
        for a in items:
            is_child = bool(a.get('parent_question_id'))
            indent = "margin-left:1.5rem;border-left:2px solid #DDD6FE;" if is_child else ""
            if show_scores:
                wts=json.loads(a['weights']) if isinstance(a['weights'],str) else a['weights']
                mx=max(wts) if wts else 10; sc=a['score']; sp=(sc/mx*100) if mx>0 else 0
                bc="#EF4444" if sp>=70 else ("#F59E0B" if sp>=40 else "#10B981")
                score_h=f'<div style="font-family:var(--mono);font-weight:700;color:{bc};white-space:nowrap;">{sc:.0f}/{mx}</div>'
                bar_h=f'<div style="background:#F1F5F9;border-radius:999px;height:3px;margin:4px 0 6px;"><div style="background:{bc};height:3px;border-radius:999px;width:{sp:.1f}%;"></div></div>'
            else:
                score_h=""; bar_h=""
            child_tag = '<span style="font-size:.65rem;color:#8B5CF6;font-weight:700;">↳ FOLLOW-UP</span> ' if is_child else ''
            st.markdown(f'<div style="padding:.625rem .875rem;border:1px solid #F1F5F9;border-radius:8px;margin-bottom:.375rem;{indent}"><div style="display:flex;justify-content:space-between;align-items:flex-start;gap:.75rem;"><div style="flex:1;min-width:0;"><div style="font-size:.78rem;color:#64748B;">{child_tag}{a["qtxt"]}</div><div style="font-size:.85rem;font-weight:600;color:#0F172A;margin-top:.15rem;">→ {a["answer"]}</div></div>{score_h}</div>{bar_h}</div>', unsafe_allow_html=True)

def _rd_team(req,user,has_write,is_locked,is_mgr):
    rid=req['id']
    creator=get_user_id(req['created_by'])
    if creator:
        dept=f" · {creator.get('department','')}" if creator.get('department') else ''
        st.markdown(f'<div style="display:flex;align-items:center;gap:.875rem;padding:.875rem;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:var(--r);margin-bottom:.75rem;"><div style="width:38px;height:38px;background:linear-gradient(135deg,#3B82F6,#8B5CF6);border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-weight:700;flex-shrink:0;">{creator["name"][0]}</div><div style="flex:1;"><div style="font-weight:600;font-size:.9rem;">{creator["name"]}</div><div style="font-size:.75rem;color:#64748B;">{creator["email"]}{dept}</div></div><span class="badge" style="background:#ECFDF5;color:#065F46;">Owner</span></div>', unsafe_allow_html=True)

    perms=get_perms(rid)
    for p in perms:
        pc="#065F46" if p['permission']=='write' else '#1E40AF'
        pb="#ECFDF5" if p['permission']=='write' else '#EFF6FF'
        c1,c2=st.columns([6,1])
        with c1: st.markdown(f'<div style="display:flex;align-items:center;gap:.75rem;padding:.6rem .875rem;border:1px solid #E2E8F0;border-radius:8px;margin-bottom:.375rem;"><div style="width:30px;height:30px;background:#64748B;border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-size:.8rem;font-weight:700;flex-shrink:0;">{p["name"][0]}</div><div style="flex:1;"><div style="font-weight:500;font-size:.87rem;">{p["name"]}</div><div style="font-size:.73rem;color:#94A3B8;">{p["email"]}</div></div><span class="badge" style="background:{pb};color:{pc};">{p["permission"].upper()}</span></div>', unsafe_allow_html=True)
        with c2:
            if (has_write or is_mgr) and not is_locked:
                if st.button("✕",key=f"rmperm_{p['user_id']}"): del_perm(rid,p['user_id']); st.rerun()

    if (has_write or is_mgr) and not is_locked:
        st.markdown("---")
        st.markdown('<div style="font-weight:600;font-size:.88rem;margin-bottom:.625rem;">Grant Access</div>', unsafe_allow_html=True)
        existing={p['user_id'] for p in perms}|{req['created_by']}
        avail=[u for u in all_users() if u['id'] not in existing and u['id']!=user['id']]
        if avail:
            umap={u['id']:f"{u['name']} (@{u['username']}) · {ROLE_LABELS.get(u['role'],u['role'])}" for u in avail}
            ca,cb,cc=st.columns([3,2,1])
            with ca: sel=st.selectbox("User",[u['id'] for u in avail],format_func=lambda x:umap[x],label_visibility="collapsed")
            with cb: pl=st.selectbox("Permission",["read","write"],label_visibility="collapsed")
            with cc:
                if st.button("Grant",type="primary",use_container_width=True): add_perm(rid,sel,pl,user['id']); st.success("Granted."); st.rerun()

def _rd_comments(req,user,is_mgr):
    rid=req['id']
    comments=get_comments(rid,show_internal=is_mgr)
    if not comments:
        st.markdown('<div style="text-align:center;padding:2rem;color:#94A3B8;font-size:.85rem;">No comments yet. Be the first to add one.</div>', unsafe_allow_html=True)
    for c in comments:
        is_int=bool(c.get('is_internal'))
        bg="#FFFBEB" if is_int else "#F8FAFC"; border="#FDE68A" if is_int else "#E2E8F0"
        tag='<span class="badge" style="background:#FEF3C7;color:#92400E;font-size:.62rem;">Internal</span> ' if is_int else ''
        st.markdown(f'<div style="background:{bg};border:1px solid {border};border-radius:8px;padding:.875rem 1rem;margin-bottom:.5rem;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.4rem;"><div style="font-size:.8rem;font-weight:600;color:#334155;">{tag}{c["name"]} <span style="color:#94A3B8;font-weight:400;">· {ROLE_LABELS.get(c["role"],c["role"])}</span></div><div style="font-size:.72rem;color:#94A3B8;">{fdate(c["created_at"])}</div></div><div style="font-size:.85rem;color:#0F172A;line-height:1.55;">{c["text"]}</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    with st.form(f"cmt_{rid}"):
        txt=st.text_area("Add comment",placeholder="Type your comment here...",height=90,label_visibility="collapsed")
        ca,cb=st.columns([3,1])
        with ca: internal=st.checkbox("Internal note (SbD team only)") if is_mgr else False
        with cb:
            if st.form_submit_button("Post",type="primary",use_container_width=True):
                if txt.strip(): add_comment(rid,user['id'],txt.strip(),internal); st.rerun()
                else: st.error("Comment cannot be empty.")

def _rd_audit(req):
    hist=status_hist(req['id'])
    if not hist: st.info("No history yet."); return
    html='<div class="tl">'
    for item in reversed(hist):
        _notes_html = f'<div class="tl-n">{item["notes"]}</div>' if item.get('notes') else ''
        html+=f'<div class="tl-item"><div class="tl-dot td-done"></div>'\
            f'<div class="tl-t">{item.get("from_status","—") or "(created)"} → {item["to_status"]}</div>'\
            f'<div class="tl-m">By {item["by_name"]} · {fdate(item["created_at"])}</div>'\
            f'{_notes_html}</div>'
    st.markdown(html+'</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: REVIEW QUEUE
# ══════════════════════════════════════════════════════════════════════════════

def page_pending_review(user):
    if user['role'] not in ['admin','sbd_manager']: st.error("Access denied."); return
    st.markdown('<div class="pg-hdr"><div class="pg-title">Review Queue</div><div class="pg-sub">Submitted requests awaiting initial SbD review</div></div>', unsafe_allow_html=True)
    reqs=reqs_by_status(['pending_review'])
    if not reqs:
        st.markdown('<div class="card" style="text-align:center;padding:3rem;color:#94A3B8;"><div style="font-size:2rem;">✅</div><div style="font-weight:600;margin-top:.5rem;">Review queue is clear</div></div>', unsafe_allow_html=True); return
    st.markdown(f'<div style="font-size:.78rem;color:#64748B;margin-bottom:.875rem;"><strong>{len(reqs)}</strong> awaiting review</div>', unsafe_allow_html=True)
    for req in reqs:
        with st.expander(f"📋 {req['ref_number']} — {req['project_name']}", expanded=True):
            c1,c2,c3=st.columns([4,2,2])
            with c1:
                st.markdown(f'<div style="font-weight:600;">{req["project_name"]}</div><div style="font-size:.78rem;color:#94A3B8;">Submitted {fdate(req.get("submitted_at"))} · {req.get("project_type","")}</div>', unsafe_allow_html=True)
                if req.get('sbd_outcome'):
                    st.markdown(f'<div style="margin-top:.4rem;">{obadge(req["sbd_outcome"])}</div>', unsafe_allow_html=True)
            with c2:
                if st.button("View Full Request",key=f"prv_{req['id']}"):
                    st.session_state.selected_req=req['id']; st.session_state.page="request_detail"; st.rerun()
            with c3:
                if st.button("✅ Confirm Review",key=f"prc_{req['id']}",type="primary",use_container_width=True):
                    update_status(req['id'],'awaiting_assignment',user['id'],'Initial review confirmed'); st.rerun()
            # Inline return with reason
            st.markdown('<div style="margin-top:.75rem;padding-top:.75rem;border-top:1px solid #F1F5F9;">', unsafe_allow_html=True)
            reason=st.text_input("Return for revision — reason:",key=f"prr_{req['id']}",placeholder="Describe what needs to change...")
            if st.button("↩ Return to Applicant",key=f"prrb_{req['id']}",type="secondary"):
                if reason.strip():
                    return_to_draft(req['id'],user['id'],reason.strip())
                    add_comment(req['id'],user['id'],f"Request returned for revision: {reason.strip()}",internal=False)
                    st.success("Returned to applicant."); st.rerun()
                else: st.error("Please enter a reason.")
            st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: ASSIGN RESOURCES — architect, engineer, assurance each independently
# ══════════════════════════════════════════════════════════════════════════════

def page_assign_resources(user):
    if user['role'] not in ['admin','sbd_manager']: st.error("Access denied."); return
    st.markdown('<div class="pg-hdr"><div class="pg-title">Assign Resources</div><div class="pg-sub">Assign security professionals to requests</div></div>', unsafe_allow_html=True)

    # Show all requests that need ANY assignment — not just next in sequence
    reqs=reqs_by_status(['awaiting_assignment','architect_assigned','architect_completed',
                          'engineer_assigned','engineer_completed','assurance_assigned','assurance_completed'])
    if not reqs: st.info("No requests currently need assignment."); return

    architects=all_users('security_architect')
    engineers=all_users('security_engineer')
    assurance_users=all_users('assurance')

    for req in reqs:
        status=req['status']
        _,color,_,_ = STATUS_CFG.get(status,('','#6B7280','','?'))
        with st.expander(f"{req['ref_number']} — {req['project_name']}  |  {STATUS_CFG.get(status,('',))[0]}", expanded=True):
            st.markdown(f'<div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:.75rem;">{sbadge(status)}{obadge(req.get("sbd_outcome"))}</div>', unsafe_allow_html=True)

            # ── ARCHITECT assignment ─────────────────────────────────────────
            if status=='awaiting_assignment':
                st.markdown('<div style="font-weight:600;font-size:.85rem;margin-bottom:.5rem;">🏗 Assign Security Architect</div>', unsafe_allow_html=True)
                if architects:
                    opts={p['id']:f"{p['name']}  ({p.get('department','')}) · @{p['username']}" for p in architects}
                    cur=req.get('architect_id')
                    ca,cb=st.columns([3,1])
                    with ca: sel=st.selectbox("Architect",list(opts.keys()),format_func=lambda x:opts[x],key=f"arch_{req['id']}",index=list(opts.keys()).index(cur) if cur in opts else 0,label_visibility="collapsed")
                    with cb:
                        if st.button("Assign →",key=f"abtn_{req['id']}",type="primary",use_container_width=True):
                            c2=_conn(); c2.execute("UPDATE requests SET architect_id=? WHERE id=?",(sel,req['id'])); c2.commit(); c2.close()
                            update_status(req['id'],'architect_assigned',user['id'],f"Architect assigned: {opts[sel][:40]}")
                            st.success("Architect assigned!"); st.rerun()
                else: st.warning("No security architects found. Add one in User Management.")

            # ── ENGINEER assignment ──────────────────────────────────────────
            # Offer engineer assignment at architect_completed OR if status is engineer-phase
            if status in ['architect_completed','engineer_assigned','engineer_completed']:
                st.markdown('<div style="font-weight:600;font-size:.85rem;margin:1rem 0 .5rem;">⚙ Assign Security Engineer</div>', unsafe_allow_html=True)
                if engineers:
                    opts={p['id']:f"{p['name']}  ({p.get('department','')}) · @{p['username']}" for p in engineers}
                    cur=req.get('engineer_id')
                    ca,cb=st.columns([3,1])
                    with ca: sel=st.selectbox("Engineer",list(opts.keys()),format_func=lambda x:opts[x],key=f"eng_{req['id']}",index=list(opts.keys()).index(cur) if cur in opts else 0,label_visibility="collapsed")
                    with cb:
                        if st.button("Assign →",key=f"ebtn_{req['id']}",type="primary",use_container_width=True):
                            c2=_conn(); c2.execute("UPDATE requests SET engineer_id=? WHERE id=?",(sel,req['id'])); c2.commit(); c2.close()
                            if status=='architect_completed':
                                update_status(req['id'],'engineer_assigned',user['id'],f"Engineer assigned: {opts[sel][:40]}")
                            else:
                                c2=_conn(); c2.execute("UPDATE requests SET updated_at=? WHERE id=?",(datetime.now().isoformat(),req['id'])); c2.commit(); c2.close()
                                _exe("INSERT INTO status_history (request_id,from_status,to_status,changed_by,notes,created_at) VALUES (?,?,?,?,?,?)",
                                     (req['id'],status,status,user['id'],f"Engineer reassigned: {opts[sel][:40]}",datetime.now().isoformat()))
                            st.success("Engineer assigned!"); st.rerun()
                else: st.warning("No security engineers found. Add one in User Management.")

            # ── ASSURANCE assignment ─────────────────────────────────────────
            if status in ['engineer_completed','assurance_assigned','assurance_completed']:
                st.markdown('<div style="font-weight:600;font-size:.85rem;margin:1rem 0 .5rem;">🔍 Assign Assurance Analyst</div>', unsafe_allow_html=True)
                if assurance_users:
                    opts={p['id']:f"{p['name']}  ({p.get('department','')}) · @{p['username']}" for p in assurance_users}
                    cur=req.get('assurance_id')
                    ca,cb=st.columns([3,1])
                    with ca: sel=st.selectbox("Assurance",list(opts.keys()),format_func=lambda x:opts[x],key=f"assur_{req['id']}",index=list(opts.keys()).index(cur) if cur in opts else 0,label_visibility="collapsed")
                    with cb:
                        if st.button("Assign →",key=f"asbtn_{req['id']}",type="primary",use_container_width=True):
                            c2=_conn(); c2.execute("UPDATE requests SET assurance_id=? WHERE id=?",(sel,req['id'])); c2.commit(); c2.close()
                            if status=='engineer_completed':
                                update_status(req['id'],'assurance_assigned',user['id'],f"Assurance assigned: {opts[sel][:40]}")
                            else:
                                _exe("INSERT INTO status_history (request_id,from_status,to_status,changed_by,notes,created_at) VALUES (?,?,?,?,?,?)",
                                     (req['id'],status,status,user['id'],f"Assurance reassigned: {opts[sel][:40]}",datetime.now().isoformat()))
                            st.success("Assurance assigned!"); st.rerun()
                else: st.warning("No assurance analysts found. Add one in User Management.")

            if st.button("View Full Request",key=f"arv_{req['id']}"):
                st.session_state.selected_req=req['id']; st.session_state.page="request_detail"; st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SIGN-OFF QUEUE
# ══════════════════════════════════════════════════════════════════════════════

def page_signoff(user):
    if user['role'] not in ['admin','sbd_manager']: st.error("Access denied."); return
    st.markdown('<div class="pg-hdr"><div class="pg-title">Sign-Off Queue</div><div class="pg-sub">Requests ready for final SbD sign-off</div></div>', unsafe_allow_html=True)
    reqs=reqs_by_status(['assurance_completed','pending_signoff'])
    if not reqs: st.info("Sign-off queue is empty."); return
    for req in reqs:
        c1,c2,c3=st.columns([4,2,2])
        with c1:
            st.markdown(f'<div class="card card-sm"><div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:.35rem;">{sbadge(req["status"])}{obadge(req.get("sbd_outcome"))}</div><div style="font-weight:600;">{req["project_name"]} <span class="ref">{req["ref_number"]}</span></div><div style="font-size:.75rem;color:#94A3B8;">{fdates(req["created_at"])}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown("<br>",unsafe_allow_html=True)
            if req['status']=='assurance_completed':
                if st.button("➡ Move to Sign-off",key=f"sov_{req['id']}",type="primary",use_container_width=True):
                    update_status(req['id'],'pending_signoff',user['id'],'Moved to sign-off queue'); st.rerun()
        with c3:
            st.markdown("<br>",unsafe_allow_html=True)
            b1,b2=st.columns(2)
            with b1:
                if st.button("View",key=f"sovw_{req['id']}"): st.session_state.selected_req=req['id']; st.session_state.page="request_detail"; st.rerun()
            with b2:
                if req['status']=='pending_signoff':
                    if st.button("🎉 Sign Off",key=f"so_{req['id']}",type="primary"):
                        update_status(req['id'],'signoff_received',user['id'],'Sign-off received',{'signoff_by':user['id']}); st.success("Signed off!"); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: ALL REQUESTS
# ══════════════════════════════════════════════════════════════════════════════

def page_all_requests(user):
    if user['role'] not in ['admin','sbd_manager']: st.error("Access denied."); return
    st.markdown('<div class="pg-hdr"><div class="pg-title">All Requests</div><div class="pg-sub">Complete view of all SbD requests</div></div>', unsafe_allow_html=True)
    c1,c2,c3=st.columns([2,2,2])
    with c1: sf=st.selectbox("Status",["All"]+list(STATUS_CFG.keys()))
    with c2: of=st.selectbox("Outcome",["All","no_sbd","sbd_stage1","sbd_stage2","full_sbd"])
    with c3: search=st.text_input("Search","",placeholder="Name or reference...")
    reqs=all_reqs(sf if sf!="All" else None)
    if of!="All": reqs=[r for r in reqs if r.get('sbd_outcome')==of]
    if search: s=search.lower(); reqs=[r for r in reqs if s in r['project_name'].lower() or s in r['ref_number'].lower()]
    st.markdown(f'<div style="font-size:.78rem;color:#64748B;margin-bottom:.875rem;"><strong>{len(reqs)}</strong> requests</div>', unsafe_allow_html=True)
    for req in reqs:
        c1,c2,c3,c4=st.columns([2,4,3,1])
        with c1: st.markdown(f'<span class="ref">{req["ref_number"]}</span>', unsafe_allow_html=True)
        with c2: st.markdown(f"**{req['project_name'][:44]}**"); st.caption(fdates(req['created_at']))
        with c3: st.markdown(sbadge(req['status'])+" "+obadge(req.get('sbd_outcome')), unsafe_allow_html=True)
        with c4:
            if st.button("→",key=f"all_{req['id']}",use_container_width=True):
                st.session_state.selected_req=req['id']; st.session_state.page="request_detail"; st.rerun()
        st.markdown("<div style='border-bottom:1px solid #F8FAFC;margin:.1rem 0;'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: ADMIN — QUESTION BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def page_admin(user):
    if user['role']!='admin': st.error("Admin only."); return
    st.markdown('<div class="pg-hdr"><div class="pg-title">Question Builder</div><div class="pg-sub">Configure assessment questions, conditional logic, and scoring thresholds</div></div>', unsafe_allow_html=True)
    tab1,tab2,tab3=st.tabs(["📝 Questions","🌿 Logic Tree","⚖️ Thresholds"])
    with tab1: _admin_qs()
    with tab2: _admin_tree()
    with tab3: _admin_thresh()

def _admin_qs():
    qs=all_questions_flat()
    c1,c2=st.columns([4,1])
    with c1: st.markdown(f'**{len(qs)}** questions · {sum(1 for q in qs if q["is_active"])} active')
    with c2:
        if st.button("➕ Add",type="primary",use_container_width=True): st.session_state.show_add_q=True
    if st.session_state.get('show_add_q'):
        with st.expander("➕ New Question",expanded=True): _q_form(None,qs)
    st.markdown("---")
    for q in qs:
        opts=json.loads(q['options']) if isinstance(q['options'],str) else q['options']
        wts=json.loads(q['weights']) if isinstance(q['weights'],str) else q['weights']
        ai="🟢" if q['is_active'] else "⬜"
        parent_tag=""
        if q.get('parent_question_id'):
            parent_tag=f'<span style="background:#F5F3FF;color:#6D28D9;font-size:.65rem;padding:.1rem .4rem;border-radius:4px;font-weight:700;">↳ NESTED</span>'
        with st.expander(f"{ai} Q{q['order_index']} · {q['text'][:55]}... · {q['category']}"):
            st.markdown(parent_tag, unsafe_allow_html=True)
            if q.get('parent_question_id') and q.get('trigger_answer'):
                parent=next((x for x in qs if x['id']==q['parent_question_id']),None)
                if parent: st.caption(f"↳ Appears when Q{parent['order_index']} = \"{q['trigger_answer']}\"")
            for opt,wt in zip(opts,wts):
                bw=int((wt/q['max_score']*100)) if q['max_score'] else 0
                bc="#EF4444" if bw>=70 else ("#F59E0B" if bw>=40 else "#10B981")
                st.markdown(f'<div style="display:flex;align-items:center;gap:.75rem;padding:.25rem 0;border-bottom:1px solid #F8FAFC;"><span style="flex:1;font-size:.82rem;">{opt}</span><span style="font-family:monospace;font-size:.78rem;color:{bc};font-weight:700;min-width:40px;">{wt}pt</span><div style="width:80px;background:#F1F5F9;border-radius:999px;height:4px;"><div style="background:{bc};height:4px;border-radius:999px;width:{bw}%;"></div></div></div>', unsafe_allow_html=True)
            cc1,cc2=st.columns([1,2])
            with cc1:
                if st.button("✏️ Edit",key=f"qed_{q['id']}"): st.session_state[f"qe_{q['id']}"]=True
            with cc2:
                lbl="🚫 Deactivate" if q['is_active'] else "✅ Activate"
                if st.button(lbl,key=f"qtg_{q['id']}"):
                    _exe("UPDATE questions SET is_active=? WHERE id=?",(0 if q['is_active'] else 1,q['id'])); st.rerun()
            if st.session_state.get(f"qe_{q['id']}"): _q_form(q,qs)

def _admin_tree():
    qs=[q for q in all_questions_flat() if q['is_active']]
    roots=[q for q in qs if not q.get('parent_question_id')]
    child_map={q['parent_question_id']:[c for c in qs if c['parent_question_id']==q['parent_question_id']] for q in qs if q.get('parent_question_id')}
    # Rebuild properly
    child_map={}
    for q in qs:
        if q.get('parent_question_id'):
            child_map.setdefault(q['parent_question_id'],[]).append(q)

    st.markdown("**Question dependency tree — showing conditional logic:**")
    for q in roots:
        st.markdown(f'<div style="padding:.625rem .875rem;border:1px solid #E2E8F0;border-left:3px solid #3B82F6;border-radius:8px;margin-bottom:.375rem;background:#F8FAFC;"><div style="font-size:.72rem;color:#3B82F6;font-weight:700;">Q{q["order_index"]} · {q["category"]}</div><div style="font-size:.87rem;font-weight:600;">{q["text"]}</div></div>', unsafe_allow_html=True)
        for child in child_map.get(q['id'],[]):
            st.markdown(f'<div style="padding:.5rem .875rem;border:1px solid #E9D5FF;border-left:3px solid #8B5CF6;border-radius:8px;margin-bottom:.375rem;margin-left:2rem;background:#FEFBFF;"><div style="font-size:.68rem;color:#8B5CF6;font-weight:700;">↳ IF "{child.get("trigger_answer","?")}"</div><div style="font-size:.84rem;font-weight:600;">{child["text"]}</div></div>', unsafe_allow_html=True)

def _q_form(q, all_qs):
    is_edit=q is not None; pfx=f"qe_{q['id']}_" if is_edit else "qn_"
    roots=[x for x in all_qs if not x.get('parent_question_id') and (not is_edit or x['id']!=q['id'])]
    parent_opts=[None]+[x['id'] for x in roots]
    parent_lbl={None:'None (top-level question)'}; parent_lbl.update({x['id']:f"Q{x['order_index']}: {x['text'][:50]}..." for x in roots})
    with st.form(f"qform_{pfx}"):
        text=st.text_input("Question text *",value=q['text'] if is_edit else "")
        desc=st.text_input("Description",value=q.get('description','') if is_edit else "")
        hint=st.text_input("Hint (admin-only)",value=q.get('hint','') if is_edit else "")
        cc1,cc2=st.columns(2)
        with cc1: cat=st.text_input("Category",value=q.get('category','General') if is_edit else "General")
        with cc2: order=st.number_input("Order",value=q.get('order_index',0) if is_edit else 0,min_value=0)
        active=st.checkbox("Active",value=bool(q.get('is_active',1)) if is_edit else True)
        st.markdown("**Conditional display** *(optional — show this question only when a parent answer matches)*")
        cur_parent=q.get('parent_question_id') if is_edit else None
        parent_sel=st.selectbox("Parent question",parent_opts,format_func=lambda x:parent_lbl.get(x,'None'),
                                index=parent_opts.index(cur_parent) if cur_parent in parent_opts else 0)
        trigger_ans=""
        if parent_sel:
            pq=next((x for x in all_qs if x['id']==parent_sel),None)
            if pq:
                p_opts=json.loads(pq['options']) if isinstance(pq['options'],str) else pq['options']
                cur_t=q.get('trigger_answer','') if is_edit else ''
                trigger_ans=st.selectbox("Show this question when parent answer is",p_opts,
                                         index=p_opts.index(cur_t) if cur_t in p_opts else 0)
        st.markdown("**Answer options & risk scores**")
        ex_opts=json.loads(q['options']) if is_edit and isinstance(q['options'],str) else (q['options'] if is_edit else ["No","Yes — minor","Yes — moderate","Yes — significant"])
        ex_wts=json.loads(q['weights']) if is_edit and isinstance(q['weights'],str) else (q['weights'] if is_edit else [0,3,6,10])
        num=st.number_input("Number of options",min_value=2,max_value=8,value=len(ex_opts),key=f"nopt_{pfx}")
        new_opts=[]; new_wts=[]
        for i in range(int(num)):
            co,cw=st.columns([4,1])
            with co: new_opts.append(st.text_input(f"Option {i+1}",value=ex_opts[i] if i<len(ex_opts) else "",key=f"o_{pfx}{i}"))
            with cw: new_wts.append(st.number_input("Score",value=int(ex_wts[i]) if i<len(ex_wts) else 0,min_value=0,max_value=100,key=f"w_{pfx}{i}",label_visibility="collapsed"))
        cs,cc=st.columns([1,4])
        with cs: saved=st.form_submit_button("💾 Save",type="primary")
        with cc: cancel=st.form_submit_button("Cancel")
        if saved:
            if not text.strip(): st.error("Question text required.")
            elif not all(o.strip() for o in new_opts): st.error("All options need text.")
            else:
                ms=max(new_wts) if new_wts else 10; now=datetime.now().isoformat()
                if is_edit:
                    c2=_conn()
                    c2.execute("UPDATE questions SET text=?,description=?,hint=?,options=?,weights=?,max_score=?,category=?,parent_question_id=?,trigger_answer=?,order_index=?,is_active=?,updated_at=? WHERE id=?",
                               (text,desc,hint,json.dumps(new_opts),json.dumps(new_wts),ms,cat,
                                parent_sel if parent_sel else None,
                                trigger_ans if parent_sel else None,
                                order,int(active),now,q['id']))
                    c2.commit(); c2.close()
                    st.session_state[f"qe_{q['id']}"]=False
                else:
                    c2=_conn()
                    c2.execute("INSERT INTO questions (text,description,hint,options,weights,max_score,category,parent_question_id,trigger_answer,is_active,order_index,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,1,?,?,?)",
                               (text,desc,hint,json.dumps(new_opts),json.dumps(new_wts),ms,cat,
                                parent_sel if parent_sel else None,
                                trigger_ans if parent_sel else None,
                                order,now,now))
                    c2.commit(); c2.close()
                    st.session_state.show_add_q=False
                st.success("Saved."); st.rerun()
        if cancel:
            if is_edit: st.session_state[f"qe_{q['id']}"]=False
            else: st.session_state.show_add_q=False
            st.rerun()

def _admin_thresh():
    cfg=get_cfg()
    st.markdown('<div class="alert ai">Thresholds are percentage-based. The system calculates what percentage of the maximum possible score a project achieved.</div>', unsafe_allow_html=True)
    with st.form("thresh"):
        t1=st.slider("✅ No SBD Required — scores up to (%)",5,50,int(float(cfg.get('threshold_no_sbd',20))))
        t2=st.slider("⚠️ SBD Stage 1 — scores up to (%)",10,60,int(float(cfg.get('threshold_stage1',40))))
        t3=st.slider("🔶 SBD Stage 2 — scores up to (%)",30,90,int(float(cfg.get('threshold_stage2',65))))
        st.markdown(f'<div class="card card-sm" style="margin-top:.875rem;"><div style="font-weight:700;font-size:.78rem;margin-bottom:.625rem;">Preview</div><div style="display:flex;gap:.5rem;flex-wrap:wrap;"><span style="background:#F9FAFB;color:#374151;padding:.3rem .75rem;border-radius:999px;font-size:.78rem;font-weight:600;border:1px solid #E5E7EB;">0–{t1}% → No SBD</span><span style="background:#FFFBEB;color:#78350F;padding:.3rem .75rem;border-radius:999px;font-size:.78rem;font-weight:600;border:1px solid #FDE68A;">{t1+1}–{t2}% → Stage 1</span><span style="background:#FEF2F2;color:#7F1D1D;padding:.3rem .75rem;border-radius:999px;font-size:.78rem;font-weight:600;border:1px solid #FECACA;">{t2+1}–{t3}% → Stage 2</span><span style="background:#F5F3FF;color:#4C1D95;padding:.3rem .75rem;border-radius:999px;font-size:.78rem;font-weight:600;border:1px solid #DDD6FE;">{t3+1}–100% → Full SBD</span></div></div>', unsafe_allow_html=True)
        if st.form_submit_button("💾 Save",type="primary"):
            if t1<t2<t3: set_cfg('threshold_no_sbd',str(t1)); set_cfg('threshold_stage1',str(t2)); set_cfg('threshold_stage2',str(t3)); st.success("Saved."); st.rerun()
            else: st.error("Thresholds must be in ascending order.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: USER MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def page_users(user):
    if user['role']!='admin': st.error("Admin only."); return
    st.markdown('<div class="pg-hdr"><div class="pg-title">User Management</div><div class="pg-sub">Manage portal users and roles</div></div>', unsafe_allow_html=True)
    tab1,tab2=st.tabs(["👥 All Users","➕ Add User"])
    with tab1:
        users=all_users(); rf=st.selectbox("Filter",["All"]+ROLES)
        if rf!="All": users=[u for u in users if u['role']==rf]
        st.markdown(f"**{len(users)}** users")
        for u in users:
            c1,c2,c3,c4=st.columns([3,2,2,1])
            with c1:
                dept=f" · {u['department']}" if u.get('department') else ''
                st.markdown(f'<div style="display:flex;align-items:center;gap:.625rem;"><div style="width:32px;height:32px;background:linear-gradient(135deg,#3B82F6,#8B5CF6);border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-weight:700;font-size:.82rem;flex-shrink:0;">{u["name"][0]}</div><div><div style="font-weight:600;font-size:.87rem;">{u["name"]}</div><div style="font-size:.72rem;color:#94A3B8;">@{u["username"]}{dept}</div></div></div>', unsafe_allow_html=True)
            with c2: st.caption(u['email'])
            with c3:
                nr=st.selectbox("",ROLES,index=ROLES.index(u['role']) if u['role'] in ROLES else 0,key=f"ur_{u['id']}",format_func=lambda r:ROLE_LABELS.get(r,r),label_visibility="collapsed")
                if nr!=u['role']:
                    if st.button("Save",key=f"usr_{u['id']}"): _exe("UPDATE users SET role=? WHERE id=?",(nr,u['id'])); st.success("Updated."); st.rerun()
            with c4:
                if u['id']!=user['id']:
                    if st.button("🗑",key=f"udd_{u['id']}"): _exe("UPDATE users SET is_active=0 WHERE id=?",(u['id'],)); st.rerun()
            st.markdown("<div style='border-bottom:1px solid #F8FAFC;margin:.2rem 0;'></div>", unsafe_allow_html=True)
    with tab2:
        with st.form("adduser"):
            ca,cb=st.columns(2)
            with ca: name=st.text_input("Full Name *"); username=st.text_input("Username *")
            with cb: email=st.text_input("Email *"); password=st.text_input("Password *",type="password")
            dept=st.text_input("Department"); role=st.selectbox("Role",ROLES,format_func=lambda r:ROLE_LABELS.get(r,r))
            if st.form_submit_button("➕ Create User",type="primary"):
                if not all([name,username,email,password]): st.error("All fields required.")
                elif '@' not in email: st.error("Invalid email.")
                elif len(password)<6: st.error("Min 6 chars for password.")
                else:
                    ok,msg=create_user(username,password,name,email,role,dept)
                    st.success(f"User '{name}' created!") if ok else st.error(msg)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

init_db()
inject_css()

for k,v in [("authenticated",False),("user",None),("page","dashboard")]:
    if k not in st.session_state: st.session_state[k]=v

if not st.session_state.authenticated:
    login_page()
else:
    user=st.session_state.user
    render_sidebar(user)
    page=st.session_state.page
    dispatch={
        "dashboard":       page_dashboard,
        "my_requests":     page_my_requests,
        "new_request":     page_new_request,
        "edit_request":    page_edit_request,
        "assigned":        page_assigned,
        "pending_review":  page_pending_review,
        "assign_resources":page_assign_resources,
        "signoff_queue":   page_signoff,
        "all_requests":    page_all_requests,
        "admin_panel":     page_admin,
        "user_management": page_users,
        "request_detail":  page_request_detail,
    }
    dispatch.get(page, page_dashboard)(user)
