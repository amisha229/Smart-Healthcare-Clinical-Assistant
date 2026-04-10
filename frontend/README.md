# Healthcare Clinical Assistant - Streamlit Frontend

A modern web-based frontend for the Healthcare Clinical Assistant built with Streamlit. This interface provides an intuitive user experience for healthcare professionals to interact with clinical guidance and patient reports.

## Features ✨

- **Authentication & Session Management**
  - User registration and login (no JWT, using Streamlit session state)
  - Role-based access control (Doctor, Nurse, Admin)
  - Persistent session storage during browser session

- **Dual-Mode Interface**
  - **Retrieval Mode**: Ask clinical questions about protocols and guidelines
  - **Summarization Mode**: Get summaries of patient reports based on role permissions

- **User-Friendly Chat Interface**
  - Real-time message sending and receiving
  - Conversation history display
  - Tool selection dropdown (Retrieval vs Summarization)
  - Patient selector for summarization tasks
  - New conversation button to start fresh

- **Role-Based Features**
  - Different patients accessible based on user role
  - Role-specific guidance from backend
  - Automatic filtering of accessible content

## Installation 🚀

### Prerequisites
- Python 3.8+
- Backend API running (FastAPI server on http://localhost:8000)

### Setup Steps

1. **Navigate to frontend folder:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment (optional):**
   - Edit `.env` file to change `API_BASE_URL` if backend is on different host/port
   - Default: `http://localhost:8000`

4. **Run the Streamlit app:**
   ```bash
   streamlit run app.py
   ```

5. **Access the app:**
   - Open browser and go to `http://localhost:8501`
   - Default Streamlit port is 8501

## Usage 📋

### First Time Users
1. Click on "Register" tab
2. Enter username, password, and select your role (Doctor/Nurse/Admin)
3. Click "Register"
4. Use your credentials to login

### Existing Users
1. Enter username and password
2. Click "Login"

### Using the Chat Interface
1. **For Clinical Queries:**
   - Select "📚 Retrieval (Clinical Guidelines)" from tool dropdown
   - Type your clinical question
   - Click "Send ➜"

2. **For Patient Summarization:**
   - Select "📋 Summarization (Patient Reports)" from tool dropdown
   - Select patient from the "Select Patient" dropdown (shows only accessible patients for your role)
   - Type any message (e.g., "Summarize this patient's report")
   - Click "Send ➜"

### Session Management
- Your session is stored in Streamlit's session state for the duration of your browser session
- Click "🚪 Logout" to end your session
- Click "🔄 New Conversation" to start a fresh conversation while staying logged in

## File Structure 📁

```
frontend/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── .env                   # Environment configuration
└── README.md             # This file
```

## Configuration ⚙️

### Environment Variables (.env)
- `API_BASE_URL`: Backend API URL (default: `http://localhost:8000`)
- `STREAMLIT_SERVER_PORT`: Port for Streamlit app (default: 8501)
- `STREAMLIT_SERVER_ADDRESS`: Server address (default: localhost)

## Session Storage 💾

Session data is stored in Streamlit's built-in session state:
- `logged_in`: Boolean flag for authentication status
- `user_id`: Unique user identifier from backend
- `username`: Authenticated username
- `user_role`: User's role (Doctor/Nurse/Admin)
- `conversation_id`: Current conversation ID
- `chat_history`: List of messages in current conversation
- `patients`: Cached list of accessible patients

All data is cleared when:
- User logs out
- Browser session ends
- Streamlit app restarts

## Backend API Endpoints Used 🔌

The frontend communicates with these backend endpoints:

- `POST /auth/register` - User registration
- `POST /auth/login` - User authentication
- `POST /chat` - Send chat message and get response
- `GET /chat/patients` - Fetch accessible patient list

## Troubleshooting 🔧

### "Connection refused" Error
- Ensure backend FastAPI server is running on `http://localhost:8000`
- Check backend logs for errors
- Verify API_BASE_URL in `.env` is correct

### "No accessible patients" Message
- Verify your user role in the database
- Check patient report access permissions in DocumentChunk table
- Try switching to a different role if testing

### Session Lost After Page Refresh
- This is expected behavior - Streamlit clears session on rerun
- You'll need to login again
- Consider using browser cache for persistent login (future enhancement)

## Development 🛠️

To modify the frontend:

1. Edit `app.py` with your changes
2. Streamlit will auto-reload on save
3. No need to restart the server (for most changes)

### Adding New Features
- Session state is accessible via `st.session_state`
- API calls use the `requests` library
- UI components use Streamlit's built-in widgets

## Security Notes ⚠️

Current Implementation:
- Passwords stored in backend database (plaintext in demo, hash in production)
- Session stored client-side in browser (Streamlit default)
- No HTTPS in development mode
- Backend authentication is basic (production should use hashing + tokens)

For Production:
- Use HTTPS/SSL
- Implement password hashing (bcrypt, argon2)
- Add rate limiting
- Implement CSRF protection
- Use secure session storage
- Enable role-based API endpoint access control

## License 📄

Part of the Smart Healthcare Clinical Assistant project.

## Support 📞

For issues or questions, please refer to the main project README or backend documentation.
