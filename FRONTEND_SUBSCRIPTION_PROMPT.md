# Frontend Implementation: Subscriptions & Usage Limits

The backend now enforces **daily usage quotas** per subscription plan and **IP-based rate limiting**. The frontend needs to integrate with three new API endpoints, handle two new error states, and add in-app purchase flows.

---

## Plan Tiers

| Plan | Sessions/day | Card Generations/day | Price |
|------|-------------|---------------------|-------|
| Free | 1 | 1 | $0 |
| Student | 10 | 10 | TBD |
| Unlimited | 50 | 50 | TBD |

- "Sessions" = calls to `POST /api/v1/analysis` (knowledge checks)
- "Generations" = calls to `POST /api/v1/flashcards/generate` (AI flashcard generation)
- Quotas reset daily at UTC midnight

---

## New API Endpoints

All endpoints require `Authorization: Bearer <token>` header.

### 1. `GET /api/v1/subscriptions`

Returns the user's current subscription. Auto-creates a FREE subscription on first call.

**Response (200):**
```json
{
  "id": "01957e3a-...",
  "plan_type": "free",           // "free" | "student" | "unlimited"
  "status": "active",            // "active" | "expired" | "cancelled" | "grace_period"
  "store_platform": null,        // "apple" | "google" | null (for free)
  "store_product_id": null,      // store product ID or null
  "expires_at": null,            // ISO datetime or null (for free)
  "is_active": true,             // computed: true if usable right now
  "created_at": "2025-02-06T..."
}
```

### 2. `GET /api/v1/subscriptions/usage`

Returns today's usage counts, limits, and remaining quota.

**Response (200):**
```json
{
  "usage_date": "2025-02-06",
  "sessions_used": 0,
  "sessions_limit": 1,
  "sessions_remaining": 1,
  "generations_used": 0,
  "generations_limit": 1,
  "generations_remaining": 1,
  "plan_type": "free"
}
```

### 3. `POST /api/v1/subscriptions/verify`

Verifies an app store receipt and activates the subscription. Call this after a successful in-app purchase.

**Request:**
```json
{
  "platform": "apple",                          // "apple" | "google"
  "receipt_data": "<transaction_id_or_token>",   // Apple: transaction ID, Google: purchase token
  "product_id": "com.knowit.student"             // the store product ID purchased
}
```

**Response (200):**
```json
{
  "success": true,
  "subscription": { /* SubscriptionRead object */ },
  "message": "Subscription activated: student"
}
```

**Error (400):**
```json
{
  "error": "Apple receipt verification failed",
  "code": "RECEIPT_VERIFICATION_FAILED"
}
```

---

## New Error States to Handle

### HTTP 429 — Usage Limit Exceeded (Quota)

The analysis and flashcard generation endpoints now return **429** when the user has hit their daily limit.

**Affected endpoints:**
- `POST /api/v1/analysis` — session quota exceeded
- `POST /api/v1/flashcards/generate` — generation quota exceeded

**Response body:**
```json
{
  "detail": "Daily session limit reached (1/1). Upgrade your plan for more."
}
```

### HTTP 429 — Rate Limit Exceeded (IP-based)

All endpoints have IP-based rate limits. Sensitive endpoints have stricter limits:
- Auth (login/register): 10 req/min
- AI endpoints (analysis/generate): 10 req/min
- Receipt verification: 5 req/min
- All other endpoints: 60 req/min

**Response headers** include `Retry-After` (seconds).

**Response body:**
```
Rate limit exceeded
```

---

## Frontend Implementation Requirements

### 1. Subscription State Management

Create a subscription store/provider that:
- Fetches `GET /subscriptions` on app launch (after auth)
- Fetches `GET /subscriptions/usage` before showing quota-gated screens
- Caches the subscription and refreshes on:
  - App foregrounding
  - Successful purchase verification
  - After any analysis or generation call
- Exposes: `planType`, `isActive`, `sessionsRemaining`, `generationsRemaining`

