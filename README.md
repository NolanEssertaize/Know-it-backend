# KnowIt Backend

Backend API for the KnowIt learning application. Built with FastAPI, SQLAlchemy 2.0 (async), and PostgreSQL.

## 🏗️ Architecture

```
app/
├── main.py                 # FastAPI entry point
├── config.py               # pydantic-settings configuration
├── database.py             # SQLAlchemy async setup
│
├── core/                   # Cross-cutting concerns
│   ├── dependencies.py     # FastAPI dependencies
│   └── exceptions.py       # Custom exceptions
│
├── transcription/          # Audio → Text (Whisper)
│   ├── router.py           # POST /api/v1/transcription
│   ├── service.py          # Business logic
│   └── schemas.py          # Pydantic DTOs
│
├── analysis/               # Text → Analysis (GPT-4)
│   ├── router.py           # POST /api/v1/analysis
│   ├── service.py          # Business logic
│   ├── repository.py       # Database operations
│   ├── schemas.py          # Pydantic DTOs
│   └── models.py           # SQLAlchemy Session model
│
└── topics/                 # CRUD Topics
    ├── router.py           # /api/v1/topics/*
    ├── service.py          # Business logic
    ├── repository.py       # Database operations
    ├── schemas.py          # Pydantic DTOs
    └── models.py           # SQLAlchemy Topic model
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 16+
- OpenAI API Key

### With Docker (Recommended)

```bash
# Clone the repository
cd knowit-backend

# Copy environment file
cp .env.example .env

# Edit .env and add your OPENAI_API_KEY
nano .env

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f api
```

API available at: http://localhost:8000

### Without Docker

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your settings

# Run the server
uvicorn app.main:app --reload
```

## 📡 API Endpoints

### Health Check

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API info |
| GET | `/health` | Health check |
| GET | `/api/v1/health` | API health with version |

### Transcription

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/transcription` | Upload audio → get text |

**Request:** `multipart/form-data`
- `file`: Audio file (.m4a, .mp3, .wav, etc.)
- `language` (optional): Language code (e.g., "fr")

**Response:**
```json
{
  "text": "Transcribed text here...",
  "duration_seconds": 12.5,
  "language": "fr"
}
```

### Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/analysis` | Analyze text → structured feedback |
| GET | `/api/v1/analysis/sessions/{id}` | Get session by ID |

**Request:**
```json
{
  "text": "Le polymorphisme en Java permet...",
  "topic_title": "Polymorphisme en Java",
  "topic_id": "uuid-optional"
}
```

**Response:**
```json
{
  "analysis": {
    "valid": ["Point correct 1", "Point correct 2"],
    "corrections": ["Erreur à corriger"],
    "missing": ["Concept oublié"]
  },
  "session_id": "uuid-if-saved"
}
```

### Topics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/topics` | List all topics |
| POST | `/api/v1/topics` | Create topic |
| GET | `/api/v1/topics/{id}` | Get topic with sessions |
| PATCH | `/api/v1/topics/{id}` | Update topic |
| DELETE | `/api/v1/topics/{id}` | Delete topic |

## 📖 API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## 🔧 Configuration

Environment variables (`.env`):

```env
# Application
APP_NAME=KnowIt Backend
APP_VERSION=0.1.0
DEBUG=true

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/knowit

# OpenAI
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4
WHISPER_MODEL=whisper-1

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:8081

# Server
HOST=0.0.0.0
PORT=8000
```

## 🧪 Development

### Code Style

- Python 3.11+ type hints everywhere
- Async/await for all I/O operations
- Pydantic v2 for validation
- SQLAlchemy 2.0 async patterns

### Project Structure Rules

1. **Router** → Only HTTP handling, validation via Pydantic
2. **Service** → Business logic, orchestrates external APIs and repositories
3. **Repository** → Database operations only
4. **Schemas** → Pydantic DTOs (input/output)
5. **Models** → SQLAlchemy ORM classes

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
```

## 📦 Deployment

### Production Dockerfile

The included Dockerfile is production-ready:
- Non-root user
- Health checks
- Optimized layers

### Environment Variables for Production

```env
DEBUG=false
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/knowit_prod
CORS_ORIGINS=https://your-frontend-domain.com
```

## 🔗 Frontend Integration

The API is designed to work with the KnowIt React Native frontend:

```typescript
// Frontend LLMService integration
const response = await fetch('http://localhost:8000/api/v1/transcription', {
  method: 'POST',
  body: formData, // with audio file
});

const { text } = await response.json();

// Analyze transcription
const analysisResponse = await fetch('http://localhost:8000/api/v1/analysis', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    text: text,
    topic_title: "Polymorphisme en Java",
    topic_id: topicId,
  }),
});

const { analysis } = await analysisResponse.json();
// { valid: [...], corrections: [...], missing: [...] }
```

## 📄 License

MIT
