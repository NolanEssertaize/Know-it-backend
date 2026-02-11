---
name: know-it-backend-patterns
description: Coding patterns extracted from Know it backend repository
version: 1.0.0
source: local-git-analysis
analyzed_commits: 23
---

# Know It Backend Patterns

## Commit Conventions

This project uses **informal commit messages** without a strict conventional commit prefix. Common patterns observed:

- `Added ...` - New features or additions
- `Changes ...` - Modifications to existing behavior or config
- `Fixed ...` / `Fix ...` - Bug fixes
- `NEw ...` / `Add ...` - New configurations or features
- First word is typically a past-tense verb or imperative

No enforced commit convention (no `feat:`, `fix:`, etc.).

## Code Architecture

```
app/
├── main.py                # FastAPI entry point, lifespan, middleware, router registration
├── config.py              # Pydantic Settings configuration
├── database.py            # Async SQLAlchemy engine & session setup
├── dependencies.py        # Shared FastAPI dependencies (auth, DB session)
├── rate_limit.py          # SlowAPI rate limiting
├── core/
│   ├── dependencies.py    # Core DI utilities
│   └── exceptions.py      # Custom exception classes
├── auth/                  # Authentication module (Google OAuth, JWT)
│   ├── models.py
│   ├── oauth.py
│   ├── repository.py
│   ├── router.py
│   ├── schemas.py
│   └── service.py
├── topics/                # Learning topics management
│   ├── models.py
│   ├── repository.py
│   ├── router.py
│   ├── schemas.py
│   └── service.py
├── analysis/              # AI-powered analysis (GPT-4)
│   ├── models.py
│   ├── repository.py
│   ├── router.py
│   ├── schemas.py
│   └── service.py
├── transcription/         # Audio transcription (OpenAI Whisper)
│   ├── router.py
│   ├── schemas.py
│   └── service.py
├── flashcards/            # Flashcard & deck management with SRS
│   ├── models.py
│   ├── repository.py
│   ├── router.py
│   ├── schemas.py
│   ├── service.py
│   └── srs.py
└── subscriptions/         # Subscription & usage management
    ├── models.py
    ├── repository.py
    ├── router.py
    ├── schemas.py
    └── service.py
alembic/
├── env.py
└── versions/              # Migration scripts
    ├── add_users_auth.py
    ├── add_flashcards_and_decks.py
    ├── add_topic_favorite.py
    └── add_subscriptions_and_usage.py
```

## 3-Layer Architecture

Every module follows a strict **Router -> Service -> Repository** pattern:

| Layer | File | Responsibility |
|-------|------|----------------|
| **Router** | `router.py` | HTTP endpoints, request/response handling, dependency injection |
| **Service** | `service.py` | Business logic, DTO conversion, orchestration |
| **Repository** | `repository.py` | Database operations via async SQLAlchemy |

### Key conventions:
- **Repository** receives `AsyncSession` in constructor, handles all SQL queries
- **Service** receives `AsyncSession` in constructor, creates its own Repository internally
- **Factory functions** like `get_topic_service(db)` are used as FastAPI dependency providers
- **Models** (`models.py`) define SQLAlchemy ORM entities
- **Schemas** (`schemas.py`) define Pydantic DTOs (Create, Update, Read patterns)

## Tech Stack

- **Framework**: FastAPI 0.115.x
- **Python**: >= 3.12
- **ORM**: SQLAlchemy 2.0 (async with `asyncpg`)
- **Database**: PostgreSQL (via asyncpg)
- **Migrations**: Alembic
- **Validation**: Pydantic 2.x + Pydantic Settings
- **Auth**: Google OAuth + python-jose (JWT)
- **AI**: OpenAI SDK (Whisper for transcription, GPT-4 for analysis)
- **Rate Limiting**: SlowAPI
- **Server**: Uvicorn
- **Package Manager**: uv (with requirements.txt for deployment)

## Workflows

### Adding a New Module

1. Create `app/<module>/` directory with `__init__.py`
2. Add `models.py` with SQLAlchemy models
3. Add `schemas.py` with Pydantic DTOs (Create, Update, Read)
4. Add `repository.py` with class accepting `AsyncSession`
5. Add `service.py` with class wrapping the repository
6. Add `router.py` with FastAPI router
7. Export router from `__init__.py`
8. Register router in `app/main.py` with `API_V1_PREFIX`
9. Create Alembic migration in `alembic/versions/`

### Database Migration

1. Define/modify models in `app/<module>/models.py`
2. Create migration script in `alembic/versions/`
3. Run migration with Alembic

### Deployment

- Docker + Docker Compose for containerization
- GitHub Actions CI/CD (`.github/workflows/deploy.yml`)
- Caddy as reverse proxy
- Separate `docker-compose.prod.yml` for production

## Patterns

### Repository Pattern

Repositories are class-based, receive `AsyncSession`, and use SQLAlchemy `select()` statements:

```python
class TopicRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, topic_id: str, ...) -> Topic:
        stmt = select(Topic).where(Topic.id == topic_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
```

### Service Layer DTO Conversion

Services convert between ORM models and Pydantic DTOs using private `_to_read_dto()` / `_to_detail_dto()` methods:

```python
class TopicService:
    def _to_read_dto(self, topic: Topic, session_count: int = 0) -> TopicRead:
        return TopicRead(
            id=topic.id,
            title=topic.title,
            ...
        )
```

### User Scoping

All data access operations are scoped by `user_id` for multi-tenant security:

```python
async def get_all(self, user_id: str, ...) -> Sequence[Topic]:
    stmt = select(Topic).where(Topic.user_id == user_id)
```

### Eager Loading Strategy

Uses `selectinload()` for relationships and separate count queries to avoid async lazy-loading issues:

```python
stmt = stmt.options(selectinload(Topic.sessions))
```

### Logging

Uses Python `logging` module with `[ClassName]` prefix format:

```python
logger = logging.getLogger(__name__)
logger.info(f"[TopicService] Creating topic: {topic_data.title}")
```

### API Versioning

All routes are prefixed with `/api/v1`:

```python
API_V1_PREFIX = "/api/v1"
app.include_router(auth_router, prefix=API_V1_PREFIX)
```

## Testing Patterns

No test files detected in the repository. Consider adding:
- `tests/` directory with `conftest.py`
- Unit tests for services with mocked repositories
- Integration tests for repositories with test database
- API tests using FastAPI `TestClient`

## Hotspot Files

Most frequently changed files (likely to need attention):
- `app/flashcards/service.py` - Core flashcard business logic
- `app/flashcards/repository.py` - Flashcard data access
- `app/flashcards/schemas.py` - Flashcard DTOs
- `app/topics/repository.py` - Topic data access
- `.github/workflows/deploy.yml` - CI/CD pipeline
