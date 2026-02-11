## Implementation Plan: Google OAuth Connection

### Requirements Restatement

1. **Wire up Google OAuth endpoints** - Backend logic exists (oauth.py, service.py, repository.py) but router has NO Google endpoints
2. **Add Google OAuth config** - `google_client_id` and `google_client_secret` are missing from `config.py`
3. **Remove iOS/Apple settings** - **CANNOT REMOVE** - Apple config is actively used by subscriptions module for receipt verification
4. **User creation via Google sign-up** - Already handled by `AuthService.authenticate_oauth()` (find-or-create flow)
5. **Email uniqueness** - Already enforced (`User.email` has `unique=True`)
6. **API contracts** - Document request/response schemas for the frontend
7. **Frontend prompt** - Provide implementation guide for Expo Go mobile app

### Current State Analysis

| Component | Status | Notes |
|-----------|--------|-------|
| `oauth.py` - GoogleOAuth class | DONE | Code exchange, user info, ID token verification all implemented |
| `service.py` - authenticate_oauth() | DONE | Find by google_id -> find by email (link) -> create new user |
| `repository.py` - OAuth methods | DONE | create_oauth_user, get_by_google_id, link_google_account |
| `schemas.py` - OAuth DTOs | DONE | GoogleAuthRequest, GoogleTokenRequest, OAuthUserInfo |
| `models.py` - User model | DONE | AuthProvider enum, google_id field, email unique |
| `router.py` - OAuth endpoints | MISSING | Schemas imported but no endpoints defined |
| `config.py` - Google credentials | MISSING | google_client_id, google_client_secret not in Settings |

### Task Type
- [x] Backend
- [x] Frontend (documentation/prompt only)

### Implementation Steps

#### Step 1: Update `app/config.py`
- Add `google_client_id: str = ""` and `google_client_secret: str = ""` to Settings
- Keep Apple fields (used by subscriptions)

#### Step 2: Add Google OAuth endpoints to `app/auth/router.py`
Add two endpoints in a GOOGLE OAUTH section:

1. **`POST /auth/google`** (web flow) - Accepts `GoogleAuthRequest` (code + redirect_uri)
2. **`POST /auth/google/token`** (mobile/Expo flow) - Accepts `GoogleTokenRequest` (id_token)

Both call `GoogleOAuth.authenticate()` -> `AuthService.authenticate_oauth()` -> return `AuthResponse`

Rate-limited at 10/minute, handle `OAuthError` -> 401.

#### Step 3: Clean up `app/auth/oauth.py`
- Remove the commented-out factory function string at lines 189-196

#### Step 4: Create frontend prompt file
- Write `FRONTEND_GOOGLE_AUTH_PROMPT.md` with Expo Go implementation guide

### API Contracts

#### `POST /api/v1/auth/google` (Web Flow)

**Request:**
```json
{
  "code": "4/0AX4XfWh...",
  "redirect_uri": "http://localhost:3000/auth/callback"
}
```

**Response (201):**
```json
{
  "user": {
    "id": "uuid",
    "email": "user@gmail.com",
    "full_name": "John Doe",
    "picture_url": "https://lh3.googleusercontent.com/...",
    "auth_provider": "google",
    "is_active": true,
    "is_verified": true,
    "created_at": "2026-02-11T12:00:00Z",
    "last_login": "2026-02-11T12:00:00Z"
  },
  "tokens": {
    "access_token": "eyJhbG...",
    "refresh_token": "eyJhbG...",
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

**Error (401):**
```json
{
  "error": "Failed to exchange authorization code",
  "code": "OAUTH_ERROR"
}
```

#### `POST /api/v1/auth/google/token` (Mobile / Expo Flow)

**Request:**
```json
{
  "id_token": "eyJhbGciOiJSUzI1NiIs..."
}
```

**Response (200):** Same `AuthResponse` as above.

**Error (401):**
```json
{
  "error": "Invalid Google ID token",
  "code": "OAUTH_ERROR"
}
```

### Key Files

| File | Operation | Description |
|------|-----------|-------------|
| `app/config.py:48` | Modify | Add google_client_id and google_client_secret |
| `app/auth/router.py` | Modify | Add Google OAuth endpoints section |
| `app/auth/oauth.py:189-196` | Modify | Remove commented-out factory string |
| `FRONTEND_GOOGLE_AUTH_PROMPT.md` | Create | Expo Go Google Auth implementation guide |

### Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Google credentials not set | Fields default to "", OAuthError raised at request time |
| Expo Go ID token has different audience | GoogleOAuth.verify_id_token uses settings.google_client_id - ensure Expo uses the same client ID or add an Expo-specific client ID |

### Google Cloud Console Setup Instructions

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create/select a project
3. Navigate to **APIs & Services > Credentials**
4. Click **Create Credentials > OAuth 2.0 Client IDs**
5. Configure the OAuth consent screen if not done yet
6. Create **two** client IDs:
   - **Web application** - for web flow, add redirect URIs
   - **Android** - for Expo, set package name to your app's package
7. Copy the **Web Client ID** and **Client Secret**
8. Add to `.env`:
   ```env
   GOOGLE_CLIENT_ID=your-web-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret
   ```
9. In your Expo app, use the **Web Client ID** for `expo-auth-session` (it returns an ID token signed for the web client)
