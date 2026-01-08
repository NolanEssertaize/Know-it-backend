# Know It Backend - Structure du Projet

```
knowit-backend/
│
├── app/
│   ├── __init__.py
│   ├── main.py                          # Point d'entrée FastAPI
│   ├── config.py                        # Configuration pydantic-settings
│   ├── database.py                      # Configuration SQLAlchemy Async
│   │
│   ├── core/                            # Éléments transversaux
│   │   ├── __init__.py
│   │   ├── dependencies.py              # Dépendances FastAPI (DB session, etc.)
│   │   └── exceptions.py                # Exceptions personnalisées
│   │
│   ├── transcription/                   # Module Transcription (Whisper)
│   │   ├── __init__.py
│   │   ├── router.py                    # Endpoints API
│   │   ├── service.py                   # Logique métier + appel API externe
│   │   └── schemas.py                   # DTOs Pydantic
│   │
│   ├── analysis/                        # Module Analysis (OpenAI GPT-4)
│   │   ├── __init__.py
│   │   ├── router.py                    # Endpoints API
│   │   ├── service.py                   # Logique métier + appel API externe
│   │   ├── repository.py                # Accès DB (CRUD sessions)
│   │   ├── schemas.py                   # DTOs Pydantic
│   │   └── models.py                    # Modèles SQLAlchemy
│   │
│   └── topics/                          # Module Topics (CRUD basique)
│       ├── __init__.py
│       ├── router.py
│       ├── service.py
│       ├── repository.py
│       ├── schemas.py
│       └── models.py
│
├── alembic/                             # Migrations DB (optionnel pour v0)
│   └── ...
│
├── requirements.txt
├── .env.example
├── Dockerfile
└── docker-compose.yml
```

## Flux de données

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐     ┌──────────┐
│   Frontend  │────▶│   Router    │────▶│     Service     │────▶│ External │
│  (React N.) │     │ (Endpoint)  │     │ (Business Logic)│     │   API    │
└─────────────┘     └─────────────┘     └────────┬────────┘     └──────────┘
                                                 │
                                                 ▼
                                        ┌─────────────────┐     ┌──────────┐
                                        │   Repository    │────▶│ Database │
                                        │     (DAL)       │     │ (Postgres│
                                        └─────────────────┘     └──────────┘
```

## Endpoints API

| Method | Endpoint                    | Description                              |
|--------|----------------------------|------------------------------------------|
| POST   | `/api/v1/transcription`    | Upload audio → transcription text        |
| POST   | `/api/v1/analysis`         | Text + topic → structured analysis       |
| GET    | `/api/v1/topics`           | Liste tous les topics                    |
| POST   | `/api/v1/topics`           | Crée un nouveau topic                    |
| GET    | `/api/v1/topics/{id}`      | Détails d'un topic + sessions            |
| GET    | `/api/v1/sessions/{id}`    | Détails d'une session                    |
