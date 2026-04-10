import streamlit as st
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Page Configuration
st.set_page_config(
    page_title="Healthcare Clinical Assistant",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .login-container {
        max-width: 400px;
        margin: 50px auto;
        padding: 30px;
        border-radius: 10px;
        background-color: #f8f9fa;
    }
    .chat-container {
        display: flex;
        flex-direction: column;
        height: 100vh;
    }
    .message-user {
        background-color: #e3f2fd;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    .message-ai {
        background-color: #f3e5f5;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize Session State
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.user_role = None
    st.session_state.conversation_id = None
    st.session_state.chat_history = []
    st.session_state.patients = []


# Helper Functions
def login_user(username: str, password: str):
    """Login user and store session"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/login",
            json={"username": username, "password": password}
        )
        
        if response.status_code == 200:
            data = response.json()
            st.session_state.logged_in = True
            st.session_state.user_id = data.get("user_id")
            st.session_state.username = username
            st.session_state.user_role = data.get("role")
            st.session_state.conversation_id = None
            st.session_state.chat_history = []
            return True, "Login successful!"
        else:
            return False, "Invalid credentials"
    except Exception as e:
        return False, f"Error: {str(e)}"


def register_user(username: str, password: str, role: str):
    """Register new user"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/register",
            json={"username": username, "password": password, "role": role}
        )
        
        if response.status_code == 200:
            return True, "Registration successful! Please login."
        else:
            return False, f"Registration failed: {response.text}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def send_chat_message(message: str, selected_tool: str, patient_name: str = None):
    """Send message to chat API"""
    try:
        payload = {
            "conversation_id": st.session_state.conversation_id,
            "user_id": st.session_state.user_id,
            "user_role": st.session_state.user_role,
            "selected_tool": selected_tool,
            "patient_name": patient_name if selected_tool == "summarization" else None,
            "message": message
        }
        
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json=payload
        )
        
        if response.status_code == 200:
            data = response.json()
            st.session_state.conversation_id = data.get("conversation_id")
            return True, data.get("response")
        else:
            return False, f"Error: {response.text}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def fetch_patients():
    """Fetch list of accessible patients"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/chat/patients",
            params={"user_role": st.session_state.user_role}
        )
        
        if response.status_code == 200:
            data = response.json()
            st.session_state.patients = data.get("patients", [])
            return st.session_state.patients
        else:
            return []
    except Exception as e:
        st.error(f"Error fetching patients: {str(e)}")
        return []


# Main App Logic
if not st.session_state.logged_in:
    # LOGIN / REGISTER PAGE
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.markdown("## 🏥 Healthcare Assistant")
        st.markdown("### Login")
        
        login_username = st.text_input("Username", key="login_username")
        login_password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", key="login_button", use_container_width=True):
            success, message = login_user(login_username, login_password)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)
    
    with col2:
        st.markdown("## 📝 New User?")
        st.markdown("### Register")
        
        reg_username = st.text_input("Username", key="reg_username")
        reg_password = st.text_input("Password", type="password", key="reg_password")
        reg_confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm_password")
        reg_role = st.selectbox("Role", ["Doctor", "Nurse", "Admin"], key="reg_role")
        
        if st.button("Register", key="register_button", use_container_width=True):
            if reg_password != reg_confirm_password:
                st.error("Passwords do not match!")
            elif not reg_username or not reg_password:
                st.error("Please fill all fields!")
            else:
                success, message = register_user(reg_username, reg_password, reg_role)
                if success:
                    st.success(message)
                else:
                    st.error(message)

else:
    # MAIN CHAT INTERFACE
    # Header with User Info and Logout
    col1, col2 = st.columns([0.85, 0.15])
    
    with col1:
        st.markdown(f"## 🏥 Healthcare Clinical Assistant")
        st.markdown(f"**User:** {st.session_state.username} | **Role:** {st.session_state.user_role}")
    
    with col2:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.session_state.username = None
            st.session_state.user_role = None
            st.session_state.conversation_id = None
            st.session_state.chat_history = []
            st.rerun()
    
    st.divider()
    
    # Tool Selection (Retrieval vs Summarization)
    col1, col2 = st.columns([0.5, 0.5])
    
    with col1:
        selected_tool = st.selectbox(
            "Select Tool",
            ["retrieval", "summarization"],
            format_func=lambda x: "📚 Retrieval (Clinical Guidelines)" if x == "retrieval" else "📋 Summarization (Patient Reports)",
            key="tool_selector"
        )
    
    patient_name = None
    with col2:
        if selected_tool == "summarization":
            st.info("Fetching accessible patients...")
            patients = fetch_patients()
            
            if patients:
                patient_name = st.selectbox(
                    "Select Patient",
                    patients,
                    key="patient_selector"
                )
            else:
                st.warning("No accessible patient reports found for your role.")
    
    st.divider()
    
    # Chat History Display
    st.markdown("### 💬 Conversation History")
    
    if st.session_state.chat_history:
        for idx, chat in enumerate(st.session_state.chat_history):
            if chat["sender"] == "user":
                st.markdown(f"**👤 You:** {chat['message']}")
            else:
                st.markdown(f"**🤖 Assistant:** {chat['message']}")
            st.divider()
    else:
        st.info("Start a conversation by typing a message below.")
    
    # Chat Input
    st.markdown("### ✉️ Send Message")
    
    col1, col2 = st.columns([0.9, 0.1])
    
    with col1:
        user_input = st.text_area(
            "Type your message here...",
            height=100,
            key="user_input",
            placeholder="Ask a clinical question or request a patient summary..."
        )
    
    with col2:
        send_button = st.button("Send ➜", use_container_width=True, key="send_button")
    
    # Process Message
    if send_button and user_input.strip():
        # Validate summarization has patient selected
        if selected_tool == "summarization" and not patient_name:
            st.error("Please select a patient for summarization!")
        else:
            # Add user message to history
            st.session_state.chat_history.append({
                "sender": "user",
                "message": user_input,
                "tool": selected_tool
            })
            
            # Send to backend
            with st.spinner("Processing your message..."):
                success, response = send_chat_message(
                    user_input,
                    selected_tool,
                    patient_name
                )
            
            if success:
                # Add AI response to history
                st.session_state.chat_history.append({
                    "sender": "ai",
                    "message": response,
                    "tool": selected_tool
                })
                st.rerun()
            else:
                st.error(f"Error: {response}")
    
    # Sidebar Info
    with st.sidebar:
        st.markdown("### 📊 Session Info")
        st.markdown(f"**Username:** {st.session_state.username}")
        st.markdown(f"**Role:** {st.session_state.user_role}")
        st.markdown(f"**Conversation ID:** {st.session_state.conversation_id if st.session_state.conversation_id else 'New'}")
        st.markdown(f"**Messages Sent:** {len([m for m in st.session_state.chat_history if m['sender'] == 'user'])}")
        
        st.divider()
        st.markdown("### ℹ️ About")
        st.info(
            "This is a clinical assistant powered by RAG technology. "
            "Use **Retrieval** to ask about clinical protocols and guidelines, "
            "or **Summarization** to get a summary of patient reports based on your role permissions."
        )
        
        st.divider()
        
        if st.button("🔄 New Conversation", use_container_width=True):
            st.session_state.conversation_id = None
            st.session_state.chat_history = []
            st.rerun()
