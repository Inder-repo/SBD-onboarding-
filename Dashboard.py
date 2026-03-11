import sys, os
_app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

import streamlit as st
from database import get_stats, get_all_requests, get_user_requests
from utils import status_badge, format_date, outcome_badge, get_status_pipeline

def show_dashboard(user):
    st.markdown("""
    <div class="page-header">
        <div class="page-title">🏠 Dashboard</div>
        <div class="page-subtitle">Overview of Secure by Design activities</div>
    </div>
    """, unsafe_allow_html=True)
    
    stats = get_stats()
    
    # Top stats row
    cols = st.columns(6)
    stat_items = [
        ("Total Requests", stats['total'], "📋"),
        ("Pending Review", stats['pending_review'], "⏳"),
        ("Awaiting Assignment", stats['awaiting_assignment'], "👤"),
        ("In Progress", stats['in_progress'], "⚙️"),
        ("Pending Sign-off", stats['pending_signoff'], "✍️"),
        ("Completed", stats['completed'], "✅"),
    ]
    
    for col, (label, value, icon) in zip(cols, stat_items):
        with col:
            st.markdown(f"""
            <div class="stat-card">
                <div style="font-size:1.5rem;margin-bottom:0.25rem;">{icon}</div>
                <div class="stat-number">{value}</div>
                <div class="stat-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_left, col_right = st.columns([3, 2])
    
    with col_left:
        st.markdown("### Recent Requests")
        
        if user['role'] in ['admin', 'sbd_manager']:
            requests = get_all_requests()[:10]
        else:
            requests = get_user_requests(user['id'])[:10]
        
        if not requests:
            st.markdown("""
            <div class="card" style="text-align:center;padding:2rem;color:#94a3b8;">
                <div style="font-size:2rem;margin-bottom:0.5rem;">📭</div>
                No requests yet. Create your first SbD request!
            </div>
            """, unsafe_allow_html=True)
        else:
            for req in requests:
                pipeline_html = _mini_pipeline(req['status'])
                st.markdown(f"""
                <div class="card" style="cursor:pointer;margin-bottom:0.75rem;padding:1rem 1.25rem;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
                        <span class="ref-number">{req['ref_number']}</span>
                        {status_badge(req['status'])}
                    </div>
                    <div style="font-weight:600;color:#0f172a;margin-bottom:0.25rem;">{req['project_name']}</div>
                    <div style="font-size:0.8rem;color:#64748b;margin-bottom:0.75rem;">
                        Created {format_date(req['created_at'])}
                        {f" · {outcome_badge(req['sbd_outcome'])}" if req.get('sbd_outcome') else ''}
                    </div>
                    {pipeline_html}
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"View {req['ref_number']}", key=f"dash_view_{req['id']}", use_container_width=False):
                    st.session_state.selected_request_id = req['id']
                    st.session_state.page = "request_detail"
                    st.rerun()
    
    with col_right:
        st.markdown("### SbD Outcomes")
        
        outcome_data = [
            ("No SBD Needed", stats['outcome_no_sbd'], "#94a3b8", "🟢"),
            ("SBD Stage 1", stats['outcome_sbd_stage1'], "#fbbf24", "🟡"),
            ("SBD Stage 2", stats['outcome_sbd_stage2'], "#f97316", "🟠"),
            ("Full SBD", stats['outcome_full_sbd'], "#ef4444", "🔴"),
        ]
        
        total_with_outcome = sum(v for _, v, _, _ in outcome_data)
        
        for label, count, color, emoji in outcome_data:
            pct = (count / total_with_outcome * 100) if total_with_outcome > 0 else 0
            st.markdown(f"""
            <div style="margin-bottom:0.75rem;">
                <div style="display:flex;justify-content:space-between;margin-bottom:0.25rem;">
                    <span style="font-size:0.85rem;font-weight:500;">{emoji} {label}</span>
                    <span style="font-family:'JetBrains Mono';font-size:0.85rem;font-weight:700;">{count}</span>
                </div>
                <div style="background:#e2e8f0;border-radius:999px;height:6px;">
                    <div style="background:{color};height:6px;border-radius:999px;width:{pct:.1f}%;transition:width 0.3s;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("### Quick Actions")
        
        if st.button("➕ New SbD Request", use_container_width=True, type="primary"):
            st.session_state.page = "new_request"
            st.rerun()
        
        if user['role'] in ['admin', 'sbd_manager']:
            if st.button("📥 Review Pending", use_container_width=True):
                st.session_state.page = "pending_review"
                st.rerun()
            
            if st.button("👥 Assign Resources", use_container_width=True):
                st.session_state.page = "assign_resources"
                st.rerun()

def _mini_pipeline(current_status):
    steps = get_status_pipeline()
    step_keys = [s['key'] for s in steps]
    
    try:
        current_idx = next(i for i, s in enumerate(steps) if s['key'] == current_status)
    except StopIteration:
        current_idx = -1
    
    dots_html = ""
    for i, step in enumerate(steps[:8]):  # show first 8 steps
        if i < current_idx:
            cls = "done"
            icon = "✓"
        elif i == current_idx:
            cls = "active"
            icon = step['icon']
        else:
            cls = ""
            icon = ""
        
        if i > 0:
            line_cls = "done" if i <= current_idx else ""
            dots_html += f'<div class="pipe-line {line_cls}"></div>'
        
        dots_html += f'<div class="pipe-step"><div class="pipe-dot {cls}">{icon}</div></div>'
    
    return f'<div class="pipeline" style="margin:0;">{dots_html}</div>'
