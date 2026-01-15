# KnowIt Backend - Security Updates

## Summary of Changes

This update implements JWT authentication and user-based access control for the KnowIt Backend API.

---

## ✅ Completed Tasks

### 1. JWT Configuration in `config.py`

Added the following JWT settings:

```python
# JWT Authentication
jwt_secret_key: str
jwt_algorithm: str = "HS256"
jwt_access_expire_minutes: int = 30
jwt_refresh_expire_days: int = 7
```

### 2. Secured Routes with `CurrentActiveUser`

The following routes now require authentication:

| Route | Method | File |
|-------|--------|------|
| `/api/v1/transcription` | POST | `app/transcription/router.py` |
| `/api/v1/analysis` | POST | `app/analysis/router.py` |
| `/api/v1/analysis/sessions/{id}` | GET | `app/analysis/router.py` |
| `/api/v1/topics` | GET, POST | `app/topics/router.py` |
| `/api/v1/topics/{id}` | GET, PATCH, DELETE | `app/topics/router.py` |

### 3. User-based Filtering in Repositories

#### Topics Repository (`app/topics/repository.py`)
- `create()` - Now requires `user_id` parameter to associate topic with user
- `get_by_id()` - Added `user_id` and `verify_ownership` parameters
- `get_all()` - Now requires `user_id` to return only user's topics
- `count()` - Now requires `user_id` to count only user's topics
- `update()` - Now requires `user_id` for ownership verification
- `delete()` - Now requires `user_id` for ownership verification
- Added `verify_ownership()` method

#### Topics Service (`app/topics/service.py`)
- All methods now accept and pass `user_id` to the repository
- Users can only see and modify their own topics

#### Analysis Service (`app/analysis/service.py`)
- `analyze_text()` - Verifies topic ownership before creating session
- `get_session()` - Verifies ownership through topic relationship

---

## 📁 Files Modified

```
app/
├── config.py                      # Added JWT settings
├── transcription/
│   └── router.py                  # Added CurrentActiveUser dependency
├── analysis/
│   ├── router.py                  # Added CurrentActiveUser, ownership verification
│   └── service.py                 # Added user_id verification
└── topics/
    ├── router.py                  # Added CurrentActiveUser to all routes
    ├── repository.py              # Added user_id filtering
    └── service.py                 # Added user_id pass-through

.env.example                       # Added JWT environment variables
```

---

## 🔧 Environment Variables

Add these to your `.env` file:

```env
# JWT Authentication
JWT_SECRET_KEY=your-super-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_EXPIRE_MINUTES=30
JWT_REFRESH_EXPIRE_DAYS=7
```

⚠️ **Important**: Generate a secure secret key for production:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 🔒 Security Features Implemented

1. **Authentication Required**: All sensitive routes require a valid JWT access token
2. **User Isolation**: Users can only access their own topics and sessions
3. **Ownership Verification**: All CRUD operations verify that resources belong to the requesting user
4. **Proper Error Responses**: 401 for unauthenticated, 403 for unauthorized access, 404 for not found

---

## 📝 API Response Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 204 | Deleted (no content) |
| 400 | Bad request |
| 401 | Not authenticated (missing or invalid token) |
| 403 | Forbidden (resource doesn't belong to user) |
| 404 | Not found |
| 500 | Internal server error |
| 503 | External API unavailable |

---

## 🧪 Testing

To test the secured endpoints:

1. Register a user via `POST /api/v1/auth/register`
2. Login via `POST /api/v1/auth/login` to get tokens
3. Include the access token in the `Authorization` header:
   ```
   Authorization: Bearer <access_token>
   ```

Example with curl:
```bash
# Create a topic (authenticated)
curl -X POST http://localhost:8000/api/v1/topics \
  -H "Authorization: Bearer <your_access_token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Python Basics"}'

# List your topics (authenticated)
curl http://localhost:8000/api/v1/topics \
  -H "Authorization: Bearer <your_access_token>"
```