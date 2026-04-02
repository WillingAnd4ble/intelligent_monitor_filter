# API Specification
**Project:** Agent-based Information System for Personalized arXiv Publication Monitoring

This document outlines the RESTful API endpoints exposed by the **FastAPI Backend** and consumed by the **Next.js Web UI**, complete with request/response JSON schemas.

---

## 0. Universal Error Schemas
All endpoints follow a standardized error pattern.
**400 Bad Request / 401 Unauthorized / 404 Not Found:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The 'comment' field is required for rejection."
  }
}
```

---

## 1. Authentication Endpoints

### 1.1 `POST /auth/register` & `POST /auth/login`
Authenticates a user and returns a JWT.
**Response (200 OK):**
```json
{
  "token": "jwt-token-string"
}
```

### 1.2 Frontend Client Auth Flow (Next.js)
To securely manage sessions, the Next.js frontend employs the following strategy:
- **Storage Strategy:** Instead of putting the JWT in `localStorage` (vulnerable to XSS cross-site scripting), the API endpoints directly set an `httpOnly`, `Secure`, `SameSite=Lax` cookie upon a successful login.
- **Axios Interceptor (401 Handling):** The frontend HTTP client globally catches `401 Unauthorized` responses. Upon a `401`, it immediately triggers a route-push redirecting to `/login` and destroys the local UI user state context gracefully.
- **Refresh Logic:** The server dynamically issues a renewed cookie on valid actions if nearing expiration (sliding session token logic), eliminating the need for complex refresh-token chains on the UI.

---

## 2. User Settings Endpoints
*All endpoints below require `Authorization: Bearer <jwt-token>`*

### 2.1 `GET /api/v1/settings`
### 2.2 `PUT /api/v1/settings`
Updates the user's configuration. Triggers the Agent `GoalDistiller` in the background if `filtering_goal` changes.
**Response (200 OK):**
```json
{
  "status": "success"
}
```

---

## 3. Feed & Library Endpoints

### 3.1 `GET /api/v1/feed`
Retrieves the daily recommended papers for the user (`status == 'feed'`).
**Response (200 OK):**
```json
[
  {
    "user_paper_id": "uuid-string",
    "paper_id": "arxiv:2401.12345",
    "title": "LLM Agents in the Wild",
    "authors": ["John Doe"],
    "abstract": "This paper discusses...",
    "agent_score": 9.5,
    "agent_explanation": "This paper directly addresses your goal...",
    "source_url": "https://arxiv.org/abs/2401.12345"
  }
]
```

### 3.2 `GET /api/v1/feed/stats`
Dashboard UI widget data.
**Response (200 OK):**
```json
{
  "total_scraped_today": 254,
  "evaluated_by_agent": 23,
  "recommended_today": 4
}
```

### 3.3 `POST /api/v1/feed/{user_paper_id}/accept`
Marks a paper as accepted.
**Response (200 OK):**
```json
{ "status": "success", "paper_status": "accepted" }
```

### 3.4 `POST /api/v1/feed/{user_paper_id}/reject`
Rejects a paper via 'Thumbs Down'. 
**Note:** The comment is **required**. This endpoint is an asynchronous **fire-and-forget** route. It returns 202 instantly, while the background worker increments the `rejection_count` and summarizes the memory context for future runs.
**Request Body:**
```json
{
  "comment": "Too theoretical, I need practical implementations of agents, not just math."
}
```
**Response (202 Accepted):**
```json
{ "status": "processing_feedback", "paper_status": "rejected" }
```

### 3.5 `GET /api/v1/library`
Retrieves the user's accepted papers (`status == 'accepted'`). Same schema as `GET /api/v1/feed`.

### 3.6 `POST /api/v1/library/{user_paper_id}/explain`
Triggers the Explainer. Returns a pre-computed explanation from the `paper_explanations` table if available for the user's current level, otherwise computes and caches it.
**Response (200 OK):**
```json
{
  "level": "professional",
  "explanation": "Markdown string containing the tailored explanation..."
}
```

### 3.7 `DELETE /api/v1/library/{user_paper_id}`
Removes an accepted paper from the library entirely or reverts its status.
**Response (204 No Content)**

---

## 4. Pipeline & Automation Endpoints

### 4.1 `POST /api/v1/pipeline/trigger`
Trigger the scraping and pipeline.
**Response (202 Accepted):**
```json
{ "task_id": "uuid-string" }
```

### 4.2 `GET /api/v1/pipeline/{task_id}/status`
Checks the progress of a manual trigger.
**Response (200 OK):**
```json
{ "task_id": "uuid-string", "state": "PROCESSING_PDFS", "progress": 65 }
```

### 4.3 `POST /api/v1/pipeline/{task_id}/cancel`
Force-cancels a background LangGraph pipeline.
**Response (200 OK):**
```json
{ "status": "cancelled" }
```
