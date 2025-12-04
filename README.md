# Nicole - AI Optometry Mentor

Nicole is an intelligent AI chatbot designed specifically for optometry students and professionals. She provides mentorship on optometry concepts, business ideas, and professional development.

## Features

✨ **Core Features**
- 🤖 AI-powered responses using Google Gemini
- 👤 User authentication & profiles
- 💬 Multi-chat sessions with history
- 🏷️ Chat organization with tags/categories
- 📊 Usage analytics & rate limiting
- 📱 Mobile-responsive design

🔒 **Security & Performance**
- Secure API key management with environment variables
- Rate limiting to prevent abuse
- User-specific rate limits (Free & Pro tiers)
- Database tracking of API usage

💾 **Data Management**
- Chat history saved to database
- Export chats as PDF or JSON
- Full-text search across chats
- User session management

## Tech Stack

- **Backend**: Django 5.2
- **Frontend**: HTML, Tailwind CSS, JavaScript
- **Database**: SQLite (development), PostgreSQL (production)
- **AI**: Google Gemini API
- **Styling**: Tailwind CSS with custom Art Deco theme

## Installation

### Prerequisites
- Python 3.8+
- pip
- Git

### Local Setup

1. Clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/nicole-optometry-mentor.git
cd nicole-optometry-mentor
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file:
```bash
cat > .env << 'EOF'
GEMINI_API_KEY=your_api_key_here
SECRET_KEY=your_django_secret_key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