### 2. Quota Check Before Actions

Before showing the analysis or generate screen (or on button tap), check remaining quota:

```
// Pseudocode
const usage = await api.get('/subscriptions/usage')
if (usage.sessions_remaining <= 0) {
  showUpgradeModal()  // "You've used your free session today. Upgrade to continue."
  return
}
// proceed to analysis
```

After a successful analysis/generation, refresh the usage data to update the UI.

### 3. Handle 429 Responses

Add a global API interceptor that catches 429 responses:

- **If body contains `"detail"` with `"limit reached"`** → quota exceeded → show upgrade modal
- **If body is plain text `"Rate limit exceeded"`** → IP rate limit → show "Please wait and try again" toast
- Read the `Retry-After` header to show a countdown if desired

### 4. Usage Display UI

Show remaining quota on the home screen or relevant screens:

```
Sessions: 0/1 remaining today
Generations: 0/1 remaining today
[Upgrade to Student — 10/day]
```

Consider a progress bar or ring indicator.

### 5. In-App Purchase Flow

#### Apple (iOS)

1. Use StoreKit 2 to present product options (`com.knowit.student`, `com.knowit.unlimited`)
2. After successful purchase, get the `transactionId` from the `Transaction` object
3. Call `POST /api/v1/subscriptions/verify`:
   ```json
   {
     "platform": "apple",
     "receipt_data": "<transactionId>",
     "product_id": "com.knowit.student"
   }
   ```
4. On success, refresh subscription state and usage
5. On failure, show error and allow retry

#### Google (Android)

1. Use Google Play Billing Library to present product options
2. After successful purchase, get the `purchaseToken` from the `Purchase` object
3. Call `POST /api/v1/subscriptions/verify`:
   ```json
   {
     "platform": "google",
     "receipt_data": "<purchaseToken>",
     "product_id": "com.knowit.student"
   }
   ```
4. On success, refresh subscription state and usage
5. On failure, show error and allow retry

### 6. Subscription Status Screen

Create a screen accessible from settings/profile that shows:

- Current plan name and badge (Free / Student / Unlimited)
- `is_active` status
- Expiration date (if paid plan)
- Current daily usage (sessions and generations)
- Upgrade/manage buttons
- "Restore Purchases" button that re-triggers receipt verification

### 7. Upgrade Modal/Paywall

Show when quota is exhausted or user taps "Upgrade":

- Display plan comparison (Free vs Student vs Unlimited)
- Show daily limits for each tier
- Purchase buttons for Student and Unlimited
- "Restore Purchases" link
- Close/dismiss button

### 8. Expired/Grace Period Handling

When `status` is `"expired"` or `"grace_period"` and `is_active` is `false`:
- The user effectively falls back to FREE limits
- Show a banner: "Your subscription has expired. Renew to restore your limits."
- Deep-link to the app store subscription management

---

## Store Product IDs

| Plan | Apple Product ID | Google Product ID |
|------|-----------------|-------------------|
| Student | `com.knowit.student` | `com.knowit.student` |
| Unlimited | `com.knowit.unlimited` | `com.knowit.unlimited` |

These must be configured in App Store Connect and Google Play Console.

---

## Summary of Changes by Screen

| Screen | Change |
|--------|--------|
| **Home / Dashboard** | Show usage remaining badge/indicator |
| **Analysis Screen** | Check `sessions_remaining` before allowing analysis. Show upgrade if 0. Handle 429. Refresh usage after success. |
| **Flashcard Generate** | Check `generations_remaining` before allowing generation. Show upgrade if 0. Handle 429. Refresh usage after success. |
| **Settings / Profile** | Add "Subscription" row linking to subscription status screen |
| **New: Subscription Screen** | Current plan, usage stats, expiry, upgrade/manage/restore buttons |
| **New: Upgrade Modal** | Plan comparison, purchase buttons, shown when quota hit |
| **API Layer** | Global 429 interceptor, subscription/usage API methods |
