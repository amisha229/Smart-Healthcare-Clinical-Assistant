import streamlit as st
import streamlit.components.v1 as components
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
    st.session_state.auto_scroll_to_latest = False


def fetch_user_conversations(user_id: int):
    """Fetch conversation summaries from the backend database."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/chat/conversations",
            params={"user_id": user_id},
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def fetch_conversation_history(user_id: int, conversation_id: int):
    """Fetch a single conversation's message history from the backend database."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/chat/conversations/{conversation_id}",
            params={"user_id": user_id},
        )
        if response.status_code == 200:
            return response.json().get("messages", [])
        return []
    except Exception:
        return []


def delete_conversation(user_id: int, conversation_id: int):
    """Delete a conversation and its messages from the backend database."""
    try:
        response = requests.delete(
            f"{API_BASE_URL}/chat/conversations/{conversation_id}",
            params={"user_id": user_id},
        )
        if response.status_code == 200:
            return True, response.json()
        return False, response.text
    except Exception as e:
        return False, str(e)


def rename_conversation(user_id: int, conversation_id: int, title: str):
    """Rename a conversation in the backend database."""
    try:
        response = requests.patch(
            f"{API_BASE_URL}/chat/conversations/{conversation_id}",
            params={"user_id": user_id},
            json={"title": title},
        )
        if response.status_code == 200:
            return True, response.json()
        return False, response.text
    except Exception as e:
        return False, str(e)


def _short_title(text: str, max_len: int = 34) -> str:
    """Keep sidebar conversation labels on one line with ellipsis."""
    value = (text or "").strip()
    if len(value) <= max_len:
        return value
    return value[: max_len - 3].rstrip() + "..."


