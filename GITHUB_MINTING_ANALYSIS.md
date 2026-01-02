# GitHub App Token Minting Service - Analysis Summary

This document summarizes the key findings from analyzing `github-app-basic.openapi.json` to support GitHub authentication integration in the spec-compiler service.

## Service Overview

The GitHub App Token Minting Service is a Cloud Run service that manages GitHub OAuth tokens for accessing the GitHub API. It handles the complete OAuth flow and token lifecycle management.

## Key API Endpoints

### 1. Token Retrieval: `POST /api/token`

**Purpose**: Retrieve a stored GitHub user access token, with optional refresh.

**Authentication**: 
- Cloud Run IAM authentication (infrastructure level)
- Requires `roles/run.invoker` IAM role
- Authorization header: `Bearer <GCP-identity-token>`

**Request Parameters**:
- `force_refresh` (optional, boolean): Force token refresh even if not near expiry
  - Can be provided as query parameter: `/api/token?force_refresh=true`
  - Or in JSON body: `{"force_refresh": true}`

**Response Format** (HTTP 200):
```json
{
  "access_token": "gho_ExampleToken123...",
  "token_type": "bearer",
  "expires_at": "2025-12-31T23:59:59+00:00"  // or null for non-expiring tokens
}
```

**Response Schema**:
- `access_token` (string, required): GitHub user access token
- `token_type` (string, required): Token type, typically "bearer"
- `expires_at` (string|null, optional): ISO-8601 expiration timestamp or null

**Error Responses**:
- `404`: User has not completed authorization (no token stored)
- `500`: Token refresh failed due to GitHub API error
- `503`: Firestore service unavailable

### 2. OAuth Flow: `GET /github/install`

**Purpose**: Initiates OAuth user authorization flow (interactive browser use only).

**Process**:
1. Generates CSRF state token
2. Redirects to GitHub's authorization page
3. User authorizes the app
4. GitHub redirects to `/oauth/callback`

**Parameters**:
- `scopes` (optional, string): Comma-separated OAuth scopes (default: "user:email,read:org")

**Response**: HTTP 302 redirect to GitHub with state token cookie

### 3. OAuth Callback: `GET /oauth/callback`

**Purpose**: Handles OAuth callback from GitHub after user authorization.

**Process**:
1. Validates CSRF state token
2. Exchanges authorization code for access token
3. Returns success/error HTML page

**Note**: This endpoint is called automatically by GitHub, not by client applications.

## Authentication & Security

### Infrastructure-Level Auth
- All endpoints (except health checks) require Cloud Run IAM authentication
- Authentication is enforced by Cloud Run, not application code
- Deploy with: `gcloud run deploy --no-allow-unauthenticated`

### Obtaining Identity Tokens
- **User accounts**: `gcloud auth print-identity-token`
- **Service accounts (Python)**: `google.oauth2.id_token.fetch_id_token(auth_req, service_url)`
- **Service accounts (Node.js)**: `GoogleAuth.getIdTokenClient(serviceUrl)`

### Token Characteristics
- Most GitHub user tokens do not expire (`expires_at: null`)
- Tokens are stored encrypted in Firestore using AES-256-GCM
- Automatic refresh when tokens are near expiration (configurable threshold)
- Cooldown period after failed refresh attempts (default: 300 seconds)

## Integration Requirements for spec-compiler

### Configuration
1. **MINTING_SERVICE_BASE_URL**: Cloud Run service URL (e.g., `https://token-service-xxxxx-uc.a.run.app`)
2. **MINTING_SERVICE_AUTH_HEADER**: GCP identity token for IAM authentication
3. **GITHUB_API_BASE_URL**: GitHub API base URL (default: `https://api.github.com`)

### Token Acquisition Flow
```python
# 1. Request token from minting service
response = requests.post(
    f"{MINTING_SERVICE_BASE_URL}/api/token",
    headers={"Authorization": f"Bearer {GCP_IDENTITY_TOKEN}"},
    json={"force_refresh": False}
)

# 2. Extract token from response
token_data = response.json()
access_token = token_data["access_token"]
token_type = token_data["token_type"]
expires_at = token_data.get("expires_at")  # May be null

# 3. Use token for GitHub API calls
github_response = requests.get(
    f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}",
    headers={"Authorization": f"Bearer {access_token}"}
)
```

### Error Handling
- **404 from minting service**: User hasn't completed OAuth flow - prompt for authorization
- **500/503 from minting service**: Retry with exponential backoff
- **Invalid token from GitHub API**: Request refresh with `force_refresh=true`

## Operational Assumptions

1. **Single-User Context**: The minting service stores one token per deployment (not multi-tenant)
2. **Stateless Integration**: spec-compiler requests tokens on-demand, doesn't store them
3. **Token Lifecycle**: Minting service handles all token management (storage, refresh, expiry)
4. **IAM Dependency**: Requires GCP identity tokens for every request

## Data Models Defined

### GitHubAuthToken
Represents a minted GitHub token with metadata:
- `access_token` (string, required): The GitHub access token
- `token_type` (string, default="bearer"): Token type
- `expires_at` (string|null, optional): ISO-8601 expiration or null
- `scope` (string|null, optional): Comma-separated OAuth scopes
- `created_at` (datetime): Timestamp when token was minted

### RepoContextPayload
Represents repository context for LLM requests:
- `tree` (list[dict]): Repository file tree structure
- `dependencies` (list[dict]): Repository dependencies
- `file_summaries` (list[dict]): File summaries for context

## References

- OpenAPI Spec: `github-app-basic.openapi.json`
- Service Documentation: See `info.description` in OpenAPI spec
- Token Response Schema: `components.schemas.TokenResponse`
- Token Request Schema: `components.schemas.TokenRequest`

## Next Steps for Implementation

1. Implement HTTP client for minting service communication
2. Add token caching with TTL based on `expires_at`
3. Implement retry logic with exponential backoff
4. Add metrics/logging for token acquisition
5. Integrate with GitHub API client for repository operations
