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
    st.session_state.current_tool_selection = "retrieval"  # Track current tool


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
            st.session_state.current_tool_selection = "retrieval"  # Reset tool on login
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
    disease_name: str = None,
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
            "disease_name": disease_name if selected_tool == "treatment_comparison" else None,
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
    # MAIN CHAT INTERFACE - Sidebar with User Info at Top
    with st.sidebar:
        # User Info at Top
        st.markdown("### 👤 User Session")
        st.markdown(
            f"<span class='status-chip'>User: {st.session_state.username}</span>",
            unsafe_allow_html=True
        )
        st.markdown(
            f"<span class='status-chip'>Role: {st.session_state.user_role}</span>",
            unsafe_allow_html=True
        )
        
        # Buttons at Top
        col_new, col_logout = st.columns([1, 1])
        with col_new:
            if st.button("🔄 New Chat", use_container_width=True, key="new_chat_btn"):
                upsert_current_conversation_snapshot()
                st.session_state.conversation_id = None
                st.session_state.chat_history = []
                st.session_state.last_summarized_patient = None
                st.rerun()
        
        with col_logout:
            if st.button("🚪 Logout", use_container_width=True, key="logout_btn"):
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
        
        # Session Info
        st.markdown("### 📊 Current Session")
        st.markdown(f"**Conversation ID:** {st.session_state.conversation_id if st.session_state.conversation_id else 'New'}")
        st.markdown(f"**Messages:** {len([m for m in st.session_state.chat_history if m['sender'] == 'user'])}")
        st.divider()
    
    # Main Title
    st.markdown("<h2 class='title-clean'>🏥 Healthcare Clinical Assistant</h2>", unsafe_allow_html=True)
    
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
    
    # ========== INITIALIZE TOOL VARIABLES ==========
    # Filter tools based on role
    if st.session_state.user_role == "Admin":
        available_tools = ["retrieval", "medical_knowledge"]
    elif st.session_state.user_role == "Doctor":
        available_tools = ["retrieval", "summarization", "medical_knowledge", "treatment_comparison", "diagnosis_recommendation"]
    else:
        available_tools = ["retrieval", "summarization", "medical_knowledge", "treatment_comparison"]

    # Initialize variables for tool-specific settings
    patient_name = None
    selected_knowledge_type = "condition"
    use_rag_for_knowledge = False
    selected_disease = None
    
    # Get current tool selection (from session state for persistence)
    if "current_tool_selection" not in st.session_state:
        st.session_state.current_tool_selection = available_tools[0]
    
    # ========== CHAT HISTORY DISPLAY ==========
    # ========== SCROLLABLE CHAT DISPLAY AREA ==========
    st.markdown("""
        <style>
        .chat-container {
            height: 460px;
            overflow-y: auto;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 12px;
        }
        </style>
    """, unsafe_allow_html=True)
    
    chat_container = st.container(border=True)
    
    with chat_container:
        if st.session_state.chat_history:
            # Display chat history in forward order (messages grow downward)
            for chat in st.session_state.chat_history:
                if chat["sender"] == "user":
                    with st.chat_message("user"):
                        st.write(chat["message"])
                else:
                    with st.chat_message("assistant"):
                        st.write(chat["message"])
            # Auto-scroll to bottom by adding empty space that pushes content up
            st.markdown("---")  # Visual separator
        else:
            st.markdown(
                "<div class='hint-box'>Start a conversation by typing a message below or selecting a patient for summarization.</div>",
                unsafe_allow_html=True,
            )
    
    st.write("")  # Add spacing
    
    # ========== CHAT INPUT & TOOL SELECTOR SIDE BY SIDE (FIXED AT BOTTOM) ==========
    col_input, col_tool = st.columns([0.7, 0.3], gap="small")
    
    with col_input:
        selected_tool = st.session_state.current_tool_selection
        if selected_tool in ["retrieval", "medical_knowledge", "treatment_comparison", "diagnosis_recommendation"]:
            if selected_tool == "retrieval":
                input_label = "Ask a clinical question..."
            elif selected_tool == "medical_knowledge":
                input_label = "Ask a general medical question..."
            elif selected_tool == "treatment_comparison":
                input_label = "Ask about treatment options..."
            else:
                input_label = "Enter symptoms to get possible diagnoses and recommendations..."
        else:
            input_label = "Type your message..."
        
        user_input = st.chat_input(input_label)
    
    with col_tool:
        selected_tool = st.selectbox(
            "Tool",
            available_tools,
            index=available_tools.index(st.session_state.current_tool_selection),
            format_func=lambda x: (
                "📚 Retrieval" if x == "retrieval" else
                "📋 Summarization" if x == "summarization" else
                "🧠 Knowledge" if x == "medical_knowledge" else
                "💊 Treatment" if x == "treatment_comparison" else
                "🩺 Diagnosis"
            ),
            key="tool_selector",
            label_visibility="collapsed"
        )
        st.session_state.current_tool_selection = selected_tool
    
    st.write("")  # Add spacing after input
    
    # ========== TOOL-SPECIFIC SETTINGS ==========
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
    
    elif selected_tool == "treatment_comparison":
        diseases = [
            "Type 2 Diabetes Mellitus",
            "Hypertensive Heart Disease",
            "Community-Acquired Pneumonia",
            "Major Depressive Disorder",
            "Rheumatoid Arthritis"
        ]
        selected_disease = st.selectbox(
            "Select Disease",
            diseases,
            key="disease_selector"
        )
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
                selected_disease,
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
                conv_summary = f"Conversation {idx + 1} - {len([m for m in conv.get('chat_history', []) if m['sender'] == 'user'])} msgs"
                
                if st.button(f"📝 {conv_summary}", use_container_width=True, key=f"load_conv_{idx}"):
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
