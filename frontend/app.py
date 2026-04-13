import streamlit as st
import requests
import os
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
FRONTEND_DATA_DIR = Path(__file__).parent / ".streamlit_data"
FRONTEND_DATA_DIR.mkdir(exist_ok=True)

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
    .status-chip {
        display: inline-block;
        background-color: #172035;
        border: 1px solid #2d3d63;
        color: #dbe7ff;
        border-radius: 999px;
        padding: 4px 10px;
        margin-right: 8px;
        font-size: 0.85rem;
    }
    .title-clean {
        color: #f8fafc;
        margin-bottom: 0.25rem;
    }
    .hint-box {
        border-left: 4px solid #2b6cb0;
        background: #111a2d;
        color: #d6e3ff;
        padding: 10px 12px;
        border-radius: 8px;
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
    st.session_state.conversations = []  # Store old conversations
    st.session_state.last_summarized_patient = None  # Track last selected patient


def _user_store_file(username: str) -> Path:
    safe_username = "".join(ch for ch in username if ch.isalnum() or ch in ("-", "_"))
    return FRONTEND_DATA_DIR / f"{safe_username}_chat_store.json"


def load_user_conversations(username: str):
    store_file = _user_store_file(username)
    if not store_file.exists():
        return []

    try:
        with open(store_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("conversations", [])
    except Exception:
        return []


def save_user_conversations(username: str):
    if not username:
        return

    store_file = _user_store_file(username)
    payload = {
        "updated_at": datetime.utcnow().isoformat(),
        "conversations": st.session_state.conversations,
    }

    with open(store_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def upsert_current_conversation_snapshot():
    if not st.session_state.username:
        return
    if not st.session_state.chat_history:
        return

    convo_id = st.session_state.conversation_id or int(datetime.utcnow().timestamp())
    snapshot = {
        "conversation_id": convo_id,
        "chat_history": st.session_state.chat_history.copy(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    existing_idx = None
    for idx, convo in enumerate(st.session_state.conversations):
        if convo.get("conversation_id") == convo_id:
            existing_idx = idx
            break

    if existing_idx is None:
        st.session_state.conversations.append(snapshot)
    else:
        st.session_state.conversations[existing_idx] = snapshot

    save_user_conversations(st.session_state.username)


def build_contextual_message(user_message: str, max_turns: int = 6) -> str:
    """Embed recent turns so backend can answer with conversation continuity."""
    recent = st.session_state.chat_history[-max_turns:]
    if not recent:
        return user_message

    transcript_lines = []
    for item in recent:
        role = "User" if item.get("sender") == "user" else "Assistant"
        transcript_lines.append(f"{role}: {item.get('message', '')}")

    transcript = "\n".join(transcript_lines)
    return (
        "Use the following recent conversation context for continuity. "
        "Do not repeat old answers unless needed.\n\n"
        f"Recent context:\n{transcript}\n\n"
        f"Current user question:\n{user_message}"
    )


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
            st.session_state.conversations = load_user_conversations(username)
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


def send_chat_message(
    message: str,
    selected_tool: str,
    patient_name: str = None,
    knowledge_type: str = "condition",
    use_rag: bool = True,
):
    """Send message to chat API"""
    try:
        payload = {
            "conversation_id": st.session_state.conversation_id,
            "user_id": st.session_state.user_id,
            "user_role": st.session_state.user_role,
            "selected_tool": selected_tool,
            "patient_name": patient_name if selected_tool == "summarization" else None,
            "knowledge_type": knowledge_type if selected_tool == "medical_knowledge" else None,
            "use_rag": use_rag if selected_tool == "medical_knowledge" else True,
            "message": message
        }
        
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json=payload
        )
        
        if response.status_code == 200:
            data = response.json()
            st.session_state.conversation_id = data.get("conversation_id")
            upsert_current_conversation_snapshot()
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
    # LOGIN ONLY PAGE
    st.markdown("## 🏥 Healthcare Assistant")
    st.markdown("### Login to Your Account")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        login_username = st.text_input("Username", key="login_username")
        login_password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", key="login_button", use_container_width=True):
            success, message = login_user(login_username, login_password)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

else:
    # MAIN CHAT INTERFACE
    # Header with User Info and Logout
    col1, col2, col3 = st.columns([0.7, 0.15, 0.15])
    
    with col1:
        st.markdown("<h2 class='title-clean'>🏥 Healthcare Clinical Assistant</h2>", unsafe_allow_html=True)
        st.markdown(
            f"<span class='status-chip'>User: {st.session_state.username}</span>"
            f"<span class='status-chip'>Role: {st.session_state.user_role}</span>",
            unsafe_allow_html=True
        )
    
    with col2:
        if st.button("🔄 New Chat", use_container_width=True):
            upsert_current_conversation_snapshot()
            st.session_state.conversation_id = None
            st.session_state.chat_history = []
            st.session_state.last_summarized_patient = None
            st.rerun()
    
    with col3:
        if st.button("🚪 Logout", use_container_width=True):
            upsert_current_conversation_snapshot()
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.session_state.username = None
            st.session_state.user_role = None
            st.session_state.conversation_id = None
            st.session_state.chat_history = []
            st.session_state.conversations = []
            st.rerun()
    st.divider()
    
    # Admin Register Section (only for Admin users)
    if st.session_state.user_role == "Admin":
        with st.expander("👤 Register New User", expanded=False):
            st.markdown("### Register a New Doctor or Nurse")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                reg_username = st.text_input("New Username", key="reg_username_admin")
                reg_password = st.text_input("Password", type="password", key="reg_password_admin")
            
            with col2:
                reg_confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm_admin")
                reg_role = st.selectbox("Role", ["Doctor", "Nurse"], key="reg_role_admin")
            
            with col3:
                st.write("")  # Spacing
                if st.button("Register User", use_container_width=True, key="register_button_admin"):
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
    
    st.divider()
    
    # Tool Selection (Retrieval vs Summarization)
    col1, col2 = st.columns([0.5, 0.5])
    
    with col1:
        # Filter tools based on role
        if st.session_state.user_role == "Admin":
            available_tools = ["retrieval", "medical_knowledge"]
        else:
            available_tools = ["retrieval", "summarization", "medical_knowledge"]

        selected_tool = st.selectbox(
            "Select Tool",
            available_tools,
            format_func=lambda x: (
                "📚 Retrieval (Clinical Guidelines)" if x == "retrieval" else
                "📋 Summarization (Patient Reports)" if x == "summarization" else
                "🧠 Medical Knowledge"
            ),
            key="tool_selector"
        )
    
    patient_name = None
    selected_knowledge_type = "condition"
    use_rag_for_knowledge = False
    with col2:
        if selected_tool == "summarization":
            patients = fetch_patients()
            
            if patients:
                selected_patient = st.selectbox(
                    "Select Patient",
                    patients,
                    key="patient_selector"
                )
                patient_name = selected_patient
                
                # Auto-trigger summarization when patient selection changes
                if patient_name != st.session_state.last_summarized_patient:
                    st.session_state.last_summarized_patient = patient_name
                    
                    with st.spinner(f"Generating summary for {patient_name}..."):
                        success, response = send_chat_message(
                            message="Please provide a summary of this patient's report",
                            selected_tool="summarization",
                            patient_name=patient_name
                        )
                    
                    if success:
                        st.session_state.chat_history.append({
                            "sender": "user",
                            "message": f"Show summary for patient: {patient_name}",
                            "tool": "summarization"
                        })
                        st.session_state.chat_history.append({
                            "sender": "ai",
                            "message": response,
                            "tool": "summarization"
                        })
                        upsert_current_conversation_snapshot()
                        st.rerun()
                    else:
                        st.error(f"Error: {response}")
            else:
                st.warning("No accessible patient reports found for your role.")

        elif selected_tool == "medical_knowledge":
            selected_knowledge_type = st.selectbox(
                "Knowledge Type",
                ["condition", "drug", "symptom", "procedure", "guideline"],
                key="knowledge_type_selector"
            )
            use_rag_for_knowledge = st.toggle(
                "Augment with clinical context",
                value=False,
                key="knowledge_use_rag_toggle"
            )
    
    st.divider()
    
    # Chat History Display
    st.markdown("### 💬 Current Conversation")
    
    if st.session_state.chat_history:
        for chat in st.session_state.chat_history:
            if chat["sender"] == "user":
                with st.chat_message("user"):
                    st.write(chat["message"])
            else:
                with st.chat_message("assistant"):
                    st.write(chat["message"])
    else:
        st.markdown(
            "<div class='hint-box'>Start a conversation by typing a message below or selecting a patient for summarization.</div>",
            unsafe_allow_html=True,
        )
    
    # Chat Input (hidden for summarization mode)
    if selected_tool in ["retrieval", "medical_knowledge"]:
        input_label = "Ask a clinical question..." if selected_tool == "retrieval" else "Ask a general medical question..."
        user_input = st.chat_input(input_label)

        # Process Message
        if user_input and user_input.strip():
            # Add user message to history
            st.session_state.chat_history.append({
                "sender": "user",
                "message": user_input,
                "tool": selected_tool
            })
            
            # Send to backend
            with st.spinner("Processing your question..."):
                success, response = send_chat_message(
                    user_input,
                    selected_tool,
                    None,
                    selected_knowledge_type,
                    use_rag_for_knowledge,
                )
            
            if success:
                # Add AI response to history
                st.session_state.chat_history.append({
                    "sender": "ai",
                    "message": response,
                    "tool": selected_tool
                })
                upsert_current_conversation_snapshot()
                st.rerun()
            else:
                st.error(f"Error: {response}")
    
    # Sidebar with Old Conversations
    with st.sidebar:
        st.markdown("### 📊 Session Info")
        st.markdown(f"**Username:** {st.session_state.username}")
        st.markdown(f"**Role:** {st.session_state.user_role}")
        st.markdown(f"**Conversation ID:** {st.session_state.conversation_id if st.session_state.conversation_id else 'New'}")
        st.markdown(f"**Current Messages:** {len([m for m in st.session_state.chat_history if m['sender'] == 'user'])}")
        
        st.divider()
        
        # Display Old Conversations
        if st.session_state.conversations:
            st.markdown("### 📜 Previous Conversations")
            
            ordered = sorted(
                st.session_state.conversations,
                key=lambda x: x.get("updated_at", ""),
                reverse=True,
            )

            for idx, conv in enumerate(ordered):
                with st.expander(f"Conversation {idx + 1}", expanded=False):
                    st.markdown(f"**ID:** {conv.get('conversation_id', 'N/A')}")
                    st.markdown(f"**Messages:** {len([m for m in conv.get('chat_history', []) if m['sender'] == 'user'])}")
                    
                    st.divider()
                    
                    for chat in conv.get('chat_history', []):
                        if chat["sender"] == "user":
                            st.markdown(f"**👤 You:** {chat['message']}")
                        else:
                            st.markdown(f"**🤖 Assistant:** {chat['message']}")
                        st.divider()
                    
                    if st.button(f"Load Conversation {idx + 1}", key=f"load_conv_{idx}"):
                        st.session_state.conversation_id = conv.get('conversation_id')
                        st.session_state.chat_history = conv.get('chat_history', []).copy()
                        st.rerun()
        
        st.divider()
        st.markdown("### ℹ️ About")
        st.info(
            "This is a clinical assistant powered by RAG technology. "
            "Use **Retrieval** to ask about clinical protocols and guidelines, "
            "or **Summarization** to get a summary of patient reports based on your role permissions."
        )
