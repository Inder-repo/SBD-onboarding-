import sys, os, sqlite3, json, hashlib
from datetime import datetime
import streamlit as st

st.set_page_config(
    page_title="SbD Portal",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ══════════════════════════════════════════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════════════════════════════════════════

DB_PATH = "sbd_portal.db"

def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
        name TEXT NOT NULL, email TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'project_member',
        department TEXT, created_at TEXT NOT NULL, is_active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL, description TEXT, hint TEXT,
        question_type TEXT DEFAULT 'single_choice',
        options TEXT, weights TEXT, max_score INTEGER DEFAULT 10,
        category TEXT DEFAULT 'General',
        stage_visibility TEXT DEFAULT 'all',
        parent_question_id INTEGER DEFAULT NULL,
        trigger_answer TEXT DEFAULT NULL,
        is_active INTEGER DEFAULT 1, order_index INTEGER DEFAULT 0,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        FOREIGN KEY (parent_question_id) REFERENCES questions(id)
    );
    CREATE TABLE IF NOT EXISTS sbd_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL, value TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ref_number TEXT UNIQUE NOT NULL,
        project_name TEXT NOT NULL, project_description TEXT,
        business_owner TEXT, project_type TEXT, go_live_date TEXT,
        created_by INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending_review',
        sbd_outcome TEXT, total_score REAL DEFAULT 0, max_possible_score REAL DEFAULT 0,
        score_pct REAL DEFAULT 0,
        architect_id INTEGER, architect_url TEXT, architect_notes TEXT,
        engineer_id INTEGER, engineer_notes TEXT,
        assurance_id INTEGER, assurance_notes TEXT,
        signoff_by INTEGER, signoff_notes TEXT,
        is_locked INTEGER DEFAULT 0,
        priority TEXT DEFAULT 'normal',
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        submitted_at TEXT, review_started_at TEXT,
        awaiting_assignment_at TEXT, architect_assigned_at TEXT,
        architect_completed_at TEXT, engineer_assigned_at TEXT,
        engineer_completed_at TEXT, assurance_assigned_at TEXT,
        assurance_completed_at TEXT, pending_signoff_at TEXT,
        signoff_received_at TEXT,
        FOREIGN KEY (created_by) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS request_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL, question_id INTEGER NOT NULL,
        answer TEXT NOT NULL, score REAL DEFAULT 0, created_at TEXT NOT NULL,
        FOREIGN KEY (request_id) REFERENCES requests(id),
        FOREIGN KEY (question_id) REFERENCES questions(id)
    );
    CREATE TABLE IF NOT EXISTS request_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        permission TEXT NOT NULL DEFAULT 'read',
        granted_by INTEGER NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(request_id, user_id),
        FOREIGN KEY (request_id) REFERENCES requests(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL, from_status TEXT, to_status TEXT NOT NULL,
        changed_by INTEGER NOT NULL, notes TEXT, created_at TEXT NOT NULL,
        FOREIGN KEY (request_id) REFERENCES requests(id),
        FOREIGN KEY (changed_by) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        text TEXT NOT NULL, is_internal INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (request_id) REFERENCES requests(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)
    c.commit()
    _seed(c)
    c.close()

def _seed(c):
    now = datetime.now().isoformat()
    users = [
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
    ]
    for un,pw,name,email,role,dept in users:
        ph = hashlib.sha256(pw.encode()).hexdigest()
        try: c.execute("INSERT OR IGNORE INTO users (username,password_hash,name,email,role,department,created_at) VALUES (?,?,?,?,?,?,?)",(un,ph,name,email,role,dept,now))
        except: pass

    # 20 rich questions with nesting, staging, hints
    qs = [
        # ── CORE (always shown) ──────────────────────────────────────────────
        (1, "What type of project is this?",
         "Select the category that best describes the nature of your initiative.",
         "Consider both the technical and business nature of the project.",
         json.dumps(["Internal tooling / process improvement","New internal application","Customer-facing digital product","Platform / infrastructure change","Third-party SaaS onboarding","Data analytics / reporting"]),
         json.dumps([0, 3, 8, 5, 6, 4]), 8, "Project Scope", "all", None, None, 1),

        (2, "Does your project process, store, or transmit personal data (PII)?",
         "Personal data includes names, emails, addresses, health, financial, or any data that identifies an individual.",
         "Think about all data flows, including logs, analytics and third-party integrations.",
         json.dumps(["No personal data involved","Minimal — employee data (internal only)","Moderate — customer names and contact details","Significant — financial or health-related data","Extensive — special category data (biometric, political, etc.)"]),
         json.dumps([0, 2, 5, 8, 10]), 10, "Data & Privacy", "all", None, None, 2),

        (3, "What is the data classification of information handled?",
         "Use your organisation's data classification policy as a guide.",
         None,
         json.dumps(["Public","Internal Use Only","Confidential","Highly Confidential","Restricted / Secret"]),
         json.dumps([0, 1, 4, 7, 10]), 10, "Data & Privacy", "all", None, None, 3),

        (4, "What is the expected scale of users or transactions?",
         "Consider peak usage, not just average.",
         None,
         json.dumps(["< 50 internal users","50–500 users","500–10,000 users","10,000–100,000 users","> 100,000 users / high-volume transactions"]),
         json.dumps([0, 2, 4, 7, 10]), 10, "Exposure & Scale", "all", None, None, 4),

        (5, "Is the project externally accessible (internet-facing)?",
         "Any component reachable from outside the corporate network.",
         None,
         json.dumps(["No — fully internal network only","Internal with VPN access required","Externally accessible but authenticated only","Fully public-facing (no auth required to reach)"]),
         json.dumps([0, 2, 7, 10]), 10, "Exposure & Scale", "all", None, None, 5),

        (6, "Does the project involve third-party integrations or vendor products?",
         "APIs, SaaS platforms, data feeds, or any software not built in-house.",
         None,
         json.dumps(["No third-party integrations","1–2 trusted, well-established vendors","3–5 external systems","Many external / less-vetted third parties"]),
         json.dumps([0, 2, 5, 10]), 10, "Third-party Risk", "all", None, None, 6),

        (7, "What authentication mechanism does the system use?",
         "For all user-facing entry points.",
         None,
         json.dumps(["No authentication required","Username and password only","SSO / SAML with corporate IdP","MFA enforced for all users","Passwordless / hardware token"]),
         json.dumps([10, 7, 3, 1, 0]), 10, "Access Control", "all", None, None, 7),

        (8, "What regulatory or compliance requirements apply?",
         "Select the most stringent applicable framework.",
         "If multiple apply, select the highest.",
         json.dumps(["None identified","Internal policy only","GDPR / data protection legislation","PCI-DSS (payment card data)","HIPAA / clinical data regulation","Multiple strict frameworks (SOX, ISO27001, etc.)"]),
         json.dumps([0, 1, 4, 7, 8, 10]), 10, "Compliance", "all", None, None, 8),

        (9, "Does the project involve financial transactions?",
         "Direct handling of payments, transfers, or financial records.",
         None,
         json.dumps(["No financial data","Financial reporting / read-only","Internal financial workflows","Customer-facing payment processing"]),
         json.dumps([0, 2, 5, 10]), 10, "Financial Risk", "all", None, None, 9),

        (10, "What is the business impact if this system is unavailable for 24 hours?",
         "Consider revenue loss, regulatory breach, and reputational damage.",
         None,
         json.dumps(["Minimal — workarounds exist","Moderate — some business disruption","Significant — major operational impact","Critical — regulatory breach or severe financial loss"]),
         json.dumps([0, 3, 6, 10]), 10, "Business Impact", "all", None, None, 10),

        # ── CONDITIONAL — triggered by parent answers ────────────────────────
        (11, "You indicated external-facing access. How is the application protected?",
         "Describe the perimeter controls in place.",
         "WAF, DDoS protection, and rate limiting are expected for public-facing systems.",
         json.dumps(["No perimeter controls in place","Basic firewall rules only","WAF deployed","WAF + DDoS protection + rate limiting","Full SASE / Zero Trust network access"]),
         json.dumps([10, 7, 4, 2, 0]), 10, "Exposure & Scale", "all", 5, "Externally accessible but authenticated only", 11),

        (12, "You indicated fully public access. Is a Web Application Firewall (WAF) deployed?",
         "Public endpoints without a WAF are high risk.",
         None,
         json.dumps(["No WAF","WAF in detection mode only","WAF in prevention mode","WAF + Bot management + DDoS protection"]),
         json.dumps([10, 6, 3, 0]), 10, "Exposure & Scale", "all", 5, "Fully public-facing (no auth required to reach)", 12),

        (13, "You indicated significant PII. Is data encrypted at rest?",
         "Encryption at rest is a baseline requirement for sensitive personal data.",
         None,
         json.dumps(["No encryption at rest","Partial encryption","Full encryption using managed keys","Full encryption using customer-managed keys (CMK)"]),
         json.dumps([10, 6, 2, 0]), 10, "Data & Privacy", "all", 2, "Significant — financial or health-related data", 13),

        (14, "You indicated special category data. Is data minimisation enforced?",
         "Special category data requires additional safeguards under GDPR Art. 9.",
         None,
         json.dumps(["No — all data retained indefinitely","Retention policies exist but not enforced","Retention policies enforced with automated purge","Strict minimisation with privacy-by-design review completed"]),
         json.dumps([10, 6, 3, 0]), 10, "Data & Privacy", "all", 2, "Extensive — special category data (biometric, political, etc.)", 14),

        (15, "You indicated payment processing. Is PCI-DSS compliance in scope?",
         "Any system that stores, processes or transmits cardholder data must meet PCI-DSS.",
         None,
         json.dumps(["Not assessed","Assessment in progress","PCI-DSS compliant (SAQ)","PCI-DSS compliant (QSA audited)","Tokenisation used — cardholder data never stored"]),
         json.dumps([10, 6, 3, 1, 0]), 10, "Compliance", "all", 9, "Customer-facing payment processing", 15),

        # ── STAGE-GATED — only shown when SBD engagement confirmed ──────────
        (16, "Has a Data Protection Impact Assessment (DPIA) been initiated?",
         "Required for high-risk processing under GDPR Article 35.",
         None,
         json.dumps(["No — not started","Under discussion","In progress","Completed and approved by DPO"]),
         json.dumps([8, 5, 2, 0]), 8, "Compliance", "stage1_plus", None, None, 16),

        (17, "Has a threat model been produced for this system?",
         "STRIDE or equivalent methodology expected for SbD-engaged projects.",
         None,
         json.dumps(["No threat model","Informal / undocumented","Formal threat model (not reviewed)","Formal threat model reviewed and signed off"]),
         json.dumps([8, 5, 3, 0]), 8, "Security Design", "stage1_plus", None, None, 17),

        (18, "Are security requirements documented in the project backlog or design?",
         "Security user stories or non-functional requirements.",
         None,
         json.dumps(["No security requirements documented","Informal notes only","Documented but not tracked","Formal security NFRs in backlog with acceptance criteria"]),
         json.dumps([8, 5, 3, 0]), 8, "Security Design", "stage1_plus", None, None, 18),

        (19, "Has penetration testing been scoped or completed?",
         "Required for Stage 2 and Full SBD engagements.",
         None,
         json.dumps(["Not planned","Planned for future release","Scoped and scheduled","Completed — findings remediated","Completed — findings accepted with risk sign-off"]),
         json.dumps([8, 5, 3, 0, 1]), 8, "Security Testing", "stage2_plus", None, None, 19),

        (20, "Is there a documented incident response plan for this system?",
         "Includes detection, containment, escalation and recovery procedures.",
         None,
         json.dumps(["No plan","Generic company plan referenced","System-specific plan drafted","Tested plan with defined RTO/RPO"]),
         json.dumps([8, 5, 3, 0]), 8, "Resilience", "stage2_plus", None, None, 20),
    ]

    for (order,text,desc,hint,opts,wts,max_s,cat,stage_vis,parent_id,trigger_ans,qorder) in qs:
        try:
            c.execute("""INSERT OR IGNORE INTO questions
                (text,description,hint,question_type,options,weights,max_score,category,
                 stage_visibility,parent_question_id,trigger_answer,is_active,order_index,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?,?,?)""",
                (text,desc,hint,'single_choice',opts,wts,max_s,cat,stage_vis,parent_id,trigger_ans,qorder,now,now))
        except: pass

    configs = [
        ("threshold_no_sbd","20"),("threshold_stage1","40"),
        ("threshold_stage2","65"),("threshold_full_sbd","100"),
        ("org_name","Acme Corporation"),("portal_version","2.0"),
    ]
    for k,v in configs:
        try: c.execute("INSERT OR IGNORE INTO sbd_config (key,value,updated_at) VALUES (?,?,?)",(k,v,now))
        except: pass
    c.commit()

# ── DB helpers ──────────────────────────────────────────────────────────────

def hp(p): return hashlib.sha256(p.encode()).hexdigest()

def qry(sql, params=(), one=False):
    c = db(); r = c.execute(sql, params)
    result = r.fetchone() if one else r.fetchall()
    c.close()
    return (dict(result) if result else None) if one else [dict(x) for x in result]

def exe(sql, params=()):
    c = db(); c.execute(sql, params); c.commit(); c.close()

def exe_last(sql, params=()):
    c = db(); c.execute(sql, params); lid = c.execute("SELECT last_insert_rowid()").fetchone()[0]; c.commit(); c.close(); return lid

def get_user(username): return qry("SELECT * FROM users WHERE username=? AND is_active=1",(username,),one=True)
def get_user_id(uid): return qry("SELECT * FROM users WHERE id=?",(uid,),one=True)
def all_users(role=None):
    if role: return qry("SELECT * FROM users WHERE role=? AND is_active=1 ORDER BY name",(role,))
    return qry("SELECT * FROM users WHERE is_active=1 ORDER BY name")

def active_questions(stage_filter=None):
    qs = qry("SELECT * FROM questions WHERE is_active=1 ORDER BY order_index,id")
    if stage_filter:
        allowed = {'all', stage_filter}
        qs = [q for q in qs if q['stage_visibility'] in allowed]
    return qs

def all_questions(): return qry("SELECT * FROM questions ORDER BY order_index,id")

def get_cfg(): return {r['key']:r['value'] for r in qry("SELECT * FROM sbd_config")}
def set_cfg(k,v): exe("INSERT OR REPLACE INTO sbd_config (key,value,updated_at) VALUES (?,?,?)",(k,v,datetime.now().isoformat()))

def new_ref():
    count = qry("SELECT COUNT(*) as c FROM requests",one=True)['c']
    return f"SBD-{datetime.now().year}-{str(count+1).zfill(4)}"

def create_request(name,desc,biz_owner,proj_type,go_live,uid):
    now=datetime.now().isoformat(); ref=new_ref()
    rid=exe_last("INSERT INTO requests (ref_number,project_name,project_description,business_owner,project_type,go_live_date,created_by,status,created_at,updated_at,submitted_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (ref,name,desc,biz_owner,proj_type,go_live,uid,'pending_review',now,now,now))
    exe("INSERT INTO status_history (request_id,from_status,to_status,changed_by,notes,created_at) VALUES (?,?,?,?,?,?)",
        (rid,None,'pending_review',uid,'Request submitted',now))
    return rid,ref

def save_answers(rid, answers_dict):
    now=datetime.now().isoformat()
    exe("DELETE FROM request_answers WHERE request_id=?",(rid,))
    total=0; max_total=0
    qs_map = {str(q['id']):q for q in all_questions()}
    for qid,ans_data in answers_dict.items():
        exe("INSERT INTO request_answers (request_id,question_id,answer,score,created_at) VALUES (?,?,?,?,?)",
            (rid,qid,ans_data['answer'],ans_data['score'],now))
        total+=ans_data['score']
        q=qs_map.get(str(qid))
        if q: max_total+=q['max_score']
    pct=(total/max_total*100) if max_total>0 else 0
    exe("UPDATE requests SET total_score=?,max_possible_score=?,score_pct=?,updated_at=? WHERE id=?",(total,max_total,pct,now,rid))
    return total,max_total,pct

def sbd_outcome(pct, cfg):
    t1=float(cfg.get('threshold_no_sbd',20)); t2=float(cfg.get('threshold_stage1',40)); t3=float(cfg.get('threshold_stage2',65))
    if pct<=t1: return "no_sbd"
    elif pct<=t2: return "sbd_stage1"
    elif pct<=t3: return "sbd_stage2"
    else: return "full_sbd"

def finalize(rid, outcome, total, max_s, pct, uid):
    now=datetime.now().isoformat()
    ns="no_sbd_needed" if outcome=="no_sbd" else "awaiting_assignment"
    old=qry("SELECT status FROM requests WHERE id=?",(rid,),one=True)
    exe(f"UPDATE requests SET status=?,sbd_outcome=?,total_score=?,max_possible_score=?,score_pct=?,updated_at=?,{'awaiting_assignment_at=?,' if ns=='awaiting_assignment' else ''}updated_at=? WHERE id=?",
        ([ns,outcome,total,max_s,pct,now]+([now] if ns=='awaiting_assignment' else [])+[now,rid]))
    # Simpler approach:
    c2=db()
    c2.execute("UPDATE requests SET status=?,sbd_outcome=?,total_score=?,max_possible_score=?,score_pct=?,updated_at=? WHERE id=?",(ns,outcome,total,max_s,pct,now,rid))
    if ns=='awaiting_assignment': c2.execute("UPDATE requests SET awaiting_assignment_at=? WHERE id=?",(now,rid))
    c2.execute("INSERT INTO status_history (request_id,from_status,to_status,changed_by,notes,created_at) VALUES (?,?,?,?,?,?)",(rid,old['status'] if old else None,ns,uid,f'Outcome: {outcome} | Score: {pct:.1f}%',now))
    c2.commit(); c2.close()

def update_status(rid, new_s, uid, notes=None, extras=None):
    now=datetime.now().isoformat()
    old=qry("SELECT status FROM requests WHERE id=?",(rid,),one=True)
    ts={'pending_review':'review_started_at','awaiting_assignment':'awaiting_assignment_at',
        'architect_assigned':'architect_assigned_at','architect_completed':'architect_completed_at',
        'engineer_assigned':'engineer_assigned_at','engineer_completed':'engineer_completed_at',
        'assurance_assigned':'assurance_assigned_at','assurance_completed':'assurance_completed_at',
        'pending_signoff':'pending_signoff_at','signoff_received':'signoff_received_at'}
    c2=db()
    c2.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?",(new_s,now,rid))
    if new_s in ts: c2.execute(f"UPDATE requests SET {ts[new_s]}=? WHERE id=?",(now,rid))
    if new_s=='signoff_received': c2.execute("UPDATE requests SET is_locked=1 WHERE id=?",(rid,))
    if extras:
        for k,v in extras.items(): c2.execute(f"UPDATE requests SET {k}=? WHERE id=?",(v,rid))
    c2.execute("INSERT INTO status_history (request_id,from_status,to_status,changed_by,notes,created_at) VALUES (?,?,?,?,?,?)",
               (rid,old['status'] if old else None,new_s,uid,notes,now))
    c2.commit(); c2.close()

def get_req(rid): return qry("SELECT * FROM requests WHERE id=?",(rid,),one=True)

def req_answers(rid):
    return qry("""SELECT ra.*,q.text as qtxt,q.category,q.options,q.weights,q.hint,q.description as qdesc
        FROM request_answers ra JOIN questions q ON ra.question_id=q.id WHERE ra.request_id=? ORDER BY q.order_index""",(rid,))

def user_reqs(uid):
    return qry("""SELECT DISTINCT r.* FROM requests r
        LEFT JOIN request_permissions rp ON r.id=rp.request_id AND rp.user_id=?
        WHERE r.created_by=? OR rp.user_id=? ORDER BY r.created_at DESC""",(uid,uid,uid))

def assigned_reqs(uid, field):
    return qry(f"SELECT * FROM requests WHERE {field}=? ORDER BY created_at DESC",(uid,))

def all_reqs(status=None):
    if status: return qry("SELECT * FROM requests WHERE status=? ORDER BY created_at DESC",(status,))
    return qry("SELECT * FROM requests ORDER BY created_at DESC")

def reqs_by_status(sl):
    ph=','.join('?'*len(sl))
    return qry(f"SELECT * FROM requests WHERE status IN ({ph}) ORDER BY created_at DESC",sl)

def status_hist(rid):
    return qry("""SELECT sh.*,u.name as by_name FROM status_history sh
        JOIN users u ON sh.changed_by=u.id WHERE sh.request_id=? ORDER BY sh.created_at ASC""",(rid,))

def add_perm(rid,uid,perm,by): exe("INSERT OR REPLACE INTO request_permissions (request_id,user_id,permission,granted_by,created_at) VALUES (?,?,?,?,?)",(rid,uid,perm,by,datetime.now().isoformat()))
def get_perms(rid): return qry("SELECT rp.*,u.name,u.email,u.username FROM request_permissions rp JOIN users u ON rp.user_id=u.id WHERE rp.request_id=?",(rid,))
def del_perm(rid,uid): exe("DELETE FROM request_permissions WHERE request_id=? AND user_id=?",(rid,uid))

def can_access(rid,uid,write=False):
    r=qry("SELECT created_by FROM requests WHERE id=?",(rid,),one=True)
    if r and r['created_by']==uid: return True
    p=qry("SELECT permission FROM request_permissions WHERE request_id=? AND user_id=?",(rid,uid),one=True)
    if p: return p['permission']=='write' if write else True
    return False

def is_assigned(rid,uid):
    r=get_req(rid)
    return r and uid in [r.get('architect_id'),r.get('engineer_id'),r.get('assurance_id')]

def add_comment(rid,uid,text,internal=False): exe("INSERT INTO comments (request_id,user_id,text,is_internal,created_at) VALUES (?,?,?,?,?)",(rid,uid,text,int(internal),datetime.now().isoformat()))
def get_comments(rid,show_internal=False):
    if show_internal: return qry("SELECT c.*,u.name,u.role FROM comments c JOIN users u ON c.user_id=u.id WHERE c.request_id=? ORDER BY c.created_at DESC",(rid,))
    return qry("SELECT c.*,u.name,u.role FROM comments c JOIN users u ON c.user_id=u.id WHERE c.request_id=? AND c.is_internal=0 ORDER BY c.created_at DESC",(rid,))

def get_stats():
    s={}
    s['total']=qry("SELECT COUNT(*) as c FROM requests",one=True)['c']
    for k,v in [('pending_review',"status='pending_review'"),('awaiting',"status='awaiting_assignment'"),
                ('in_progress',"status IN ('architect_assigned','architect_completed','engineer_assigned','engineer_completed','assurance_assigned','assurance_completed')"),
                ('pending_signoff',"status='pending_signoff'"),('complete',"status='signoff_received'"),('no_sbd',"status='no_sbd_needed'")]:
        s[k]=qry(f"SELECT COUNT(*) as c FROM requests WHERE {v}",one=True)['c']
    for o in ['no_sbd','sbd_stage1','sbd_stage2','full_sbd']:
        s[f'o_{o}']=qry("SELECT COUNT(*) as c FROM requests WHERE sbd_outcome=?",(o,),one=True)['c']
    return s

def create_user(un,pw,name,email,role,dept=""):
    try: exe("INSERT INTO users (username,password_hash,name,email,role,department,created_at) VALUES (?,?,?,?,?,?,?)",(un,hp(pw),name,email,role,dept,datetime.now().isoformat())); return True,"OK"
    except sqlite3.IntegrityError: return False,"Username exists"

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG & CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

STATUS_CFG = {
    'pending_review':      ('Pending Review',      '#F59E0B','#FEF3C7','⏳'),
    'no_sbd_needed':       ('No SBD Required',     '#6B7280','#F3F4F6','—'),
    'awaiting_assignment': ('Awaiting Assignment', '#3B82F6','#EFF6FF','👤'),
    'architect_assigned':  ('Architect Assigned',  '#8B5CF6','#F5F3FF','🏗'),
    'architect_completed': ('Architecture Done',   '#10B981','#ECFDF5','✓'),
    'engineer_assigned':   ('Engineer Assigned',   '#F97316','#FFF7ED','⚙'),
    'engineer_completed':  ('Engineering Done',    '#10B981','#ECFDF5','✓'),
    'assurance_assigned':  ('Assurance Assigned',  '#EC4899','#FDF2F8','🔍'),
    'assurance_completed': ('Assurance Done',      '#10B981','#ECFDF5','✓'),
    'pending_signoff':     ('Pending Sign-off',    '#6366F1','#EEF2FF','✍'),
    'signoff_received':    ('Signed Off',          '#059669','#ECFDF5','🎉'),
}

OUTCOME_CFG = {
    'no_sbd':    ('No SBD Required', '#6B7280','#F9FAFB','#E5E7EB','✅','Low risk — no formal SBD engagement required.'),
    'sbd_stage1':('SBD Stage 1',     '#D97706','#FFFBEB','#FDE68A','⚠️','Light-touch engagement: architecture review and sign-off.'),
    'sbd_stage2':('SBD Stage 2',     '#DC2626','#FEF2F2','#FECACA','🔶','Standard engagement: architecture, engineering, and assurance.'),
    'full_sbd':  ('Full SBD',        '#7C3AED','#F5F3FF','#DDD6FE','🔴','Full engagement: all phases including penetration testing.'),
}

PIPELINE = [
    ('pending_review','Submitted','📋'),('awaiting_assignment','Assessed','📊'),
    ('architect_assigned','Architect','🏗'),('architect_completed','Arch ✓','✅'),
    ('engineer_assigned','Engineer','⚙'),('engineer_completed','Eng ✓','✅'),
    ('assurance_assigned','Assurance','🔍'),('assurance_completed','Assur ✓','✅'),
    ('pending_signoff','Sign-off','✍'),('signoff_received','Complete','🎉'),
]

ROLES = ['project_member','security_architect','security_engineer','assurance','sbd_manager','admin']
ROLE_LABELS = {'project_member':'Project Member','security_architect':'Security Architect',
               'security_engineer':'Security Engineer','assurance':'Assurance Analyst',
               'sbd_manager':'SbD Programme Manager','admin':'System Administrator'}

def fdate(s):
    if not s: return "—"
    try: return datetime.fromisoformat(s).strftime("%d %b %Y %H:%M")
    except: return s

def fdate_short(s):
    if not s: return "—"
    try: return datetime.fromisoformat(s).strftime("%d %b %Y")
    except: return s

# ══════════════════════════════════════════════════════════════════════════════
# STYLES — Enterprise grade
# ══════════════════════════════════════════════════════════════════════════════

def inject_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

:root {
  --navy: #0A0F1E;
  --navy2: #111827;
  --navy3: #1F2937;
  --accent: #3B82F6;
  --accent2: #60A5FA;
  --success: #10B981;
  --warning: #F59E0B;
  --danger: #EF4444;
  --purple: #8B5CF6;
  --surface: #FFFFFF;
  --surface2: #F8FAFC;
  --surface3: #F1F5F9;
  --border: #E2E8F0;
  --border2: #CBD5E1;
  --text: #0F172A;
  --text2: #334155;
  --text3: #64748B;
  --text4: #94A3B8;
  --mono: 'JetBrains Mono', monospace;
  --sans: 'Inter', sans-serif;
  --radius: 10px;
  --radius2: 6px;
  --shadow: 0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.06);
  --shadow2: 0 4px 12px rgba(0,0,0,.1), 0 2px 4px rgba(0,0,0,.06);
}

*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] { font-family: var(--sans) !important; }
#MainMenu, footer, header { visibility: hidden; }

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {
  background: var(--navy) !important;
  border-right: 1px solid rgba(255,255,255,.06) !important;
}
[data-testid="stSidebar"] * { color: #CBD5E1 !important; }
[data-testid="stSidebarContent"] { padding: 0 !important; }

.sb-brand {
  padding: 1.5rem 1.25rem 1.25rem;
  border-bottom: 1px solid rgba(255,255,255,.06);
  display: flex; align-items: center; gap: .75rem;
}
.sb-brand-icon {
  width: 38px; height: 38px;
  background: linear-gradient(135deg, var(--accent), var(--purple));
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem; flex-shrink: 0;
}
.sb-brand-text { font-weight: 700; font-size: .95rem; color: #F1F5F9 !important; letter-spacing: -.01em; }
.sb-brand-sub { font-size: .68rem; color: #64748B !important; text-transform: uppercase; letter-spacing: .08em; }

.sb-user {
  margin: .75rem; padding: .875rem 1rem;
  background: rgba(255,255,255,.04);
  border: 1px solid rgba(255,255,255,.06);
  border-radius: var(--radius);
  display: flex; align-items: center; gap: .75rem;
}
.sb-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  background: linear-gradient(135deg, var(--accent), var(--purple));
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: .9rem; color: white !important; flex-shrink: 0;
}
.sb-uname { font-weight: 600; font-size: .85rem; color: #F1F5F9 !important; }
.sb-urole { font-size: .7rem; color: #64748B !important; text-transform: uppercase; letter-spacing: .06em; }

.sb-section {
  padding: .375rem 1.25rem .25rem;
  font-size: .65rem; font-weight: 700; color: #475569 !important;
  text-transform: uppercase; letter-spacing: .1em; margin-top: .5rem;
}

[data-testid="stSidebar"] .stButton button {
  background: transparent !important;
  border: none !important; border-radius: var(--radius2) !important;
  color: #94A3B8 !important;
  padding: .45rem 1rem !important;
  font-size: .83rem !important; font-weight: 500 !important;
  text-align: left !important;
  transition: background .15s, color .15s !important;
  margin: 1px .5rem !important;
  width: calc(100% - 1rem) !important;
}
[data-testid="stSidebar"] .stButton button:hover {
  background: rgba(255,255,255,.06) !important; color: #F1F5F9 !important;
}
[data-testid="stSidebar"] .stButton button[kind="primary"] {
  background: rgba(59,130,246,.2) !important;
  color: #93C5FD !important;
  border-left: 2px solid #3B82F6 !important;
}

/* ── MAIN ── */
.main .block-container {
  padding: 1.75rem 2.25rem !important;
  max-width: 1360px !important;
}

/* ── PAGE HEADER ── */
.pg-header {
  margin-bottom: 1.75rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid var(--border);
  display: flex; justify-content: space-between; align-items: flex-start;
}
.pg-title {
  font-size: 1.5rem; font-weight: 800;
  color: var(--text); letter-spacing: -.025em; margin: 0;
}
.pg-sub { color: var(--text3); font-size: .85rem; margin-top: .2rem; }

/* ── CARDS ── */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.5rem;
  box-shadow: var(--shadow);
  transition: box-shadow .2s;
}
.card:hover { box-shadow: var(--shadow2); }
.card-sm { padding: 1rem 1.25rem; }
.card-flush { padding: 0; overflow: hidden; }

/* ── STAT CARDS ── */
.stat-grid { display: grid; grid-template-columns: repeat(6,1fr); gap: 1rem; margin-bottom: 1.75rem; }
.stat-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1.25rem;
  box-shadow: var(--shadow);
}
.stat-icon { font-size: 1.4rem; margin-bottom: .5rem; }
.stat-val { font-family: var(--mono); font-size: 2rem; font-weight: 700; color: var(--text); line-height: 1; }
.stat-lbl { font-size: .72rem; color: var(--text3); text-transform: uppercase; letter-spacing: .06em; margin-top: .25rem; }

/* ── BADGES ── */
.badge {
  display: inline-flex; align-items: center; gap: .3rem;
  padding: .2rem .65rem; border-radius: 999px;
  font-size: .7rem; font-weight: 600; text-transform: uppercase; letter-spacing: .04em;
  white-space: nowrap;
}
.badge-dot {
  width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
}

/* ── REF ── */
.ref {
  font-family: var(--mono); font-size: .78rem; font-weight: 600;
  color: var(--accent); background: #EFF6FF;
  padding: .18rem .55rem; border-radius: var(--radius2);
  letter-spacing: .02em;
}

/* ── PIPELINE ── */
.pipeline { display: flex; align-items: center; margin: .75rem 0; overflow-x: auto; }
.pipe-step { display: flex; flex-direction: column; align-items: center; flex: 1; min-width: 72px; }
.pipe-node {
  width: 30px; height: 30px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: .75rem; z-index: 1;
  transition: all .2s;
}
.pipe-node-todo { background: var(--surface3); border: 2px solid var(--border2); color: var(--text4); }
.pipe-node-done { background: var(--success); border: 2px solid var(--success); color: white; }
.pipe-node-active { background: var(--accent); border: 2px solid var(--accent); color: white; box-shadow: 0 0 0 4px rgba(59,130,246,.2); }
.pipe-lbl { font-size: .6rem; text-align: center; margin-top: .3rem; color: var(--text3); text-transform: uppercase; letter-spacing: .04em; max-width: 64px; line-height: 1.3; }
.pipe-line { flex: 1; height: 2px; margin-bottom: .9rem; transition: background .2s; }
.pipe-line-todo { background: var(--border); }
.pipe-line-done { background: var(--success); }

/* ── TIMELINE ── */
.tl { position: relative; padding-left: 1.75rem; }
.tl::before { content: ''; position: absolute; left: .45rem; top: 4px; bottom: 4px; width: 2px; background: var(--border); border-radius: 2px; }
.tl-item { position: relative; margin-bottom: 1.25rem; }
.tl-dot { position: absolute; left: -1.5rem; top: .2rem; width: 12px; height: 12px; border-radius: 50%; border: 2px solid white; }
.tl-dot-done { background: var(--success); box-shadow: 0 0 0 2px var(--success); }
.tl-dot-now { background: var(--accent); box-shadow: 0 0 0 3px rgba(59,130,246,.3); }
.tl-dot-todo { background: var(--border2); box-shadow: 0 0 0 2px var(--border2); }
.tl-title { font-size: .85rem; font-weight: 600; color: var(--text); }
.tl-meta { font-size: .75rem; color: var(--text3); margin-top: .1rem; }
.tl-note { font-size: .78rem; color: var(--text2); font-style: italic; margin-top: .2rem; }

/* ── QUESTION CARDS ── */
.q-card {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: var(--radius);
  padding: 1rem 1.25rem;
  margin-bottom: 1rem;
}
.q-card.nested {
  border-left-color: var(--purple);
  background: #FEFBFF;
  margin-left: 1.5rem;
}
.q-card.stage-gated { border-left-color: var(--warning); background: #FFFBF0; }
.q-num { font-family: var(--mono); font-size: .7rem; color: var(--accent); font-weight: 700; margin-bottom: .2rem; }
.q-num.nested { color: var(--purple); }
.q-text { font-weight: 600; font-size: .92rem; color: var(--text); margin-bottom: .2rem; }
.q-desc { font-size: .8rem; color: var(--text3); margin-bottom: .25rem; }
.q-hint { font-size: .75rem; color: var(--text4); font-style: italic; }

/* ── OUTCOME BANNERS ── */
.outcome-banner {
  border-radius: var(--radius);
  padding: 1.25rem 1.5rem;
  display: flex; align-items: flex-start; gap: 1rem;
  border: 1px solid;
}
.outcome-icon { font-size: 2rem; flex-shrink: 0; margin-top: .1rem; }
.outcome-title { font-weight: 700; font-size: 1.05rem; }
.outcome-desc { font-size: .82rem; margin-top: .2rem; }

/* ── SCORE RING (CSS only) ── */
.score-ring-wrap { display: flex; flex-direction: column; align-items: center; padding: 1.25rem 0; }
.score-ring {
  width: 100px; height: 100px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--mono); font-size: 1.5rem; font-weight: 700;
  margin-bottom: .75rem;
}
.score-lbl { font-size: .72rem; color: var(--text3); text-transform: uppercase; letter-spacing: .06em; }

/* ── FORM ELEMENTS ── */
.stTextInput input, .stTextArea textarea, .stSelectbox select {
  font-family: var(--sans) !important;
  border-radius: var(--radius2) !important;
  border: 1px solid var(--border2) !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px rgba(59,130,246,.1) !important;
}

/* ── TABLES ── */
.tbl { width: 100%; border-collapse: collapse; font-size: .84rem; }
.tbl th {
  background: var(--surface3); padding: .6rem 1rem;
  text-align: left; font-weight: 600; font-size: .7rem;
  color: var(--text3); text-transform: uppercase; letter-spacing: .06em;
  border-bottom: 2px solid var(--border);
}
.tbl td { padding: .75rem 1rem; border-bottom: 1px solid var(--border); color: var(--text2); }
.tbl tr:last-child td { border-bottom: none; }
.tbl tr:hover td { background: var(--surface2); }

/* ── LOCK BANNER ── */
.lock-banner {
  background: var(--navy2); color: #F1F5F9;
  border-radius: var(--radius); padding: .75rem 1.25rem;
  display: flex; align-items: center; gap: .75rem;
  font-weight: 600; font-size: .88rem; margin-bottom: 1rem;
}

/* ── ALERTS ── */
.alert { padding: .75rem 1rem; border-radius: var(--radius2); margin: .5rem 0; font-size: .84rem; }
.alert-info { background: #EFF6FF; border: 1px solid #BFDBFE; color: #1E40AF; }
.alert-warn { background: #FFFBEB; border: 1px solid #FDE68A; color: #92400E; }
.alert-success { background: #ECFDF5; border: 1px solid #A7F3D0; color: #065F46; }
.alert-danger { background: #FEF2F2; border: 1px solid #FECACA; color: #991B1B; }

/* ── TABS ── */
.stTabs [data-baseweb="tab-list"] {
  border-bottom: 2px solid var(--border) !important;
  gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
  font-size: .83rem !important; font-weight: 500 !important;
  padding: .6rem 1.25rem !important;
  border-bottom: 2px solid transparent !important;
  margin-bottom: -2px !important;
}
.stTabs [aria-selected="true"] {
  border-bottom-color: var(--accent) !important;
  color: var(--accent) !important;
  font-weight: 600 !important;
}

/* ── PRIORITY TAGS ── */
.priority-high { color: #DC2626; background: #FEF2F2; padding: .15rem .5rem; border-radius: 4px; font-size: .72rem; font-weight: 700; }
.priority-normal { color: #2563EB; background: #EFF6FF; padding: .15rem .5rem; border-radius: 4px; font-size: .72rem; font-weight: 700; }
.priority-low { color: #059669; background: #ECFDF5; padding: .15rem .5rem; border-radius: 4px; font-size: .72rem; font-weight: 700; }

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 3px; }

/* ── EXPANDER ── */
.streamlit-expanderHeader { font-weight: 600 !important; font-size: .88rem !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS
# ══════════════════════════════════════════════════════════════════════════════

def status_badge(s):
    if s not in STATUS_CFG: return f'<span class="badge" style="background:#F3F4F6;color:#6B7280;">{s}</span>'
    label,color,bg,_ = STATUS_CFG[s]
    return f'<span class="badge" style="background:{bg};color:{color};"><span class="badge-dot" style="background:{color};"></span>{label}</span>'

def outcome_badge(o):
    if not o or o not in OUTCOME_CFG: return ''
    label,color,bg,_,icon,_ = OUTCOME_CFG[o]
    return f'<span class="badge" style="background:{bg};color:{color};">{icon} {label}</span>'

def render_pipeline(current):
    try: ci = next(i for i,s in enumerate(PIPELINE) if s[0]==current)
    except: ci = -1
    html = '<div class="pipeline">'
    for i,(key,label,icon) in enumerate(PIPELINE):
        if i < ci:   nc,lc = 'pipe-node-done','pipe-line-done'; ni='✓'
        elif i == ci: nc,lc = 'pipe-node-active','pipe-line-done'; ni=icon
        else:         nc,lc = 'pipe-node-todo','pipe-line-todo'; ni=''
        if i>0: html+=f'<div class="pipe-line {lc if i<=ci else "pipe-line-todo"}"></div>'
        html+=f'<div class="pipe-step"><div class="pipe-node {nc}">{ni}</div><div class="pipe-lbl">{label}</div></div>'
    return html+'</div>'

def score_ring(pct, show_score=True):
    if pct >= 65:   color='#DC2626'; bg='#FEF2F2'
    elif pct >= 40: color='#D97706'; bg='#FFFBEB'
    elif pct >= 20: color='#F59E0B'; bg='#FEF9C3'
    else:           color='#10B981'; bg='#ECFDF5'
    val = f"{pct:.0f}%" if show_score else "?"
    return f'''<div class="score-ring-wrap">
      <div class="score-ring" style="background:{bg};color:{color};border:4px solid {color};">{val}</div>
      <div class="score-lbl">Risk Score</div>
    </div>'''

def phase_timeline(req):
    phases = [
        ('submitted_at','Submitted','📋'),
        ('awaiting_assignment_at','Assessment Complete','📊'),
        ('architect_assigned_at','Architect Assigned','🏗'),
        ('architect_completed_at','Architecture Done','✅'),
        ('engineer_assigned_at','Engineer Assigned','⚙'),
        ('engineer_completed_at','Engineering Done','✅'),
        ('assurance_assigned_at','Assurance Assigned','🔍'),
        ('assurance_completed_at','Assurance Done','✅'),
        ('pending_signoff_at','Pending Sign-off','✍'),
        ('signoff_received_at','Signed Off','🎉'),
    ]
    html='<div class="tl">'
    current_reached=False
    for field,label,icon in phases:
        dt=req.get(field)
        if dt: cls='tl-dot-done'
        elif not current_reached: cls='tl-dot-now'; current_reached=True
        else: cls='tl-dot-todo'
        html+=f'''<div class="tl-item">
          <div class="tl-dot {cls}"></div>
          <div class="tl-title">{icon} {label}</div>
          <div class="tl-meta">{fdate(dt) if dt else '<span style="color:#CBD5E1">Pending</span>'}</div>
        </div>'''
    return html+'</div>'

# ══════════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════════

def login_page():
    cfg = get_cfg()
    org = cfg.get('org_name','Your Organisation')
    col1,col2,col3 = st.columns([1,1.1,1])
    with col2:
        st.markdown(f"""
        <div style="text-align:center;padding:3rem 0 2rem;">
          <div style="width:64px;height:64px;background:linear-gradient(135deg,#3B82F6,#8B5CF6);
               border-radius:18px;display:inline-flex;align-items:center;justify-content:center;
               font-size:2rem;margin-bottom:1.25rem;box-shadow:0 8px 24px rgba(59,130,246,.3);">🔐</div>
          <div style="font-size:1.6rem;font-weight:800;color:#0F172A;letter-spacing:-.03em;">SbD Portal</div>
          <div style="font-size:.82rem;color:#64748B;margin-top:.3rem;">{org} · Secure by Design Programme</div>
        </div>
        """, unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="card" style="padding:2rem;">', unsafe_allow_html=True)
            st.markdown('<div style="font-weight:700;font-size:.95rem;margin-bottom:1.25rem;color:#0F172A;">Sign in to your account</div>', unsafe_allow_html=True)
            username = st.text_input("Username", placeholder="Enter your username", label_visibility="collapsed")
            password = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed")
            st.markdown('<div style="margin-top:.25rem;"></div>', unsafe_allow_html=True)
            if st.button("Sign In →", use_container_width=True, type="primary"):
                u = get_user(username)
                if u and u['password_hash'] == hp(password):
                    st.session_state.authenticated = True
                    st.session_state.user = u
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("""<div style="text-align:center;margin-top:1rem;color:#94A3B8;font-size:.78rem;line-height:1.8;">
          <strong style="color:#64748B;">Demo accounts</strong><br>
          admin / admin123 &nbsp;·&nbsp; sbd_manager / manager123<br>
          architect1 / arch123 &nbsp;·&nbsp; user1 / user123
        </div>""", unsafe_allow_html=True)

def logout():
    for k in list(st.session_state.keys()): del st.session_state[k]

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

def render_sidebar(user):
    with st.sidebar:
        st.markdown(f"""<div class="sb-brand">
          <div class="sb-brand-icon">🔐</div>
          <div><div class="sb-brand-text">SbD Portal</div>
          <div class="sb-brand-sub">Security by Design</div></div>
        </div>""", unsafe_allow_html=True)

        st.markdown(f"""<div class="sb-user">
          <div class="sb-avatar">{user['name'][0].upper()}</div>
          <div><div class="sb-uname">{user['name']}</div>
          <div class="sb-urole">{ROLE_LABELS.get(user['role'],user['role'])}</div></div>
        </div>""", unsafe_allow_html=True)

        st.markdown('<div class="sb-section">Navigation</div>', unsafe_allow_html=True)
        nav = [("🏠","Dashboard","dashboard"),("📋","My Requests","my_requests"),("➕","New Request","new_request")]

        role = user['role']
        if role in ['security_architect','security_engineer','assurance']:
            nav.append(("📌","Assigned to Me","assigned"))
        if role in ['sbd_manager','admin']:
            st.markdown('<div class="sb-section">Management</div>', unsafe_allow_html=True)
            nav += [("📥","Review Queue","pending_review"),("👥","Assign Resources","assign_resources"),
                    ("✅","Sign-Off Queue","signoff_queue"),("📊","All Requests","all_requests")]
        if role == 'admin':
            st.markdown('<div class="sb-section">Administration</div>', unsafe_allow_html=True)
            nav += [("⚙️","Question Builder","admin_panel"),("👤","User Management","user_management")]

        for icon,label,pk in nav:
            active = st.session_state.get('page') == pk
            if st.button(f"{icon}  {label}", key=f"nav_{pk}", use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.page = pk; st.rerun()

        st.markdown("---")
        if st.button("🚪  Sign Out", use_container_width=True):
            logout(); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def page_dashboard(user):
    cfg = get_cfg()
    stats = get_stats()
    role = user['role']

    st.markdown(f"""<div class="pg-header">
      <div><div class="pg-title">Welcome back, {user['name'].split()[0]}</div>
      <div class="pg-sub">{cfg.get('org_name','')} · Secure by Design Programme Dashboard</div></div>
    </div>""", unsafe_allow_html=True)

    # Stat row
    stat_items = [
        ("📋","Total",stats['total'],"#3B82F6"),
        ("⏳","Pending Review",stats['pending_review'],"#F59E0B"),
        ("👤","Awaiting Assign",stats['awaiting'],"#8B5CF6"),
        ("⚙","In Progress",stats['in_progress'],"#F97316"),
        ("✍","Pending Sign-off",stats['pending_signoff'],"#6366F1"),
        ("🎉","Completed",stats['complete'],"#10B981"),
    ]
    cols = st.columns(6)
    for col,(icon,label,val,color) in zip(cols,stat_items):
        with col:
            st.markdown(f"""<div class="stat-card" style="border-top:3px solid {color};">
              <div class="stat-icon">{icon}</div>
              <div class="stat-val" style="color:{color};">{val}</div>
              <div class="stat-lbl">{label}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown('<div style="font-weight:700;font-size:1rem;margin-bottom:.875rem;color:#0F172A;">Recent Activity</div>', unsafe_allow_html=True)
        if role in ['admin','sbd_manager']: reqs = all_reqs()[:8]
        elif role in ['security_architect','security_engineer','assurance']:
            field_map = {'security_architect':'architect_id','security_engineer':'engineer_id','assurance':'assurance_id'}
            reqs = assigned_reqs(user['id'], field_map.get(role,'created_by'))[:8]
            reqs += user_reqs(user['id'])
            reqs = list({r['id']:r for r in reqs}.values())[:8]
        else:
            reqs = user_reqs(user['id'])[:8]

        if not reqs:
            st.markdown('<div class="card" style="text-align:center;padding:2.5rem;color:#94A3B8;"><div style="font-size:2.5rem;margin-bottom:.75rem;">📭</div><div style="font-weight:600;">No requests yet</div><div style="font-size:.82rem;margin-top:.25rem;">Create your first SbD request to get started</div></div>', unsafe_allow_html=True)
        else:
            for req in reqs:
                _,color,bg,icon = STATUS_CFG.get(req['status'],('','#6B7280','#F3F4F6','?'))
                st.markdown(f"""<div class="card card-sm" style="margin-bottom:.625rem;border-left:3px solid {color};">
                  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:.75rem;">
                    <div style="flex:1;min-width:0;">
                      <div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;margin-bottom:.3rem;">
                        <span class="ref">{req['ref_number']}</span>
                        {status_badge(req['status'])}
                        {outcome_badge(req.get('sbd_outcome'))}
                      </div>
                      <div style="font-weight:600;font-size:.9rem;color:#0F172A;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{req['project_name']}</div>
                      <div style="font-size:.75rem;color:#94A3B8;margin-top:.15rem;">{fdate_short(req['created_at'])}</div>
                    </div>
                  </div>
                </div>""", unsafe_allow_html=True)
                if st.button(f"Open {req['ref_number']}", key=f"dsh_{req['id']}", use_container_width=False):
                    st.session_state.selected_req = req['id']
                    st.session_state.page = "request_detail"; st.rerun()

    with col_right:
        st.markdown('<div style="font-weight:700;font-size:1rem;margin-bottom:.875rem;color:#0F172A;">SbD Outcomes</div>', unsafe_allow_html=True)
        outcome_data = [
            ('no_sbd',    'No SBD Required', stats['o_no_sbd']),
            ('sbd_stage1','SBD Stage 1',     stats['o_sbd_stage1']),
            ('sbd_stage2','SBD Stage 2',     stats['o_sbd_stage2']),
            ('full_sbd',  'Full SBD',        stats['o_full_sbd']),
        ]
        total_out = sum(v for _,_,v in outcome_data) or 1
        st.markdown('<div class="card">', unsafe_allow_html=True)
        for o,label,count in outcome_data:
            _,color,_,_,icon,_ = OUTCOME_CFG[o]
            pct = count/total_out*100
            st.markdown(f"""<div style="margin-bottom:1rem;">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.3rem;">
                <span style="font-size:.82rem;font-weight:500;color:#334155;">{icon} {label}</span>
                <span style="font-family:var(--mono);font-size:.82rem;font-weight:700;color:{color};">{count}</span>
              </div>
              <div style="background:#F1F5F9;border-radius:999px;height:5px;">
                <div style="background:{color};height:5px;border-radius:999px;width:{pct:.1f}%;transition:width .4s;"></div>
              </div>
            </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕  New SbD Request", use_container_width=True, type="primary"):
            st.session_state.page = "new_request"; st.rerun()
        if role in ['admin','sbd_manager']:
            c1,c2 = st.columns(2)
            with c1:
                if st.button("📥 Review", use_container_width=True):
                    st.session_state.page="pending_review"; st.rerun()
            with c2:
                if st.button("👥 Assign", use_container_width=True):
                    st.session_state.page="assign_resources"; st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: NEW REQUEST (4-step wizard with conditional questions)
# ══════════════════════════════════════════════════════════════════════════════

def page_new_request(user):
    st.markdown('<div class="pg-header"><div><div class="pg-title">New SbD Request</div><div class="pg-sub">Complete all steps to submit your security assessment</div></div></div>', unsafe_allow_html=True)

    for k,v in [('nrq_step',1),('nrq_pid',None),('nrq_ans',{}),('nrq_name',''),('nrq_desc',''),('nrq_owner',''),('nrq_type','New Application'),('nrq_golive','')]:
        if k not in st.session_state: st.session_state[k]=v

    step = st.session_state.nrq_step
    _stepper(["Project Info","Assessment","Review","Outcome"], step)
    st.markdown("<br>", unsafe_allow_html=True)

    if step==1: _nrq_s1(user)
    elif step==2: _nrq_s2(user)
    elif step==3: _nrq_s3(user)
    elif step==4: _nrq_s4(user)

def _stepper(steps, cur):
    html='<div style="display:flex;align-items:center;margin-bottom:1.25rem;">'
    for i,label in enumerate(steps,1):
        if i<cur:   ds=f"background:#10B981;color:white;border:2px solid #10B981;"; lc="#10B981"; icon="✓"
        elif i==cur: ds=f"background:#3B82F6;color:white;border:2px solid #3B82F6;box-shadow:0 0 0 3px rgba(59,130,246,.2);"; lc="#3B82F6"; icon=str(i)
        else:        ds="background:#F8FAFC;color:#94A3B8;border:2px solid #E2E8F0;"; lc="#94A3B8"; icon=str(i)
        html+=f'<div style="display:flex;flex-direction:column;align-items:center;flex:1;"><div style="width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.8rem;{ds}">{icon}</div><div style="font-size:.7rem;margin-top:.3rem;color:{lc};font-weight:{"600" if i==cur else "400"};text-align:center;">{label}</div></div>'
        if i<len(steps): lc2="#10B981" if i<cur else "#E2E8F0"; html+=f'<div style="flex:2;height:2px;background:{lc2};margin-bottom:1.1rem;"></div>'
    st.markdown(html+'</div>', unsafe_allow_html=True)

def _nrq_s1(user):
    c1,c2 = st.columns([2,1])
    with c1:
        st.markdown('<div style="font-weight:700;font-size:.95rem;margin-bottom:1rem;color:#0F172A;">📋 Project Information</div>', unsafe_allow_html=True)
        with st.form("nrq_s1"):
            name = st.text_input("Project Name *", value=st.session_state.nrq_name, placeholder="e.g. Customer Payments Portal v3")
            desc = st.text_area("Project Description", value=st.session_state.nrq_desc, placeholder="Describe the project purpose, technology stack, and key data flows...", height=110)
            c_a,c_b = st.columns(2)
            with c_a: owner = st.text_input("Business Owner", value=st.session_state.nrq_owner, placeholder="Name or team")
            with c_b: ptype = st.selectbox("Project Type", ["New Application","Platform Change","Third-party Integration","Data Analytics","Infrastructure","Process Automation"], index=["New Application","Platform Change","Third-party Integration","Data Analytics","Infrastructure","Process Automation"].index(st.session_state.nrq_type) if st.session_state.nrq_type in ["New Application","Platform Change","Third-party Integration","Data Analytics","Infrastructure","Process Automation"] else 0)
            golive = st.text_input("Target Go-Live Date", value=st.session_state.nrq_golive, placeholder="e.g. Q3 2026 or dd/mm/yyyy")
            if st.form_submit_button("Continue to Assessment →", type="primary"):
                if not name.strip(): st.error("Project name is required.")
                else:
                    st.session_state.nrq_name=name.strip(); st.session_state.nrq_desc=desc.strip()
                    st.session_state.nrq_owner=owner.strip(); st.session_state.nrq_type=ptype
                    st.session_state.nrq_golive=golive.strip()
                    st.session_state.nrq_step=2; st.rerun()
    with c2:
        st.markdown('<div class="card" style="background:#F0F9FF;border-color:#BFDBFE;">', unsafe_allow_html=True)
        st.markdown("""<div style="font-weight:700;font-size:.82rem;color:#1E40AF;margin-bottom:.75rem;">ℹ️ About this process</div>
<div style="font-size:.78rem;color:#1E3A5F;line-height:1.6;">
Your answers will be scored to determine the level of security engagement required for your project.<br><br>
The assessment takes approximately <strong>5–10 minutes</strong>.<br><br>
Some questions may only appear based on your previous answers.
</div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

def _nrq_s2(user):
    qs = active_questions()
    top_qs = [q for q in qs if q['stage_visibility']=='all' and q['parent_question_id'] is None]
    child_map = {}
    for q in qs:
        if q['parent_question_id']:
            pid = str(q['parent_question_id'])
            child_map.setdefault(pid,[]).append(q)

    st.markdown('<div style="font-weight:700;font-size:.95rem;margin-bottom:1rem;color:#0F172A;">🔍 Security Assessment</div>', unsafe_allow_html=True)

    cats = {}
    for q in top_qs: cats.setdefault(q['category'],[]).append(q)

    with st.form("nrq_s2"):
        answers = {}
        qnum = 0

        for cat, cat_qs in cats.items():
            st.markdown(f'<div style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#64748B;margin:.75rem 0 .5rem;padding-top:.5rem;border-top:1px solid #F1F5F9;">{cat}</div>', unsafe_allow_html=True)
            for q in cat_qs:
                qnum += 1
                opts = json.loads(q['options'])
                prev = st.session_state.nrq_ans.get(str(q['id']),{}).get('answer')
                prev_idx = opts.index(prev) if prev in opts else 0

                hint_html = f'<div class="q-hint">💡 {q["hint"]}</div>' if q.get('hint') else ''
                desc_html = f'<div class="q-desc">{q["description"]}</div>' if q.get('description') else ''
                st.markdown(f'<div class="q-card"><div class="q-num">Q{qnum}</div><div class="q-text">{q["text"]}</div>{desc_html}{hint_html}</div>', unsafe_allow_html=True)
                sel = st.radio("", options=opts, index=prev_idx, key=f"q_{q['id']}", label_visibility="collapsed")
                answers[q['id']] = sel

                # Show child questions conditionally
                children = child_map.get(str(q['id']), [])
                for child in children:
                    if child['trigger_answer'] and sel == child['trigger_answer']:
                        c_opts = json.loads(child['options'])
                        c_prev = st.session_state.nrq_ans.get(str(child['id']),{}).get('answer')
                        c_prev_idx = c_opts.index(c_prev) if c_prev in c_opts else 0
                        c_desc = f'<div class="q-desc">{child["description"]}</div>' if child.get('description') else ''
                        st.markdown(f'<div class="q-card nested"><div class="q-num nested">↳ Follow-up</div><div class="q-text">{child["text"]}</div>{c_desc}</div>', unsafe_allow_html=True)
                        c_sel = st.radio("", options=c_opts, index=c_prev_idx, key=f"q_{child['id']}", label_visibility="collapsed")
                        answers[child['id']] = c_sel

        st.markdown("<br>", unsafe_allow_html=True)
        cc1,cc2 = st.columns([1,5])
        with cc1: back = st.form_submit_button("← Back")
        with cc2: proceed = st.form_submit_button("Review Answers →", type="primary")

        if back: st.session_state.nrq_step=1; st.rerun()
        if proceed:
            qs_map = {q['id']:q for q in qs}
            scored = {}
            for qid, answer in answers.items():
                q = qs_map.get(qid)
                if not q: continue
                opts = json.loads(q['options']); wts = json.loads(q['weights'])
                score = wts[opts.index(answer)] if answer in opts else 0
                scored[str(qid)] = {'answer':answer,'score':score}
            st.session_state.nrq_ans = scored
            st.session_state.nrq_step = 3; st.rerun()

def _nrq_s3(user):
    qs = active_questions()
    qs_map = {q['id']:q for q in qs}
    cfg = get_cfg()

    answered = st.session_state.nrq_ans
    total = sum(v['score'] for v in answered.values())
    max_s = sum(qs_map[int(qid)]['max_score'] for qid in answered if int(qid) in qs_map)
    pct = (total/max_s*100) if max_s>0 else 0
    outcome = sbd_outcome(pct, cfg)
    _,o_color,o_bg,o_border,o_icon,o_desc = OUTCOME_CFG[outcome]

    st.markdown('<div style="font-weight:700;font-size:.95rem;margin-bottom:1rem;color:#0F172A;">📝 Review & Submit</div>', unsafe_allow_html=True)

    c1,c2 = st.columns([3,2])
    with c1:
        st.markdown(f"""<div class="card card-sm" style="margin-bottom:1rem;">
          <div style="font-weight:700;font-size:1rem;color:#0F172A;margin-bottom:.25rem;">{st.session_state.nrq_name}</div>
          <div style="font-size:.82rem;color:#64748B;">{st.session_state.nrq_desc or 'No description provided'}</div>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:.75rem;margin-top:.875rem;">
            <div><div style="font-size:.65rem;color:#94A3B8;text-transform:uppercase;font-weight:600;">Owner</div><div style="font-size:.82rem;font-weight:500;">{st.session_state.nrq_owner or '—'}</div></div>
            <div><div style="font-size:.65rem;color:#94A3B8;text-transform:uppercase;font-weight:600;">Type</div><div style="font-size:.82rem;font-weight:500;">{st.session_state.nrq_type}</div></div>
            <div><div style="font-size:.65rem;color:#94A3B8;text-transform:uppercase;font-weight:600;">Go-Live</div><div style="font-size:.82rem;font-weight:500;">{st.session_state.nrq_golive or '—'}</div></div>
          </div>
        </div>""", unsafe_allow_html=True)

        # Show answers — no individual scores shown to submitter
        by_cat = {}
        for qid_s, ans_d in answered.items():
            q = qs_map.get(int(qid_s))
            if not q: continue
            by_cat.setdefault(q['category'],[]).append((q,ans_d['answer']))

        for cat, items in by_cat.items():
            st.markdown(f'<div style="font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#94A3B8;margin:.75rem 0 .4rem;">{cat}</div>', unsafe_allow_html=True)
            for q, ans in items:
                is_child = bool(q.get('parent_question_id'))
                indent = "margin-left:1rem;" if is_child else ""
                st.markdown(f"""<div style="padding:.5rem .75rem;border:1px solid #F1F5F9;border-radius:8px;margin-bottom:.3rem;{indent}">
                  <div style="font-size:.78rem;color:#64748B;">{q['text']}</div>
                  <div style="font-size:.82rem;font-weight:600;color:#0F172A;margin-top:.15rem;">→ {ans}</div>
                </div>""", unsafe_allow_html=True)

    with c2:
        # Score ring — hidden from user; show outcome only
        st.markdown(f"""<div class="outcome-banner" style="background:{o_bg};border-color:{o_border};margin-bottom:1rem;">
          <div class="outcome-icon">{o_icon}</div>
          <div>
            <div class="outcome-title" style="color:{o_color};">Preliminary Outcome</div>
            <div class="outcome-desc" style="color:{o_color};">{_[0] if isinstance(_,tuple) else OUTCOME_CFG[outcome][0]}</div>
            <div style="font-size:.75rem;color:#64748B;margin-top:.4rem;">{o_desc}</div>
          </div>
        </div>""", unsafe_allow_html=True)

        # Get the outcome label properly
        o_label = OUTCOME_CFG[outcome][0]
        st.markdown(f"""<div class="outcome-banner" style="background:{o_bg};border-color:{o_border};margin-bottom:1rem;">
          <div class="outcome-icon">{o_icon}</div>
          <div>
            <div class="outcome-title" style="color:{o_color};">{o_label}</div>
            <div style="font-size:.75rem;color:#64748B;margin-top:.4rem;">{o_desc}</div>
          </div>
        </div>""", unsafe_allow_html=True)

        st.markdown('<div class="alert alert-info" style="font-size:.78rem;">The SbD team will review and confirm the final outcome. Individual question scores are not shown.</div>', unsafe_allow_html=True)

        cfg2 = get_cfg()
        t1=int(float(cfg2.get('threshold_no_sbd',20))); t2=int(float(cfg2.get('threshold_stage1',40))); t3=int(float(cfg2.get('threshold_stage2',65)))
        st.markdown(f"""<div class="card card-sm" style="margin-top:1rem;">
          <div style="font-size:.72rem;font-weight:700;color:#64748B;text-transform:uppercase;margin-bottom:.5rem;">Score Thresholds</div>
          {"".join(f'<div style="display:flex;justify-content:space-between;font-size:.78rem;padding:.2rem 0;border-bottom:1px solid #F8FAFC;"><span>{band}</span><span style="color:{c};font-weight:600;">{lbl}</span></div>' for band,lbl,c in [(f"0–{t1}%","No SBD","#6B7280"),(f"{t1+1}–{t2}%","Stage 1","#D97706"),(f"{t2+1}–{t3}%","Stage 2","#DC2626"),(f"{t3+1}–100%","Full SBD","#7C3AED")])}
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    cb1,_,cb3 = st.columns([1,1,2])
    with cb1:
        if st.button("← Revise Answers"): st.session_state.nrq_step=2; st.rerun()
    with cb3:
        if st.button("✅  Submit Request", type="primary", use_container_width=True):
            rid,ref = create_request(st.session_state.nrq_name, st.session_state.nrq_desc,
                                     st.session_state.nrq_owner, st.session_state.nrq_type,
                                     st.session_state.nrq_golive, user['id'])
            t,mx,p = save_answers(rid, st.session_state.nrq_ans)
            finalize(rid, outcome, t, mx, p, user['id'])
            st.session_state.nrq_pid=rid; st.session_state.nrq_ref=ref
            st.session_state.nrq_outcome=outcome; st.session_state.nrq_pct=p
            st.session_state.nrq_step=4; st.rerun()

def _nrq_s4(user):
    outcome = st.session_state.get('nrq_outcome','no_sbd')
    ref = st.session_state.get('nrq_ref',''); rid = st.session_state.get('nrq_pid')
    o_label,o_color,o_bg,o_border,o_icon,o_desc = OUTCOME_CFG[outcome]

    c1,c2,c3 = st.columns([1,2,1])
    with c2:
        st.markdown(f"""<div style="text-align:center;padding:2rem 0 1.5rem;">
          <div style="font-size:3.5rem;margin-bottom:.75rem;">{o_icon}</div>
          <div style="font-size:1.4rem;font-weight:800;color:#0F172A;letter-spacing:-.02em;">Request Submitted</div>
          <div style="margin-top:.5rem;"><span class="ref" style="font-size:.9rem;">{ref}</span></div>
        </div>""", unsafe_allow_html=True)

        st.markdown(f"""<div class="outcome-banner" style="background:{o_bg};border-color:{o_border};margin-bottom:1.25rem;">
          <div class="outcome-icon">{o_icon}</div>
          <div>
            <div style="font-size:.72rem;font-weight:600;color:#64748B;text-transform:uppercase;letter-spacing:.06em;">Preliminary Assessment</div>
            <div class="outcome-title" style="color:{o_color};margin-top:.15rem;">{o_label}</div>
            <div class="outcome-desc" style="color:#64748B;margin-top:.25rem;">{o_desc}</div>
          </div>
        </div>""", unsafe_allow_html=True)

        if outcome == 'no_sbd':
            st.markdown('<div class="alert alert-success">✅ Based on your responses this project may not require SbD engagement. The SbD team will review and confirm within 5 business days.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="alert alert-warn">⚠️ Your project will proceed through the SbD programme. An SbD Programme Manager will be in touch to assign resources and guide you through each phase.</div>', unsafe_allow_html=True)

        ca,cb = st.columns(2)
        with ca:
            if st.button("View My Request →", type="primary", use_container_width=True):
                st.session_state.selected_req=rid; st.session_state.page="request_detail"
                for k in ['nrq_step','nrq_pid','nrq_ans','nrq_name','nrq_desc','nrq_owner','nrq_type','nrq_golive','nrq_ref','nrq_outcome','nrq_pct']: st.session_state.pop(k,None)
                st.rerun()
        with cb:
            if st.button("New Request", use_container_width=True):
                for k in ['nrq_step','nrq_pid','nrq_ans','nrq_name','nrq_desc','nrq_owner','nrq_type','nrq_golive','nrq_ref','nrq_outcome','nrq_pct']: st.session_state.pop(k,None)
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: MY REQUESTS & ASSIGNED
# ══════════════════════════════════════════════════════════════════════════════

def page_my_requests(user):
    st.markdown('<div class="pg-header"><div><div class="pg-title">My Requests</div><div class="pg-sub">SbD requests you have created or been granted access to</div></div></div>', unsafe_allow_html=True)
    _req_list(user, user_reqs(user['id']))

def page_assigned(user):
    field_map = {'security_architect':'architect_id','security_engineer':'engineer_id','assurance':'assurance_id'}
    field = field_map.get(user['role'])
    if not field: st.error("Not applicable for your role."); return
    reqs = assigned_reqs(user['id'], field)
    role_lbl = ROLE_LABELS.get(user['role'],'')
    st.markdown(f'<div class="pg-header"><div><div class="pg-title">Assigned to Me</div><div class="pg-sub">Requests where you are assigned as {role_lbl}</div></div></div>', unsafe_allow_html=True)
    _req_list(user, reqs, show_assignment_info=True)

def _req_list(user, reqs, show_assignment_info=False):
    cf1,cf2,cf3 = st.columns([2,3,1])
    with cf1:
        sf = st.selectbox("Status",["All","Pending Review","Awaiting Assignment","In Progress","Pending Sign-off","Completed","No SBD"])
    with cf2:
        search = st.text_input("Search", placeholder="Project name or reference...")
    with cf3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ New", type="primary", use_container_width=True):
            st.session_state.page="new_request"; st.rerun()

    sm = {"Pending Review":['pending_review'],"Awaiting Assignment":['awaiting_assignment'],
          "In Progress":['architect_assigned','architect_completed','engineer_assigned','engineer_completed','assurance_assigned','assurance_completed'],
          "Pending Sign-off":['pending_signoff'],"Completed":['signoff_received'],"No SBD":['no_sbd_needed']}
    filtered = reqs
    if sf!="All": filtered=[r for r in filtered if r['status'] in sm.get(sf,[])]
    if search: s=search.lower(); filtered=[r for r in filtered if s in r['project_name'].lower() or s in r['ref_number'].lower()]

    if not filtered:
        st.markdown('<div class="card" style="text-align:center;padding:3rem;color:#94A3B8;"><div style="font-size:2.5rem;margin-bottom:.75rem;">📭</div><div style="font-weight:600;color:#475569;">No requests found</div></div>', unsafe_allow_html=True); return

    st.markdown(f'<div style="font-size:.78rem;color:#64748B;margin-bottom:.875rem;"><strong style="color:#0F172A;">{len(filtered)}</strong> request(s)</div>', unsafe_allow_html=True)
    for req in filtered:
        _,color,bg,_ = STATUS_CFG.get(req['status'],('','#6B7280','#F3F4F6','?'))
        st.markdown(f"""<div class="card card-sm" style="margin-bottom:.75rem;border-left:3px solid {color};">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:.75rem;margin-bottom:.625rem;">
            <div style="flex:1;min-width:0;">
              <div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;margin-bottom:.3rem;">
                <span class="ref">{req['ref_number']}</span>
                {status_badge(req['status'])} {outcome_badge(req.get('sbd_outcome'))}
              </div>
              <div style="font-weight:700;font-size:.92rem;color:#0F172A;">{req['project_name']}</div>
              <div style="font-size:.75rem;color:#94A3B8;margin-top:.15rem;">Submitted {fdate_short(req['created_at'])}{f" · {req['project_type']}" if req.get('project_type') else ""}</div>
            </div>
          </div>
          {render_pipeline(req['status'])}
        </div>""", unsafe_allow_html=True)
        if st.button(f"Open request →", key=f"lst_{req['id']}"):
            st.session_state.selected_req=req['id']; st.session_state.page="request_detail"; st.rerun()
        st.markdown("<div style='margin-bottom:.25rem;'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: REQUEST DETAIL
# ══════════════════════════════════════════════════════════════════════════════

def page_request_detail(user):
    rid = st.session_state.get('selected_req')
    if not rid: st.error("No request selected."); return
    role = user['role']
    is_mgr = role in ['admin','sbd_manager']
    req = get_req(rid)
    if not req: st.error("Request not found."); return

    # Access control
    assigned = is_assigned(rid, user['id'])
    has_access = is_mgr or can_access(rid,user['id']) or assigned
    if not has_access: st.error("🚫 You don't have permission to view this request."); return
    has_write = is_mgr or can_access(rid,user['id'],write=True) or assigned
    is_locked = bool(req.get('is_locked'))

    col_back,_ = st.columns([1,8])
    with col_back:
        if st.button("← Back"):
            st.session_state.page = "assigned" if assigned and not can_access(rid,user['id']) else "my_requests"; st.rerun()

    _,color,bg,border_col,_icon,_ = OUTCOME_CFG.get(req.get('sbd_outcome','no_sbd'),OUTCOME_CFG['no_sbd'])

    st.markdown(f"""<div class="pg-header">
      <div>
        <div style="display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;margin-bottom:.4rem;">
          <div class="pg-title">{req['project_name']}</div>
          <span class="ref">{req['ref_number']}</span>
          {status_badge(req['status'])} {outcome_badge(req.get('sbd_outcome'))}
        </div>
        <div class="pg-sub">
          {f"Business Owner: {req['business_owner']} · " if req.get('business_owner') else ""}
          {f"Type: {req['project_type']} · " if req.get('project_type') else ""}
          Submitted {fdate_short(req.get('submitted_at'))}
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    if is_locked:
        st.markdown('<div class="lock-banner">🔒 This request is locked — sign-off has been received. No further modifications are permitted.</div>', unsafe_allow_html=True)

    # Pipeline
    st.markdown(render_pipeline(req['status']), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    tabs = st.tabs(["📋 Overview", "🔍 Assessment", "👥 Team & Access", "💬 Comments", "📜 Audit Trail"])
    with tabs[0]: _rd_overview(req, user, has_write, is_locked, is_mgr, assigned)
    with tabs[1]: _rd_assessment(req, user, is_mgr)
    with tabs[2]: _rd_team(req, user, has_write, is_locked, is_mgr)
    with tabs[3]: _rd_comments(req, user, is_mgr)
    with tabs[4]: _rd_audit(req)

def _rd_overview(req, user, has_write, is_locked, is_mgr, assigned):
    c1,c2 = st.columns([3,2])
    with c1:
        outcome = req.get('sbd_outcome')
        if outcome:
            o_label,o_color,o_bg,o_border,o_icon,o_desc = OUTCOME_CFG.get(outcome, OUTCOME_CFG['no_sbd'])
            st.markdown(f"""<div class="outcome-banner" style="background:{o_bg};border-color:{o_border};margin-bottom:1rem;">
              <div class="outcome-icon">{o_icon}</div>
              <div>
                <div class="outcome-title" style="color:{o_color};">{o_label}</div>
                <div class="outcome-desc" style="color:#64748B;">{o_desc}</div>
              </div>
            </div>""", unsafe_allow_html=True)

        st.markdown(f"""<div class="card card-sm" style="margin-bottom:1rem;">
          <div style="font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#94A3B8;margin-bottom:.75rem;">Project Details</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:.875rem;">
            <div><div style="font-size:.65rem;color:#94A3B8;text-transform:uppercase;font-weight:600;">Business Owner</div><div style="font-size:.87rem;font-weight:500;margin-top:.15rem;">{req.get('business_owner') or '—'}</div></div>
            <div><div style="font-size:.65rem;color:#94A3B8;text-transform:uppercase;font-weight:600;">Project Type</div><div style="font-size:.87rem;font-weight:500;margin-top:.15rem;">{req.get('project_type') or '—'}</div></div>
            <div><div style="font-size:.65rem;color:#94A3B8;text-transform:uppercase;font-weight:600;">Go-Live Target</div><div style="font-size:.87rem;font-weight:500;margin-top:.15rem;">{req.get('go_live_date') or '—'}</div></div>
            <div><div style="font-size:.65rem;color:#94A3B8;text-transform:uppercase;font-weight:600;">Submitted</div><div style="font-size:.87rem;font-weight:500;margin-top:.15rem;">{fdate_short(req.get('submitted_at'))}</div></div>
          </div>
          {f'<div style="margin-top:.875rem;padding-top:.875rem;border-top:1px solid #F1F5F9;"><div style="font-size:.65rem;color:#94A3B8;text-transform:uppercase;font-weight:600;">Description</div><div style="font-size:.85rem;color:#334155;margin-top:.15rem;">{req["project_description"]}</div></div>' if req.get('project_description') else ''}
        </div>""", unsafe_allow_html=True)

        if req.get('architect_url'):
            st.markdown(f"""<div class="card card-sm" style="margin-bottom:1rem;background:#F0FDF4;border-color:#A7F3D0;">
              <div style="font-size:.65rem;font-weight:700;text-transform:uppercase;color:#065F46;margin-bottom:.5rem;">Architecture Document</div>
              <a href="{req['architect_url']}" target="_blank" style="color:#059669;font-weight:600;font-size:.88rem;">🔗 View Document</a>
              {f'<div style="font-size:.8rem;color:#047857;margin-top:.4rem;">{req["architect_notes"]}</div>' if req.get('architect_notes') else ''}
            </div>""", unsafe_allow_html=True)

    with c2:
        st.markdown('<div style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#64748B;margin-bottom:.75rem;">Phase Timeline</div>', unsafe_allow_html=True)
        st.markdown(phase_timeline(req), unsafe_allow_html=True)

        assigned_html = ""
        for fld,lbl,icon in [('architect_id','Security Architect','🏗'),('engineer_id','Security Engineer','⚙'),('assurance_id','Assurance Analyst','🔍')]:
            if req.get(fld):
                p = get_user_id(req[fld])
                if p: assigned_html += f'<div style="display:flex;align-items:center;gap:.625rem;padding:.5rem 0;border-bottom:1px solid #F8FAFC;"><span style="font-size:1.1rem;">{icon}</span><div><div style="font-weight:600;font-size:.82rem;">{p["name"]}</div><div style="font-size:.72rem;color:#94A3B8;">{lbl}</div></div></div>'
        if assigned_html:
            st.markdown(f'<div class="card card-sm" style="margin-top:1rem;"><div style="font-size:.72rem;font-weight:700;text-transform:uppercase;color:#64748B;margin-bottom:.5rem;">Assigned Team</div>{assigned_html}</div>', unsafe_allow_html=True)

    if not is_locked:
        _rd_actions(req, user, has_write, is_mgr, assigned)

def _rd_actions(req, user, has_write, is_mgr, assigned):
    status = req['status']; rid = req['id']
    st.markdown("---")
    col_h,_ = st.columns([3,2])
    with col_h: st.markdown('<div style="font-weight:700;font-size:.9rem;margin-bottom:.75rem;color:#0F172A;">Available Actions</div>', unsafe_allow_html=True)
    cols = st.columns(5); ci=0
    def btn(label, key, primary=True):
        nonlocal ci
        with cols[ci%5]:
            r = st.button(label, key=key, type="primary" if primary else "secondary", use_container_width=True)
        ci+=1; return r

    if is_mgr:
        if status=='pending_review':
            if btn("✅ Confirm Review","act_confirm"): update_status(rid,'awaiting_assignment',user['id'],'Review confirmed'); st.rerun()
            if btn("🚫 No SBD Required","act_nosbd",False): update_status(rid,'no_sbd_needed',user['id'],'Determined: No SBD required'); st.rerun()
        if status=='architect_assigned':
            if btn("✅ Architecture Done","act_archdone"): update_status(rid,'architect_completed',user['id'],'Architecture review completed'); st.rerun()
        if status=='architect_completed':
            if btn("➡ Assign Engineer","act_toeng"): update_status(rid,'engineer_assigned',user['id'],'Moving to engineering phase'); st.rerun()
        if status=='engineer_assigned':
            if btn("✅ Engineering Done","act_engdone"): update_status(rid,'engineer_completed',user['id'],'Engineering work completed'); st.rerun()
        if status=='engineer_completed':
            if btn("➡ Assign Assurance","act_toassur"): update_status(rid,'assurance_assigned',user['id'],'Moving to assurance phase'); st.rerun()
        if status=='assurance_assigned':
            if btn("✅ Assurance Done","act_assurdone"): update_status(rid,'assurance_completed',user['id'],'Assurance completed'); st.rerun()
        if status=='assurance_completed':
            if btn("➡ Move to Sign-off","act_tosignoff"): update_status(rid,'pending_signoff',user['id'],'Moved to sign-off queue'); st.rerun()
        if status=='pending_signoff':
            if btn("🎉 Record Sign-off","act_signoff"): update_status(rid,'signoff_received',user['id'],'Sign-off received',{'signoff_by':user['id']}); st.rerun()

    # Architect: can add URL at any point in their phase
    if (assigned and req.get('architect_id')==user['id']) or is_mgr:
        if status in ['architect_assigned','architect_completed','engineer_assigned','engineer_completed','assurance_assigned','assurance_completed','pending_signoff','signoff_received']:
            with st.expander("🔗 Architecture Document Link"):
                au = st.text_input("Document URL", value=req.get('architect_url',''), key="arch_url")
                an = st.text_area("Notes", value=req.get('architect_notes',''), key="arch_notes", height=70)
                if st.button("Save Link", key="save_archlink", type="primary"):
                    c2=db(); c2.execute("UPDATE requests SET architect_url=?,architect_notes=? WHERE id=?",(au,an,rid)); c2.commit(); c2.close()
                    st.success("Saved."); st.rerun()

    # Engineer notes
    if (assigned and req.get('engineer_id')==user['id']) or is_mgr:
        if status in ['engineer_assigned','engineer_completed','assurance_assigned','assurance_completed','pending_signoff']:
            with st.expander("⚙ Engineering Notes"):
                en = st.text_area("Notes", value=req.get('engineer_notes',''), key="eng_notes_field", height=100)
                if st.button("Save Notes", key="save_engnotes", type="primary"):
                    c2=db(); c2.execute("UPDATE requests SET engineer_notes=? WHERE id=?",(en,rid)); c2.commit(); c2.close()
                    st.success("Saved."); st.rerun()

    # Assurance notes
    if (assigned and req.get('assurance_id')==user['id']) or is_mgr:
        if status in ['assurance_assigned','assurance_completed','pending_signoff']:
            with st.expander("🔍 Assurance Notes"):
                asnote = st.text_area("Notes", value=req.get('assurance_notes',''), key="assur_notes_field", height=100)
                if st.button("Save Notes", key="save_assurnotes", type="primary"):
                    c2=db(); c2.execute("UPDATE requests SET assurance_notes=? WHERE id=?",(asnote,rid)); c2.commit(); c2.close()
                    st.success("Saved."); st.rerun()

def _rd_assessment(req, user, is_mgr):
    answers = req_answers(req['id'])
    if not answers: st.info("No assessment answers on record."); return

    is_submitter = req['created_by'] == user['id']
    show_scores = is_mgr or (not is_submitter)  # hide per-Q scores from submitter

    total = req.get('total_score',0); max_s = req.get('max_possible_score',0)
    pct = req.get('score_pct',0)

    if show_scores:
        c1,c2,c3 = st.columns([1,1,3])
        with c1: st.markdown(score_ring(pct, show_score=True), unsafe_allow_html=True)
        with c2:
            st.markdown(f"""<div style="padding-top:.5rem;">
              <div style="font-size:.65rem;color:#94A3B8;text-transform:uppercase;font-weight:600;">Raw Score</div>
              <div style="font-family:var(--mono);font-size:1.3rem;font-weight:700;color:#0F172A;">{total:.0f} / {max_s:.0f}</div>
              <div style="font-size:.65rem;color:#94A3B8;text-transform:uppercase;font-weight:600;margin-top:.75rem;">Questions Answered</div>
              <div style="font-family:var(--mono);font-size:1.3rem;font-weight:700;">{len(answers)}</div>
            </div>""", unsafe_allow_html=True)
    else:
        st.markdown('<div class="alert alert-info">Individual question scores are visible to the SbD team only. Your overall assessment outcome is shown in the Overview tab.</div>', unsafe_allow_html=True)

    by_cat = {}
    for a in answers: by_cat.setdefault(a['category'],[]).append(a)

    for cat, items in by_cat.items():
        st.markdown(f'<div style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#64748B;margin:.875rem 0 .5rem;">{cat}</div>', unsafe_allow_html=True)
        for a in items:
            wts = json.loads(a['weights']) if isinstance(a['weights'],str) else a['weights']
            mx = max(wts) if wts else 10
            sc = a['score']; sp = (sc/mx*100) if mx>0 else 0
            bc="#EF4444" if sp>=70 else ("#F59E0B" if sp>=40 else "#10B981")
            score_html = f'<div style="font-family:var(--mono);font-weight:700;color:{bc};white-space:nowrap;">{sc:.0f}/{mx}</div>' if show_scores else ''
            st.markdown(f"""<div style="padding:.625rem .875rem;border:1px solid #F1F5F9;border-radius:8px;margin-bottom:.375rem;display:flex;justify-content:space-between;align-items:flex-start;gap:.75rem;">
              <div style="flex:1;min-width:0;">
                <div style="font-size:.78rem;color:#64748B;">{a['qtxt']}</div>
                <div style="font-size:.85rem;font-weight:600;color:#0F172A;margin-top:.15rem;">→ {a['answer']}</div>
                {f'<div style="font-size:.72rem;color:#94A3B8;margin-top:.15rem;font-style:italic;">{a["hint"]}</div>' if a.get('hint') and show_scores else ''}
              </div>
              {score_html}
            </div>""", unsafe_allow_html=True)
            if show_scores and sp>0:
                st.markdown(f'<div style="background:#F1F5F9;border-radius:999px;height:3px;margin:-2px 0 6px;"><div style="background:{bc};height:3px;border-radius:999px;width:{sp:.1f}%;"></div></div>', unsafe_allow_html=True)

def _rd_team(req, user, has_write, is_locked, is_mgr):
    rid = req['id']
    creator = get_user_id(req['created_by'])
    if creator:
        dept = f" · {creator.get('department','')}" if creator.get('department') else ''
        st.markdown(f"""<div style="display:flex;align-items:center;gap:.875rem;padding:.875rem;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:var(--radius);margin-bottom:.75rem;">
          <div style="width:38px;height:38px;background:linear-gradient(135deg,#3B82F6,#8B5CF6);border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-weight:700;flex-shrink:0;">{creator['name'][0]}</div>
          <div style="flex:1;"><div style="font-weight:600;font-size:.9rem;">{creator['name']}</div><div style="font-size:.75rem;color:#64748B;">{creator['email']}{dept}</div></div>
          <span class="badge" style="background:#ECFDF5;color:#065F46;">Owner</span>
        </div>""", unsafe_allow_html=True)

    perms = get_perms(rid)
    if perms:
        st.markdown('<div style="font-weight:600;font-size:.82rem;margin:.875rem 0 .5rem;">Shared Access</div>', unsafe_allow_html=True)
        for p in perms:
            c1,c2 = st.columns([6,1])
            with c1:
                perm_color = "#065F46" if p['permission']=='write' else '#1E40AF'
                perm_bg = "#ECFDF5" if p['permission']=='write' else '#EFF6FF'
                st.markdown(f"""<div style="display:flex;align-items:center;gap:.75rem;padding:.6rem .875rem;border:1px solid #E2E8F0;border-radius:8px;margin-bottom:.375rem;">
                  <div style="width:30px;height:30px;background:#64748B;border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-size:.8rem;font-weight:700;flex-shrink:0;">{p['name'][0]}</div>
                  <div style="flex:1;"><div style="font-weight:500;font-size:.87rem;">{p['name']}</div><div style="font-size:.73rem;color:#94A3B8;">{p['email']}</div></div>
                  <span class="badge" style="background:{perm_bg};color:{perm_color};">{p['permission'].upper()}</span>
                </div>""", unsafe_allow_html=True)
            with c2:
                if (has_write or is_mgr) and not is_locked:
                    if st.button("✕", key=f"rmperm_{p['user_id']}", help="Remove access"):
                        del_perm(rid,p['user_id']); st.rerun()

    if (has_write or is_mgr) and not is_locked:
        st.markdown("---")
        st.markdown('<div style="font-weight:600;font-size:.88rem;margin-bottom:.625rem;">Grant Access</div>', unsafe_allow_html=True)
        all_u = all_users()
        existing = {p['user_id'] for p in perms}|{req['created_by']}
        avail = [u for u in all_u if u['id'] not in existing and u['id']!=user['id']]
        if avail:
            umap = {u['id']:f"{u['name']}  (@{u['username']}) · {ROLE_LABELS.get(u['role'],u['role'])}" for u in avail}
            ca,cb,cc = st.columns([3,2,1])
            with ca: sel = st.selectbox("Select User", [u['id'] for u in avail], format_func=lambda x:umap[x], label_visibility="collapsed")
            with cb: pl = st.selectbox("Permission", ["read","write"], label_visibility="collapsed")
            with cc:
                if st.button("Grant", type="primary", use_container_width=True):
                    add_perm(rid,sel,pl,user['id']); st.success("Access granted."); st.rerun()
        else:
            st.caption("All users already have access.")

def _rd_comments(req, user, is_mgr):
    rid = req['id']
    comments = get_comments(rid, show_internal=is_mgr)
    if not comments:
        st.markdown('<div style="text-align:center;padding:2rem;color:#94A3B8;font-size:.85rem;">No comments yet.</div>', unsafe_allow_html=True)
    else:
        for c in comments:
            is_internal = bool(c.get('is_internal'))
            bg = "#FFFBEB" if is_internal else "#F8FAFC"
            border = "#FDE68A" if is_internal else "#E2E8F0"
            tag = '<span class="badge" style="background:#FEF3C7;color:#92400E;font-size:.65rem;">Internal</span> ' if is_internal else ''
            st.markdown(f"""<div style="background:{bg};border:1px solid {border};border-radius:8px;padding:.875rem 1rem;margin-bottom:.5rem;">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.4rem;">
                <div style="font-size:.8rem;font-weight:600;color:#334155;">{tag}{c['name']} <span style="color:#94A3B8;font-weight:400;">· {ROLE_LABELS.get(c['role'],c['role'])}</span></div>
                <div style="font-size:.72rem;color:#94A3B8;">{fdate(c['created_at'])}</div>
              </div>
              <div style="font-size:.85rem;color:#0F172A;line-height:1.55;">{c['text']}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")
    with st.form("comment_form"):
        text = st.text_area("Add a comment", placeholder="Type your comment here...", height=90, label_visibility="collapsed")
        cc1,cc2 = st.columns([3,1])
        with cc1:
            internal = st.checkbox("Internal note (SbD team only)", value=False) if is_mgr else False
        with cc2:
            if st.form_submit_button("Post Comment", type="primary", use_container_width=True):
                if text.strip():
                    add_comment(rid, user['id'], text.strip(), internal); st.rerun()
                else: st.error("Comment cannot be empty.")

def _rd_audit(req):
    hist = status_hist(req['id'])
    if not hist: st.info("No history."); return
    html='<div class="tl">'
    for item in reversed(hist):
        html+=f"""<div class="tl-item">
          <div class="tl-dot tl-dot-done"></div>
          <div class="tl-title">{item.get('from_status','—') or '(created)'} → {item['to_status']}</div>
          <div class="tl-meta">By {item['by_name']} · {fdate(item['created_at'])}</div>
          {f'<div class="tl-note">{item["notes"]}</div>' if item.get('notes') else ''}
        </div>"""
    st.markdown(html+'</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: PENDING REVIEW
# ══════════════════════════════════════════════════════════════════════════════

def page_pending_review(user):
    if user['role'] not in ['admin','sbd_manager']: st.error("Access denied."); return
    st.markdown('<div class="pg-header"><div><div class="pg-title">Review Queue</div><div class="pg-sub">Submitted requests awaiting initial SbD assessment review</div></div></div>', unsafe_allow_html=True)
    reqs = reqs_by_status(['pending_review'])
    if not reqs:
        st.markdown('<div class="card" style="text-align:center;padding:3rem;color:#94A3B8;"><div style="font-size:2.5rem;">✅</div><div style="font-weight:600;color:#475569;margin-top:.5rem;">Queue is clear</div></div>', unsafe_allow_html=True); return
    st.markdown(f'<div style="font-size:.78rem;color:#64748B;margin-bottom:.875rem;"><strong style="color:#0F172A;">{len(reqs)}</strong> awaiting review</div>', unsafe_allow_html=True)
    for req in reqs:
        c1,c2,c3 = st.columns([4,2,2])
        with c1:
            st.markdown(f"""<div style="padding:.75rem .875rem;border:1px solid #E2E8F0;border-radius:8px;background:#FAFAFA;">
              <div style="display:flex;gap:.5rem;align-items:center;margin-bottom:.3rem;"><span class="ref">{req['ref_number']}</span>{outcome_badge(req.get('sbd_outcome'))}</div>
              <div style="font-weight:600;font-size:.9rem;">{req['project_name']}</div>
              <div style="font-size:.75rem;color:#94A3B8;margin-top:.15rem;">Submitted {fdate(req['created_at'])} · Score: <strong>{req.get('score_pct',0):.0f}%</strong></div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("View Details", key=f"prv_{req['id']}"):
                st.session_state.selected_req=req['id']; st.session_state.page="request_detail"; st.rerun()
        with c3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("✅ Confirm Review", key=f"prc_{req['id']}", type="primary", use_container_width=True):
                update_status(req['id'],'awaiting_assignment',user['id'],'Initial review completed'); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: ASSIGN RESOURCES
# ══════════════════════════════════════════════════════════════════════════════

def page_assign_resources(user):
    if user['role'] not in ['admin','sbd_manager']: st.error("Access denied."); return
    st.markdown('<div class="pg-header"><div><div class="pg-title">Assign Resources</div><div class="pg-sub">Assign security professionals to requests awaiting engagement</div></div></div>', unsafe_allow_html=True)
    reqs = reqs_by_status(['awaiting_assignment','architect_assigned','architect_completed','engineer_assigned','engineer_completed','assurance_assigned'])
    if not reqs: st.info("No requests currently require resource assignment."); return
    architects=all_users('security_architect'); engineers=all_users('security_engineer'); assurance_users=all_users('assurance')
    for req in reqs:
        status=req['status']
        if status=='awaiting_assignment': nl,ni,needs='Assign Security Architect','🏗','architect'
        elif status=='architect_completed': nl,ni,needs='Assign Security Engineer','⚙','engineer'
        elif status=='engineer_completed': nl,ni,needs='Assign Assurance','🔍','assurance'
        else: nl,ni,needs='In Progress','⚙',None
        _,color,bg,_ = STATUS_CFG.get(status,('','#6B7280','#F3F4F6','?'))
        with st.expander(f"{ni} {req['ref_number']} — {req['project_name']}", expanded=(needs is not None)):
            c1,c2=st.columns([3,2])
            with c1:
                st.markdown(f"""<div style="margin-bottom:.75rem;">
                  <div style="display:flex;gap:.5rem;flex-wrap:wrap;align-items:center;margin-bottom:.4rem;">
                    <span class="ref">{req['ref_number']}</span>{status_badge(status)}{outcome_badge(req.get('sbd_outcome'))}
                  </div>
                  <div style="font-weight:600;font-size:.92rem;">{req['project_name']}</div>
                  <div style="font-size:.75rem;color:#94A3B8;">{fdate_short(req['created_at'])} · Risk: <strong style="color:#EF4444;">{req.get('score_pct',0):.0f}%</strong></div>
                  <div style="margin-top:.5rem;font-size:.8rem;font-weight:600;color:{color};">{ni} {nl}</div>
                </div>""", unsafe_allow_html=True)
            with c2:
                if st.button("View Full Request", key=f"arv_{req['id']}"):
                    st.session_state.selected_req=req['id']; st.session_state.page="request_detail"; st.rerun()
            people_map={'architect':architects,'engineer':engineers,'assurance':assurance_users}
            people=people_map.get(needs,[])
            fld_map={'architect':'architect_id','engineer':'engineer_id','assurance':'assurance_id'}
            ns_map={'architect':'architect_assigned','engineer':'engineer_assigned','assurance':'assurance_assigned'}
            if needs and people:
                opts={p['id']:f"{p['name']}  ({p.get('department','')}) · @{p['username']}" for p in people}
                cur=req.get(fld_map.get(needs,''))
                ca,cb=st.columns([3,1])
                with ca: sel=st.selectbox(f"Select {needs.title()}",list(opts.keys()),format_func=lambda x:opts[x],key=f"asel_{needs}_{req['id']}",index=list(opts.keys()).index(cur) if cur in opts else 0,label_visibility="collapsed")
                with cb:
                    if st.button("Assign →",key=f"abtn_{needs}_{req['id']}",type="primary",use_container_width=True):
                        c2=db(); c2.execute(f"UPDATE requests SET {fld_map[needs]}=? WHERE id=?",(sel,req['id'])); c2.commit(); c2.close()
                        update_status(req['id'],ns_map[needs],user['id'],f"Assigned to {opts[sel][:30]}")
                        st.success("✅ Assigned successfully!"); st.rerun()
            elif needs: st.warning(f"No users with role '{needs}' found. Add them in User Management.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SIGN-OFF QUEUE
# ══════════════════════════════════════════════════════════════════════════════

def page_signoff(user):
    if user['role'] not in ['admin','sbd_manager']: st.error("Access denied."); return
    st.markdown('<div class="pg-header"><div><div class="pg-title">Sign-Off Queue</div><div class="pg-sub">Requests ready for final SbD sign-off</div></div></div>', unsafe_allow_html=True)
    reqs=reqs_by_status(['assurance_completed','pending_signoff'])
    if not reqs: st.info("Sign-off queue is empty."); return
    for req in reqs:
        c1,c2,c3=st.columns([4,2,2])
        with c1:
            st.markdown(f"""<div style="padding:.75rem .875rem;border:1px solid #E2E8F0;border-radius:8px;">
              <div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:.35rem;">{status_badge(req['status'])}{outcome_badge(req.get('sbd_outcome'))}</div>
              <div style="font-weight:600;">{req['project_name']} <span class="ref" style="margin-left:.4rem;">{req['ref_number']}</span></div>
              <div style="font-size:.75rem;color:#94A3B8;margin-top:.15rem;">{fdate_short(req['created_at'])}</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown("<br>", unsafe_allow_html=True)
            if req['status']=='assurance_completed':
                if st.button("➡ Move to Sign-off",key=f"sov_{req['id']}",type="primary",use_container_width=True):
                    update_status(req['id'],'pending_signoff',user['id'],'Moved to sign-off'); st.rerun()
        with c3:
            st.markdown("<br>", unsafe_allow_html=True)
            b1,b2=st.columns(2)
            with b1:
                if st.button("View",key=f"sovw_{req['id']}"):
                    st.session_state.selected_req=req['id']; st.session_state.page="request_detail"; st.rerun()
            with b2:
                if req['status']=='pending_signoff':
                    if st.button("🎉 Sign Off",key=f"soso_{req['id']}",type="primary"):
                        update_status(req['id'],'signoff_received',user['id'],'Sign-off received',{'signoff_by':user['id']}); st.success("Sign-off recorded."); st.rerun()
        st.markdown("<div style='margin:.25rem 0;'>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: ALL REQUESTS
# ══════════════════════════════════════════════════════════════════════════════

def page_all_requests(user):
    if user['role'] not in ['admin','sbd_manager']: st.error("Access denied."); return
    st.markdown('<div class="pg-header"><div><div class="pg-title">All Requests</div><div class="pg-sub">Complete view of all SbD requests across the programme</div></div></div>', unsafe_allow_html=True)
    c1,c2,c3=st.columns([2,2,2])
    with c1: sf=st.selectbox("Status",["All"]+list(STATUS_CFG.keys()))
    with c2: of=st.selectbox("Outcome",["All","no_sbd","sbd_stage1","sbd_stage2","full_sbd"])
    with c3: search=st.text_input("Search","",placeholder="Name or reference...")
    reqs=all_reqs(sf if sf!="All" else None)
    if of!="All": reqs=[r for r in reqs if r.get('sbd_outcome')==of]
    if search: s=search.lower(); reqs=[r for r in reqs if s in r['project_name'].lower() or s in r['ref_number'].lower()]
    st.markdown(f'<div style="font-size:.78rem;color:#64748B;margin-bottom:.875rem;"><strong style="color:#0F172A;">{len(reqs)}</strong> requests</div>', unsafe_allow_html=True)
    for req in reqs:
        c1,c2,c3,c4,c5=st.columns([2,4,2,1,1])
        with c1: st.markdown(f'<span class="ref">{req["ref_number"]}</span>', unsafe_allow_html=True)
        with c2: st.markdown(f"**{req['project_name'][:42]}**"); st.caption(fdate_short(req['created_at']))
        with c3: st.markdown(status_badge(req['status'])+" "+outcome_badge(req.get('sbd_outcome')), unsafe_allow_html=True)
        with c4: st.caption(f"{req.get('score_pct',0):.0f}%")
        with c5:
            if st.button("→", key=f"all_{req['id']}", use_container_width=True):
                st.session_state.selected_req=req['id']; st.session_state.page="request_detail"; st.rerun()
        st.markdown("<div style='border-bottom:1px solid #F8FAFC;margin:.1rem 0;'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: ADMIN — QUESTION BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def page_admin(user):
    if user['role']!='admin': st.error("Admin only."); return
    st.markdown('<div class="pg-header"><div><div class="pg-title">Question Builder</div><div class="pg-sub">Configure assessment questions, nesting, staging, and scoring</div></div></div>', unsafe_allow_html=True)
    tab1,tab2,tab3=st.tabs(["📝 Questions","🌿 Nesting Preview","⚖️ Scoring Thresholds"])
    with tab1: _admin_questions()
    with tab2: _admin_nesting_preview()
    with tab3: _admin_thresholds()

def _admin_questions():
    qs = all_questions()
    c1,c2=st.columns([4,1])
    with c1: st.markdown(f'**{len(qs)}** questions configured &nbsp;·&nbsp; {sum(1 for q in qs if q["is_active"])} active')
    with c2:
        if st.button("➕ Add Question", type="primary", use_container_width=True):
            st.session_state.show_add_q=True

    if st.session_state.get('show_add_q'):
        with st.expander("➕ New Question", expanded=True): _q_form(None, qs)

    st.markdown("---")
    for q in qs:
        opts=json.loads(q['options']) if isinstance(q['options'],str) else (q['options'] or [])
        wts=json.loads(q['weights']) if isinstance(q['weights'],str) else (q['weights'] or [])
        active_icon="🟢" if q['is_active'] else "⬜"
        stage_badge={'all':'<span style="background:#ECFDF5;color:#065F46;font-size:.65rem;padding:.1rem .4rem;border-radius:4px;font-weight:700;">ALL STAGES</span>',
                     'stage1_plus':'<span style="background:#FFFBEB;color:#92400E;font-size:.65rem;padding:.1rem .4rem;border-radius:4px;font-weight:700;">STAGE 1+</span>',
                     'stage2_plus':'<span style="background:#FEF2F2;color:#991B1B;font-size:.65rem;padding:.1rem .4rem;border-radius:4px;font-weight:700;">STAGE 2+</span>'}.get(q.get('stage_visibility','all'),'')
        nest_badge=f'<span style="background:#F5F3FF;color:#6D28D9;font-size:.65rem;padding:.1rem .4rem;border-radius:4px;font-weight:700;">↳ NESTED</span>' if q.get('parent_question_id') else ''

        with st.expander(f"{active_icon} Q{q['order_index']} · {q['text'][:55]}..."):
            st.markdown(f"**Category:** {q['category']} &nbsp;{stage_badge} {nest_badge}", unsafe_allow_html=True)
            if q.get('parent_question_id'):
                parent = next((x for x in all_questions() if x['id']==q['parent_question_id']), None)
                if parent: st.caption(f"↳ Shown when: '{parent['text'][:50]}...' = '{q.get('trigger_answer','')}'")
            for opt,wt in zip(opts,wts):
                bar_w = int((wt/q['max_score']*100)) if q['max_score'] else 0
                bc="#EF4444" if bar_w>=70 else ("#F59E0B" if bar_w>=40 else "#10B981")
                st.markdown(f'<div style="display:flex;align-items:center;gap:.75rem;padding:.25rem 0;border-bottom:1px solid #F8FAFC;"><span style="flex:1;font-size:.82rem;">{opt}</span><span style="font-family:monospace;font-size:.78rem;color:{bc};font-weight:700;min-width:40px;text-align:right;">{wt} pts</span><div style="width:80px;background:#F1F5F9;border-radius:999px;height:4px;"><div style="background:{bc};height:4px;border-radius:999px;width:{bar_w}%;"></div></div></div>', unsafe_allow_html=True)
            cc1,cc2,cc3=st.columns([1,1,3])
            with cc1:
                if st.button("✏️ Edit", key=f"qed_{q['id']}"): st.session_state[f"qe_{q['id']}"]=True
            with cc2:
                lbl="🚫 Deactivate" if q['is_active'] else "✅ Activate"
                if st.button(lbl, key=f"qtg_{q['id']}"):
                    c2=db(); c2.execute("UPDATE questions SET is_active=? WHERE id=?",(0 if q['is_active'] else 1,q['id'])); c2.commit(); c2.close(); st.rerun()
            if st.session_state.get(f"qe_{q['id']}"): _q_form(q, all_questions())

def _admin_nesting_preview():
    qs = [q for q in all_questions() if q['is_active']]
    roots = [q for q in qs if not q.get('parent_question_id')]
    child_map = {}
    for q in qs:
        if q.get('parent_question_id'): child_map.setdefault(q['parent_question_id'],[]).append(q)

    st.markdown("**Visual tree of question dependencies:**")
    for q in roots:
        stage_lbl = {'all':'All stages','stage1_plus':'Stage 1+','stage2_plus':'Stage 2+'}.get(q.get('stage_visibility','all'),'')
        st.markdown(f"""<div style="padding:.625rem .875rem;border:1px solid #E2E8F0;border-left:3px solid #3B82F6;border-radius:8px;margin-bottom:.375rem;background:#F8FAFC;">
          <div style="font-size:.72rem;color:#3B82F6;font-weight:700;text-transform:uppercase;">Q{q['order_index']} · {q['category']} · {stage_lbl}</div>
          <div style="font-size:.87rem;font-weight:600;color:#0F172A;">{q['text']}</div>
        </div>""", unsafe_allow_html=True)
        for child in child_map.get(q['id'],[]):
            st.markdown(f"""<div style="padding:.5rem .875rem;border:1px solid #E9D5FF;border-left:3px solid #8B5CF6;border-radius:8px;margin-bottom:.375rem;margin-left:2rem;background:#FEFBFF;">
              <div style="font-size:.68rem;color:#8B5CF6;font-weight:700;">↳ IF "{child.get('trigger_answer','?')}"</div>
              <div style="font-size:.84rem;font-weight:600;color:#0F172A;">{child['text']}</div>
            </div>""", unsafe_allow_html=True)

def _q_form(q, all_qs):
    is_edit = q is not None
    pfx = f"qe_{q['id']}_" if is_edit else "qn_"

    stage_options = ['all','stage1_plus','stage2_plus']
    stage_labels = {'all':'All stages (always shown)','stage1_plus':'Stage 1+ (SBD engagement confirmed)','stage2_plus':'Stage 2+ (Standard or Full SBD)'}

    root_qs = [x for x in all_qs if not x.get('parent_question_id') and (not is_edit or x['id']!=q['id'])]
    parent_options = [None] + [x['id'] for x in root_qs]
    parent_labels = {None:'None (top-level question)'}
    parent_labels.update({x['id']:f"Q{x['order_index']}: {x['text'][:50]}..." for x in root_qs})

    with st.form(f"qform_{pfx}"):
        text = st.text_input("Question *", value=q['text'] if is_edit else "")
        desc = st.text_input("Description / subtitle", value=q.get('description','') if is_edit else "")
        hint = st.text_input("Hint (optional)", value=q.get('hint','') if is_edit else "", placeholder="Tip shown to assessors only")

        cc1,cc2,cc3 = st.columns(3)
        with cc1: cat = st.text_input("Category", value=q.get('category','General') if is_edit else "General")
        with cc2: order = st.number_input("Order", value=q.get('order_index',0) if is_edit else 0, min_value=0)
        with cc3: active = st.checkbox("Active", value=bool(q.get('is_active',1)) if is_edit else True)

        stage_vis = st.selectbox("Stage Visibility",
            options=stage_options,
            format_func=lambda x: stage_labels[x],
            index=stage_options.index(q.get('stage_visibility','all')) if is_edit else 0)

        st.markdown("**Conditional Display** *(optional)*")
        parent_sel = st.selectbox("Parent Question (show this Q only if parent has specific answer)",
            options=parent_options, format_func=lambda x: parent_labels.get(x,'None'),
            index=parent_options.index(q.get('parent_question_id')) if is_edit and q.get('parent_question_id') in parent_options else 0)

        trigger_ans = ""
        if parent_sel:
            parent_q = next((x for x in all_qs if x['id']==parent_sel), None)
            if parent_q:
                parent_opts = json.loads(parent_q['options']) if isinstance(parent_q['options'],str) else parent_q['options']
                cur_trigger = q.get('trigger_answer','') if is_edit else ''
                tidx = parent_opts.index(cur_trigger) if cur_trigger in parent_opts else 0
                trigger_ans = st.selectbox("Show when parent answer equals", parent_opts, index=tidx)
        elif is_edit:
            trigger_ans = None

        st.markdown("**Answer Options & Risk Weights**")
        ex_opts = json.loads(q['options']) if is_edit and isinstance(q['options'],str) else (q['options'] if is_edit else ["No","Yes - minor","Yes - moderate","Yes - significant"])
        ex_wts  = json.loads(q['weights']) if is_edit and isinstance(q['weights'],str) else (q['weights'] if is_edit else [0,3,6,10])
        num_opts = st.number_input("Number of options", min_value=2, max_value=8, value=len(ex_opts), key=f"nopt_{pfx}")

        new_opts=[]; new_wts=[]
        for i in range(int(num_opts)):
            co,cw = st.columns([4,1])
            with co: new_opts.append(st.text_input(f"Option {i+1}", value=ex_opts[i] if i<len(ex_opts) else "", key=f"opt_{pfx}{i}"))
            with cw: new_wts.append(st.number_input("Score", value=int(ex_wts[i]) if i<len(ex_wts) else 0, min_value=0, max_value=100, key=f"wt_{pfx}{i}", label_visibility="collapsed"))

        cs,cc = st.columns([1,4])
        with cs: saved = st.form_submit_button("💾 Save", type="primary")
        with cc: cancel = st.form_submit_button("Cancel")

        if saved:
            if not text.strip(): st.error("Question text required.")
            elif not all(o.strip() for o in new_opts): st.error("All options need text.")
            else:
                ms = max(new_wts) if new_wts else 10
                now = datetime.now().isoformat()
                if is_edit:
                    c2=db()
                    c2.execute("""UPDATE questions SET text=?,description=?,hint=?,options=?,weights=?,max_score=?,
                                  category=?,stage_visibility=?,parent_question_id=?,trigger_answer=?,
                                  order_index=?,is_active=?,updated_at=? WHERE id=?""",
                               (text,desc,hint,json.dumps(new_opts),json.dumps(new_wts),ms,cat,stage_vis,
                                parent_sel if parent_sel else None, trigger_ans if parent_sel else None,
                                order,int(active),now,q['id']))
                    c2.commit(); c2.close()
                    st.session_state[f"qe_{q['id']}"]=False
                else:
                    c2=db()
                    c2.execute("""INSERT INTO questions (text,description,hint,question_type,options,weights,max_score,
                                  category,stage_visibility,parent_question_id,trigger_answer,is_active,order_index,created_at,updated_at)
                                  VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?,?,?)""",
                               (text,desc,hint,'single_choice',json.dumps(new_opts),json.dumps(new_wts),ms,cat,
                                stage_vis,parent_sel if parent_sel else None,
                                trigger_ans if parent_sel else None,order,now,now))
                    c2.commit(); c2.close()
                    st.session_state.show_add_q=False
                st.success("Question saved."); st.rerun()
        if cancel:
            if is_edit: st.session_state[f"qe_{q['id']}"]=False
            else: st.session_state.show_add_q=False
            st.rerun()

def _admin_thresholds():
    cfg = get_cfg()
    st.markdown("### Scoring Thresholds")
    st.markdown('<div class="alert alert-info">Thresholds are percentage-based. The system calculates the percentage of the maximum possible score achieved and maps it to an SbD outcome.</div>', unsafe_allow_html=True)
    with st.form("thresh"):
        t1=st.slider("🟢 No SBD Required — scores up to (%)",5,50,int(float(cfg.get('threshold_no_sbd',20))))
        t2=st.slider("🟡 SBD Stage 1 — scores up to (%)",10,60,int(float(cfg.get('threshold_stage1',40))))
        t3=st.slider("🟠 SBD Stage 2 — scores up to (%)",30,90,int(float(cfg.get('threshold_stage2',65))))
        st.markdown(f"""<div class="card card-sm" style="margin-top:.875rem;">
          <div style="font-weight:700;font-size:.78rem;margin-bottom:.625rem;">Preview</div>
          <div style="display:flex;gap:.5rem;flex-wrap:wrap;">
            <span style="background:#F9FAFB;color:#374151;padding:.3rem .75rem;border-radius:999px;font-size:.78rem;font-weight:600;border:1px solid #E5E7EB;">0–{t1}% → No SBD</span>
            <span style="background:#FFFBEB;color:#78350F;padding:.3rem .75rem;border-radius:999px;font-size:.78rem;font-weight:600;border:1px solid #FDE68A;">{t1+1}–{t2}% → Stage 1</span>
            <span style="background:#FEF2F2;color:#7F1D1D;padding:.3rem .75rem;border-radius:999px;font-size:.78rem;font-weight:600;border:1px solid #FECACA;">{t2+1}–{t3}% → Stage 2</span>
            <span style="background:#F5F3FF;color:#4C1D95;padding:.3rem .75rem;border-radius:999px;font-size:.78rem;font-weight:600;border:1px solid #DDD6FE;">{t3+1}–100% → Full SBD</span>
          </div>
        </div>""", unsafe_allow_html=True)
        if st.form_submit_button("💾 Save Thresholds", type="primary"):
            if t1<t2<t3:
                set_cfg('threshold_no_sbd',str(t1)); set_cfg('threshold_stage1',str(t2)); set_cfg('threshold_stage2',str(t3))
                st.success("Thresholds updated."); st.rerun()
            else: st.error("Thresholds must be in ascending order.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: USER MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def page_users(user):
    if user['role']!='admin': st.error("Admin only."); return
    st.markdown('<div class="pg-header"><div><div class="pg-title">User Management</div><div class="pg-sub">Manage portal users, roles, and access levels</div></div></div>', unsafe_allow_html=True)
    tab1,tab2=st.tabs(["👥 All Users","➕ Add User"])
    with tab1:
        users=all_users(); rf=st.selectbox("Filter by role",["All"]+ROLES)
        if rf!="All": users=[u for u in users if u['role']==rf]
        st.markdown(f'**{len(users)}** users')
        for u in users:
            c1,c2,c3,c4=st.columns([3,2,2,1])
            with c1:
                dept = f" · {u['department']}" if u.get('department') else ''
                st.markdown(f"""<div style="display:flex;align-items:center;gap:.625rem;">
                  <div style="width:32px;height:32px;background:linear-gradient(135deg,#3B82F6,#8B5CF6);border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-weight:700;font-size:.82rem;flex-shrink:0;">{u['name'][0]}</div>
                  <div><div style="font-weight:600;font-size:.87rem;">{u['name']}</div><div style="font-size:.72rem;color:#94A3B8;">@{u['username']}{dept}</div></div>
                </div>""", unsafe_allow_html=True)
            with c2: st.caption(u['email'])
            with c3:
                nr=st.selectbox("",ROLES,index=ROLES.index(u['role']) if u['role'] in ROLES else 0,key=f"ur_{u['id']}",format_func=lambda r:ROLE_LABELS.get(r,r),label_visibility="collapsed")
                if nr!=u['role']:
                    if st.button("Save",key=f"usr_{u['id']}"): exe("UPDATE users SET role=? WHERE id=?",(nr,u['id'])); st.success("Role updated."); st.rerun()
            with c4:
                if u['id']!=user['id']:
                    if st.button("🗑",key=f"udd_{u['id']}"): exe("UPDATE users SET is_active=0 WHERE id=?",(u['id'],)); st.rerun()
            st.markdown("<div style='border-bottom:1px solid #F8FAFC;margin:.2rem 0;'></div>", unsafe_allow_html=True)
    with tab2:
        with st.form("adduser"):
            ca,cb=st.columns(2)
            with ca: name=st.text_input("Full Name *"); username=st.text_input("Username *")
            with cb: email=st.text_input("Email *"); password=st.text_input("Password *",type="password")
            dept=st.text_input("Department"); role=st.selectbox("Role",ROLES,format_func=lambda r:ROLE_LABELS.get(r,r))
            if st.form_submit_button("➕ Create User",type="primary"):
                if not all([name,username,email,password]): st.error("All required fields must be filled.")
                elif '@' not in email: st.error("Invalid email.")
                elif len(password)<6: st.error("Password must be at least 6 characters.")
                else:
                    ok,msg=create_user(username,password,name,email,role,dept)
                    st.success(f"User '{name}' created!") if ok else st.error(msg)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════

init_db()
inject_css()

for k,v in [("authenticated",False),("user",None),("page","dashboard")]:
    if k not in st.session_state: st.session_state[k]=v

if not st.session_state.authenticated:
    login_page()
else:
    user = st.session_state.user
    render_sidebar(user)
    page = st.session_state.page
    pages = {
        "dashboard":      page_dashboard,
        "my_requests":    page_my_requests,
        "new_request":    page_new_request,
        "assigned":       page_assigned,
        "pending_review": page_pending_review,
        "assign_resources": page_assign_resources,
        "signoff_queue":  page_signoff,
        "all_requests":   page_all_requests,
        "admin_panel":    page_admin,
        "user_management": page_users,
        "request_detail": page_request_detail,
    }
    fn = pages.get(page, page_dashboard)
    fn(user)
