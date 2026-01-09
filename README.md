# ServViaAI 🏥

An AI-powered healthcare assistant platform that leverages advanced language models, RAG (Retrieval-Augmented Generation), and machine learning to provide intelligent medical assistance, skin analysis, lab report interpretation, and multilingual support.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
  - [Option 1: Manual Setup](#option-1-manual-setup)
  - [Option 2: Using Setup Scripts](#option-2-using-setup-scripts)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Contributing](#contributing)
- [License](#license)

## 🔍 Overview

ServVia aims to bridge the gap between users and health information. By leveraging AI-driven chat capabilities and a structured data management system, it provides:

- Real-time Health Assistance: Interactive chat for medical queries and health guidance.
- Data Management: A secure backend for managing user records and health data.
- Seamless Deployment: Automated installers to get the system up and running quickly.

1. **ServVia (AI Service)** - The core AI engine handling intent classification, RAG-based retrieval, response generation, and specialized medical analysis features. 

2. **ServVia-Backend** - A robust Django-based backend service that manages users, content, data exchange, and serves as the primary API gateway.

The platform integrates with various AI services including OpenAI, Google Cloud (Speech, Text-to-Speech, Translate, Vision), and uses Qdrant for vector database operations.

## ✨ Features

- **AI-Powered Chat** - Intelligent conversational interface with context-aware responses
- **Intent Classification** - Automated understanding and routing of user queries
- **RAG Service** - Retrieval-Augmented Generation for accurate, knowledge-based responses
- **Skin Analysis** - AI-powered skin condition analysis from images
- **Lab Report Interpretation** - Automated analysis and explanation of medical lab reports
- **Multilingual Support** - Language detection, translation, and multilingual text services
- **User Profile Management** - Medical profile tracking including conditions, medications, and allergies
- **Content Management System** - Upload and manage medical content in various formats
- **Analytical Dashboards** - Usage analytics and insights

## 📁 Project Structure

```
servviaAI/
├── servvia/                    # AI Service (Port 8001)
│   ├── api/                    # API endpoints
│   ├── common/                 # Shared utilities
│   ├── database/               # Database configurations
│   ├── django_core/            # Django settings and configuration
│   ├── generation/             # Response generation modules
│   ├── intent_classification/  # Intent detection logic
│   ├── lab_report/             # Lab report analysis
│   ├── language_service/       # Multilingual support
│   ├── rag_service/            # RAG implementation
│   ├── rephrasing/             # Query rephrasing
│   ├── reranking/              # Search result reranking
│   ├── retrieval/              # Document retrieval
│   ├── skin_analysis/          # Skin condition analysis
│   ├── user_profile/           # User management
│   ├── requirements.txt        # Python dependencies for servvia
│   └── manage.py
│
├── servvia-backend/            # Backend Service (Port 8000)
│   ├── core/                   # Django core settings
│   ├── requirements.txt        # Python dependencies for backend
│   └── manage.py
│
├── setup_servvia.sh            # Setup script for macOS/Linux
├── start_servers.bat           # Start script for Windows
└── . gitignore
```

## 📋 Prerequisites

- **Python 3.10+**
- **PostgreSQL** (Database)
- **Redis** (Caching & Celery broker)
- **Qdrant** (Vector database)
- **FFmpeg** (For audio/video processing)

### External Services (API Keys Required)

- OpenAI API
- Google Cloud APIs (Speech, Text-to-Speech, Translate, Vision)

## 🛠️ Installation & Setup

### ⚠️ Important:  Two Separate Requirements Files

This project has **two separate `requirements.txt` files** that must be installed in their respective virtual environments: 

| Component | Path | Virtual Environment |
|-----------|------|---------------------|
| ServVia (AI Service) | `servvia/requirements.txt` | `servvia/venv/` |
| ServVia Backend | `servvia-backend/requirements.txt` | `servvia-backend/myenv/` |

### Option 1: Manual Setup

#### Step 1: Clone the Repository

```bash
git clone https://github.com/Manishnm10/servviaAI.git
cd servviaAI
```

#### Step 2: Set Up ServVia (AI Service)

```bash
# Navigate to servvia directory
cd servvia

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux: 
source venv/bin/activate

# Install dependencies from servvia's requirements.txt
pip install -r requirements.txt

# Return to root directory
cd .. 
```

#### Step 3: Set Up ServVia Backend

```bash
# Navigate to servvia-backend directory
cd servvia-backend

# Create virtual environment
python -m venv myenv

# Activate virtual environment
# On Windows:
myenv\Scripts\activate
# On macOS/Linux:
source myenv/bin/activate

# Install dependencies from servvia-backend's requirements.txt
pip install -r requirements.txt

# Return to root directory
cd ..
```

#### Step 4: Configure Environment Variables

Create `.env` files in both `servvia/` and `servvia-backend/` directories with the necessary configuration:

```env
# Database
POSTGRES_DB=your_db_name
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333

# OpenAI
OPENAI_API_KEY=your_openai_api_key

# Google Cloud (if using)
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json
```

#### Step 5: Run Database Migrations

```bash
# For servvia-backend
cd servvia-backend
source myenv/bin/activate  # or myenv\Scripts\activate on Windows
python manage.py makemigrations
python manage.py migrate

# For servvia
cd ../servvia
source venv/bin/activate  # or venv\Scripts\activate on Windows
python manage.py makemigrations
python manage.py migrate
```

### Option 2: Using Setup Scripts

#### For macOS/Linux: 

```bash
chmod +x setup_servvia.sh
./setup_servvia.sh
```

## 🚀 Running the Application

### Windows

Simply double-click or run:

```cmd
start_servers.bat
```

### macOS/Linux

Open two terminal windows:

**Terminal 1 - ServVia (AI Service):**
```bash
cd servvia
source venv/bin/activate
python manage.py runserver 8001
```

**Terminal 2 - ServVia Backend:**
```bash
cd servvia-backend
source myenv/bin/activate
python manage.py runserver 8000
```

### Access Points

| Service | URL |
|---------|-----|
| ServVia (AI Service) | http://127.0.0.1:8001/ |
| ServVia Backend | http://127.0.0.1:8000/ |

---

*Disclaimer: This tool is intended for informational purposes and should not replace professional medical advice, diagnosis, or treatment.*
