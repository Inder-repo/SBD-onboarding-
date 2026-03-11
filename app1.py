import streamlit as st
from datetime import datetime
import json

# Must be first Streamlit command
st.set_page_config(
    page_title="Secure by Design Portal",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded"
)

from database import init_db
from auth import login_page, get_current_user, logout
from styles import inject_styles

# Initialize database
init_db()

# Inject custom styles
inject_styles()

# Session state initialization
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "dashboard"

def main():
    if not st.session_state.authenticated:
        login_page()
        return

    user = st.session_state.user
    
    # Sidebar navigation
    with st.sidebar:
        st.markdown(f"""
        <div class="sidebar-header">
            <div class="sidebar-logo">🔐</div>
            <div class="sidebar-title">SbD Portal</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="user-badge">
            <span class="user-avatar">{user['name'][0].upper()}</span>
            <div>
                <div class="user-name">{user['name']}</div>
                <div class="user-role">{user['role'].replace('_', ' ').title()}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Navigation
        nav_items = [
            ("🏠", "Dashboard", "dashboard"),
            ("📋", "My Requests", "my_requests"),
            ("➕", "New Request", "new_request"),
        ]
        
        if user['role'] in ['sbd_manager', 'admin']:
            nav_items += [
                ("📥", "Pending Review", "pending_review"),
                ("👥", "Assign Resources", "assign_resources"),
                ("✅", "Sign-Off Queue", "signoff_queue"),
                ("📊", "All Requests", "all_requests"),
            ]
        
        if user['role'] == 'admin':
            nav_items += [
                ("⚙️", "Admin Panel", "admin_panel"),
                ("👤", "User Management", "user_management"),
            ]
        
        for icon, label, page_key in nav_items:
            active_class = "nav-active" if st.session_state.page == page_key else ""
            if st.button(f"{icon}  {label}", key=f"nav_{page_key}", 
                        use_container_width=True,
                        type="primary" if st.session_state.page == page_key else "secondary"):
                st.session_state.page = page_key
                st.rerun()
        
        st.markdown("---")
        if st.button("🚪  Logout", use_container_width=True):
            logout()
            st.rerun()
    
    # Main content
    page = st.session_state.page
    
    if page == "dashboard":
        from pages.dashboard import show_dashboard
        show_dashboard(user)
    elif page == "my_requests":
        from pages.my_requests import show_my_requests
        show_my_requests(user)
    elif page == "new_request":
        from pages.new_request import show_new_request
        show_new_request(user)
    elif page == "pending_review":
        from pages.pending_review import show_pending_review
        show_pending_review(user)
    elif page == "assign_resources":
        from pages.assign_resources import show_assign_resources
        show_assign_resources(user)
    elif page == "signoff_queue":
        from pages.signoff_queue import show_signoff_queue
        show_signoff_queue(user)
    elif page == "all_requests":
        from pages.all_requests import show_all_requests
        show_all_requests(user)
    elif page == "admin_panel":
        from pages.admin_panel import show_admin_panel
        show_admin_panel(user)
    elif page == "user_management":
        from pages.user_management import show_user_management
        show_user_management(user)
    elif page == "request_detail":
        from pages.request_detail import show_request_detail
        show_request_detail(user)

if __name__ == "__main__":
    main()