def upsert_current_conversation_snapshot():
    if not st.session_state.username:
        return
    if not st.session_state.chat_history:
        return

    if st.session_state.user_id:
        st.session_state.conversations = fetch_user_conversations(st.session_state.user_id)


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
            st.session_state.conversations = fetch_user_conversations(st.session_state.user_id)
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
            st.session_state.conversations = fetch_user_conversations(st.session_state.user_id)
            return True, {
                "response": data.get("response"),
                "source": data.get("source"),
            }
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
                st.session_state.conversation_id = None
                st.session_state.chat_history = []
                st.session_state.last_summarized_patient = None
                st.rerun()
        
        with col_logout:
            if st.button("🚪 Logout", use_container_width=True, key="logout_btn"):
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

        # Tool selector kept in sidebar to avoid breaking fixed composer layout
        if st.session_state.user_role == "Admin":
            sidebar_tools = ["retrieval", "medical_knowledge"]
        elif st.session_state.user_role == "Doctor":
            sidebar_tools = ["retrieval", "summarization", "medical_knowledge", "treatment_comparison", "diagnosis_recommendation"]
        else:
            sidebar_tools = ["retrieval", "summarization", "medical_knowledge", "treatment_comparison"]

        st.session_state.current_tool_selection = st.selectbox(
            "Tool For Next Message",
            sidebar_tools,
            index=sidebar_tools.index(st.session_state.current_tool_selection) if st.session_state.current_tool_selection in sidebar_tools else 0,
            format_func=lambda x: (
                "📚 Retrieval" if x == "retrieval" else
                "📋 Summarization" if x == "summarization" else
                "🧠 Knowledge" if x == "medical_knowledge" else
                "💊 Treatment" if x == "treatment_comparison" else
                "🩺 Diagnosis"
            ),
            key="tool_selector_sidebar"
        )

        st.markdown("### ⚙️ Tool Filters")
        sidebar_selected_tool = st.session_state.current_tool_selection

        if sidebar_selected_tool == "summarization":
            patients = fetch_patients()
            if patients:
                selected_patient = st.selectbox(
                    "Select Patient",
                    patients,
                    key="patient_selector_sidebar"
                )
                st.session_state.sidebar_patient_name = selected_patient

                # Auto-trigger summarization when patient selection changes.
                if selected_patient != st.session_state.last_summarized_patient:
                    st.session_state.last_summarized_patient = selected_patient

                    with st.spinner(f"Generating summary for {selected_patient}..."):
                        success, result = send_chat_message(
                            message="Please provide a summary of this patient's report",
                            selected_tool="summarization",
                            patient_name=selected_patient
                        )

                    if success:
                        st.session_state.chat_history.append({
                            "sender": "user",
                            "message": f"Show summary for patient: {selected_patient}",
                            "tool": "summarization"
                        })
                        st.session_state.chat_history.append({
                            "sender": "ai",
                            "message": result.get("response"),
                            "source": result.get("source"),
                            "tool": "summarization"
                        })
                        st.session_state.conversations = fetch_user_conversations(st.session_state.user_id)
                        st.session_state.auto_scroll_to_latest = True
                        st.rerun()
                    else:
                        st.error(f"Error: {result}")
            else:
                st.warning("No accessible patient reports found for your role.")

        elif sidebar_selected_tool == "medical_knowledge":
            st.session_state.sidebar_knowledge_type = st.selectbox(
                "Knowledge Type",
                ["condition", "drug", "symptom", "procedure", "guideline"],
                key="knowledge_type_selector_sidebar"
            )
            st.session_state.sidebar_use_rag = st.toggle(
                "Augment with clinical context",
                value=st.session_state.get("sidebar_use_rag", False),
                key="knowledge_use_rag_toggle_sidebar"
            )

        elif sidebar_selected_tool == "treatment_comparison":
            diseases = [
                "Type 2 Diabetes Mellitus",
                "Hypertensive Heart Disease",
                "Community-Acquired Pneumonia",
                "Major Depressive Disorder",
                "Rheumatoid Arthritis"
            ]
            st.session_state.sidebar_disease_name = st.selectbox(
                "Select Disease",
                diseases,
                key="disease_selector_sidebar"
            )

        elif sidebar_selected_tool == "diagnosis_recommendation":
            st.caption("Enter symptom combinations in chat (example: fever + cough + fatigue).")

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

    # Initialize variables for tool-specific settings (bound to sidebar controls)
    patient_name = st.session_state.get("sidebar_patient_name")
    selected_knowledge_type = st.session_state.get("sidebar_knowledge_type", "condition")
    use_rag_for_knowledge = st.session_state.get("sidebar_use_rag", False)
    selected_disease = st.session_state.get("sidebar_disease_name")
    
    # Get current tool selection (from session state for persistence)
    if "current_tool_selection" not in st.session_state:
        st.session_state.current_tool_selection = available_tools[0]

    selected_tool = st.session_state.current_tool_selection
    
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
            for idx, chat in enumerate(st.session_state.chat_history):
                if chat["sender"] == "user":
                    with st.chat_message("user"):
                        st.write(chat["message"])
                else:
                    with st.chat_message("assistant"):
                        st.write(chat["message"])
                        if chat.get("source"):
                            st.caption(f"Source: {chat.get('source')}")
                if idx == len(st.session_state.chat_history) - 1:
                    st.markdown("<div id='latest-message-anchor'></div>", unsafe_allow_html=True)
            # Auto-scroll to bottom by adding empty space that pushes content up
            st.markdown("---")  # Visual separator
        else:
            st.markdown(
                "<div class='hint-box'>Start a conversation by typing a message below or selecting a patient for summarization.</div>",
                unsafe_allow_html=True,
            )
    st.write("")  # Add spacing

    # ========== COMPOSER (native Streamlit fixed chat input) ==========
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
    
    st.write("")  # Add spacing after input
    
    if user_input and user_input.strip():
        # Add user message to history
        st.session_state.chat_history.append({
            "sender": "user",
            "message": user_input,
            "tool": selected_tool
        })
        
        # Send to backend
        with st.spinner("Processing your question..."):
            success, result = send_chat_message(
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
                "message": result.get("response"),
                "source": result.get("source"),
                "tool": selected_tool
            })
            st.session_state.conversations = fetch_user_conversations(st.session_state.user_id)
            st.session_state.auto_scroll_to_latest = True
            st.rerun()
        else:
            st.error(f"Error: {result}")

    if st.session_state.get("auto_scroll_to_latest"):
        components.html(
            """
            <script>
            (() => {
                const doc = window.parent.document;
                const anchor = doc.getElementById('latest-message-anchor');
                if (anchor) {
                    anchor.scrollIntoView({ behavior: 'smooth', block: 'end' });
                } else {
                    const main = doc.querySelector('section.main');
                    if (main) {
                        main.scrollTo({ top: main.scrollHeight, behavior: 'smooth' });
                    } else {
                        window.parent.scrollTo({ top: doc.body.scrollHeight, behavior: 'smooth' });
                    }
                }
            })();
            </script>
            """,
            height=0,
        )
        st.session_state.auto_scroll_to_latest = False
    
    # Sidebar with Old Conversations
    with st.sidebar:
        st.divider()
        
        # Display Old Conversations
        if st.session_state.conversations:
            st.markdown("### Previous Conversations")
            if "active_conversation_actions" not in st.session_state:
                st.session_state.active_conversation_actions = None

            ordered = sorted(
                st.session_state.conversations,
                key=lambda x: x.get("started_at", ""),
                reverse=True,
            )

            # Independent scroll area for conversation list only.
            with st.container(height=360):
                for idx, conv in enumerate(ordered):
                    conversation_title = conv.get("title") or f"Conversation {idx + 1}"
                    title_for_button = _short_title(conversation_title)
                    row_col1, row_col2 = st.columns([0.80, 0.20])

                    with row_col1:
                        # Single-click load behavior.
                        if st.button(title_for_button, use_container_width=True, key=f"load_conv_{idx}", help=conversation_title):
                            st.session_state.conversation_id = conv.get('conversation_id')
                            st.session_state.chat_history = [
                                {
                                    "sender": msg.get("sender"),
                                    "message": msg.get("message"),
                                    "source": msg.get("source"),
                                }
                                for msg in fetch_conversation_history(st.session_state.user_id, conv.get('conversation_id'))
                            ]
                            st.rerun()

                    with row_col2:
                        if st.button("⋯", use_container_width=True, key=f"actions_toggle_{idx}"):
                            conv_id = conv.get('conversation_id')
                            current = st.session_state.active_conversation_actions
                            st.session_state.active_conversation_actions = None if current == conv_id else conv_id

                    if st.session_state.active_conversation_actions == conv.get('conversation_id'):
                        edit_title = st.text_input(
                            "Rename conversation",
                            value=conversation_title,
                            key=f"conversation_title_{conv.get('conversation_id')}"
                        )
                        action_col1, action_col2 = st.columns([0.5, 0.5])
                        with action_col1:
                            if st.button("Save", use_container_width=True, key=f"rename_conv_{idx}"):
                                success, result = rename_conversation(st.session_state.user_id, conv.get('conversation_id'), edit_title)
                                if success:
                                    st.session_state.conversations = fetch_user_conversations(st.session_state.user_id)
                                    st.session_state.active_conversation_actions = None
                                    st.success("Conversation renamed")
                                    st.rerun()
                                else:
                                    st.error(f"Rename failed: {result}")
                        with action_col2:
                            if st.button("Delete", use_container_width=True, key=f"delete_conv_{idx}"):
                                success, result = delete_conversation(st.session_state.user_id, conv.get('conversation_id'))
                                if success:
                                    if st.session_state.conversation_id == conv.get('conversation_id'):
                                        st.session_state.conversation_id = None
                                        st.session_state.chat_history = []
                                    st.session_state.conversations = fetch_user_conversations(st.session_state.user_id)
                                    st.session_state.active_conversation_actions = None
                                    st.success("Conversation deleted")
                                    st.rerun()
                                else:
                                    st.error(f"Delete failed: {result}")
        
        st.divider()
        st.markdown("### ℹ️ About")
        st.info(
            "This is a clinical assistant powered by RAG technology. "
            "Use **Retrieval** to ask about clinical protocols and guidelines, "
            "or **Summarization** to get a summary of patient reports based on your role permissions."
        )
