# Session handoff — Next.js web UI (arXiv Lens)

Use this file to resume work in a new session. Last context: **Phase 3 backend API integration** is in place; the frontend is aligned for **httpOnly cookie auth** + **Axios `withCredentials: true`**.

---

## Quick start (next session)

1. **Backend** — FastAPI on the URL in `.env.local` (typically `http://localhost:8000`), CORS locked to `http://localhost:3000`, `allow_credentials=True`.
2. **Frontend** — From `web_ui/`: `npm install` (if needed), `npm run dev` → open `http://localhost:3000`.
3. **Env** — Copy [`.env.example`](.env.example) to `.env.local` and set at least:
   - `NEXT_PUBLIC_API_URL=http://localhost:8000` (no trailing slash)

---

## What exists in this repo (`web_ui/`)

| Area | Notes |
|------|--------|
| **Stack** | Next.js 15 App Router, TypeScript, Tailwind (olive & wheat tokens), TanStack Query, Axios, Lucide |
| **Auth transport** | [`lib/axios.ts`](lib/axios.ts): `withCredentials: true`; **401** → clear query cache + redirect to `/login?next=…` |
| **Routes** | `/` landing; `/login`, `/register`; **`/dashboard`** = feed (today’s feed, stats, cards, reject modal); `/library`; `/terminal` (settings tabs → `GET`/`PUT /api/v1/settings`); **`/feed`** redirects to `/dashboard` ([`next.config.ts`](next.config.ts)) |
| **Middleware** | [`middleware.ts`](middleware.ts): guards `/dashboard`, `/library`, `/terminal`, `/feed` **only if** `AUTH_SESSION_COOKIE_NAME` is set **and** that cookie is present on the **Next.js** origin. If unset, rely on API **401** (typical when session cookie is scoped only to API host `:8000`). |
| **Specs** | [`NEXTJS_UI_SPECIFICATION.md`](NEXTJS_UI_SPECIFICATION.md), [`API_SPECIFICATION.md`](API_SPECIFICATION.md), [`AI_SYSTEM_SPECIFICATION.md`](AI_SYSTEM_SPECIFICATION.md) — HTML mockups: `index.html`, `feed.html`, etc. |

---

## Backend alignment (your Phase 3 work)

- **Auth**: `/register`, `/login` set **JWT in `Set-Cookie`** (httpOnly, SameSite=Lax); JSON body should **not** expose raw token (frontend login flow does not need token in body).
- **Dependencies**: `get_current_user` reads **cookie**, not legacy header-only auth.
- **Data**: Settings, feed, library endpoints map SQLAlchemy → Pydantic `PaperResponse` / user settings.

---

## Optional follow-ups (not blocking)

1. **[`lib/api.ts`](lib/api.ts)** — Update `login` / `register` return types from `{ token: string }` to match cookie-only responses (e.g. `{ status: string }` or empty) once responses are final.
2. **Middleware** — Set `AUTH_SESSION_COOKIE_NAME` to the **exact** cookie name **only if** that cookie is also available on `localhost:3000` (e.g. via BFF or shared domain). Otherwise leave unset.
3. **`.env.local`** — Add `NEXT_PUBLIC_DEMO_EMAIL` if you want the sidebar email stub populated.

---

## Commands

```bash
cd web_ui
npm run dev      # development
npm run build    # production check
```

---

## Cursor “memory”

If you use project memory/rules: summarize as — *“Next.js in `web_ui/`; API base `NEXT_PUBLIC_API_URL`; cookie session via Axios `withCredentials`; feed at `/dashboard`; `/feed` → redirect; optional `AUTH_SESSION_COOKIE_NAME` for middleware when cookie exists on app origin.”*

---

*End of handoff.*
