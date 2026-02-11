# Google Authentication - Expo Go Frontend Implementation

## Overview

The backend exposes a Google OAuth endpoint for mobile apps at `POST /api/v1/auth/google/token`.
Your Expo app sends a Google **ID token** and receives back a user object + JWT tokens.

## Prerequisites

Install the required packages:

```bash
npx expo install expo-auth-session expo-crypto expo-web-browser
```

## Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/) > **APIs & Services** > **Credentials**
2. Create an **OAuth 2.0 Client ID** with type **Web application**
   - This is used by `expo-auth-session` even on mobile (it uses the web client ID to get an ID token)
   - Add `https://auth.expo.io/@your-expo-username/your-app-slug` as an authorized redirect URI
3. Copy the **Client ID** (you'll use it in the Expo app AND the backend `.env`)
4. Backend `.env`:
   ```env
   GOOGLE_CLIENT_ID=your-web-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret
   ```

## API Contract

### `POST /api/v1/auth/google/token`

**Request:**
```json
{
  "id_token": "eyJhbGciOiJSUzI1NiIs..."
}
```

**Success Response (200):**
```json
{
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@gmail.com",
    "full_name": "John Doe",
    "picture_url": "https://lh3.googleusercontent.com/a/...",
    "auth_provider": "google",
    "is_active": true,
    "is_verified": true,
    "created_at": "2026-02-11T12:00:00Z",
    "last_login": "2026-02-11T12:00:00Z"
  },
  "tokens": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

**Error Response (401):**
```json
{
  "error": "Invalid Google ID token",
  "code": "OAUTH_ERROR"
}
```

### `POST /api/v1/auth/refresh`

Use this to refresh tokens before the access token expires.

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

## Implementation Guide

### 1. Google Auth Hook

Create a hook that handles Google Sign-In using `expo-auth-session`:

```typescript
import * as Google from "expo-auth-session/providers/google";
import * as WebBrowser from "expo-web-browser";

WebBrowser.maybeCompleteAuthSession();

const GOOGLE_WEB_CLIENT_ID = "your-web-client-id.apps.googleusercontent.com";

export function useGoogleAuth() {
  const [request, response, promptAsync] = Google.useIdTokenAuthRequest({
    clientId: GOOGLE_WEB_CLIENT_ID,
  });

  return { request, response, promptAsync };
}
```

### 2. Auth Flow

When the user taps "Sign in with Google":

1. Call `promptAsync()` to open the Google Sign-In screen
2. On success, extract the `id_token` from the response
3. Send it to `POST /api/v1/auth/google/token`
4. Store the returned `access_token` and `refresh_token` securely (e.g., `expo-secure-store`)
5. Navigate to the main app

```typescript
import * as SecureStore from "expo-secure-store";

async function handleGoogleSignIn(response) {
  if (response?.type === "success") {
    const idToken = response.params.id_token;

    const res = await fetch(`${API_BASE_URL}/api/v1/auth/google/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id_token: idToken }),
    });

    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.error);
    }

    const data = await res.json();

    // Store tokens securely
    await SecureStore.setItemAsync("access_token", data.tokens.access_token);
    await SecureStore.setItemAsync("refresh_token", data.tokens.refresh_token);

    // Store user info
    await SecureStore.setItemAsync("user", JSON.stringify(data.user));

    return data;
  }
}
```

### 3. Authenticated Requests

For all subsequent API calls, include the access token:

```typescript
async function authenticatedFetch(url: string, options: RequestInit = {}) {
  const accessToken = await SecureStore.getItemAsync("access_token");

  const res = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
  });

  // If 401, try refreshing the token
  if (res.status === 401) {
    const newTokens = await refreshTokens();
    if (newTokens) {
      return fetch(url, {
        ...options,
        headers: {
          ...options.headers,
          Authorization: `Bearer ${newTokens.access_token}`,
          "Content-Type": "application/json",
        },
      });
    }
  }

  return res;
}

async function refreshTokens() {
  const refreshToken = await SecureStore.getItemAsync("refresh_token");
  if (!refreshToken) return null;

  const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!res.ok) return null;

  const tokens = await res.json();
  await SecureStore.setItemAsync("access_token", tokens.access_token);
  await SecureStore.setItemAsync("refresh_token", tokens.refresh_token);
  return tokens;
}
```

## Behavior Notes

- **New user**: If the Google email doesn't exist in the database, a new account is created automatically (sign-up via Google)
- **Existing user (same email)**: If the email already exists (e.g., registered with email/password), the Google account is **linked** to the existing user
- **Returning Google user**: If the Google ID is already known, the user is logged in directly
- **Email uniqueness**: Each email can only be associated with one account
- **Token expiry**: Access tokens expire after 30 minutes; use the refresh endpoint to get new ones
