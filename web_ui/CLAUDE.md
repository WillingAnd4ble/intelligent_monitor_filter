# Web UI — arXiv Lens Frontend

## What This Is
Next.js 15 frontend for an undergrad thesis project: a multi-agent LLM system that monitors arXiv, filters publications based on user-defined goals, and delivers personalized recommendations. This is the user-facing "terminal" — built with Cursor. The brand name in the UI is **arxivlens**.

## Tech Stack
- **Framework**: Next.js 15 (App Router), React 19, TypeScript (strict)
- **Styling**: Tailwind CSS 3.4 with custom "Olive & Wheat" design tokens
- **Data Fetching**: TanStack React Query 5 + Axios (httpOnly cookie auth)
- **Forms**: react-hook-form 7 + Zod validation
- **Markdown**: react-markdown + remark-gfm (for AI explanations)
- **Icons**: Lucide React
- **Fonts**: Inter (UI), JetBrains Mono (data/scores/IDs)

## How to Run
```bash
npm install
npm run dev          # Dev server on http://localhost:3000
npm run build        # Production build
npm run lint         # ESLint
```

Requires backend running on `http://localhost:8000` (set in `.env.local` as `NEXT_PUBLIC_API_URL`).

## Project Structure
```
web_ui/
├���─ app/
│   ├── layout.tsx                    # Root layout: fonts, providers wrapper
│   ���── page.tsx                      # Landing page (/)
│   ├── providers.tsx                 # QueryClientProvider + auth:logout listener
│   ├── globals.css                   # Tailwind base + design tokens + markdown styles
│   ├── (auth)/
│   │   ├── layout.tsx                # Centered card layout for auth pages
│   │   ├── login/page.tsx            # Login form → POST /auth/login
│   │   └���─ register/page.tsx         # Register form �� POST /auth/register
│   └── (app)/
│       ���── layout.tsx                # AppShell wrapper (topbar + sidebar + content)
│       ├── dashboard/page.tsx        # Feed view: stats + paper cards + accept/reject
│       ├── library/page.tsx          # Accepted papers: search + explain + remove
│       └── terminal/page.tsx         # Settings: 4 tabs (Filtering, Library, Pipeline, Account)
├── components/
│   ├── layout/
│   │   ├── AppShell.tsx              # Grid layout: sidebar(232px) + main, PipelineProvider wrapper
│   │   ├── Topbar.tsx                # Header: brand wordmark + PipelinePill
│   │   ├── Sidebar.tsx               # Nav links + trigger button + sign out
│   │   └── PipelinePill.tsx          # Pipeline status indicator (idle/running/error)
│   ├── feed/
│   │   ├── FeedStats.tsx             # 3 stat cards (scraped, evaluated, recommended)
│   ���   ├── PaperCard.tsx             # Full paper card: score, metadata, explanation, actions
│   │   └── RejectModal.tsx           # Modal with required comment textarea (Zod validated)
│   ├── library/
│   │   ├���─ LibraryCard.tsx           # Compact paper card: score, title, explain/remove actions
│   │   └── ExplanationInline.tsx     # Markdown explanation block (react-markdown + remark-gfm)
│   └── terminal/
│       └── TerminalClient.tsx        # Monolithic settings component: 4 tabs, TagBlock sub-component
├── contexts/
│   └── pipeline-context.tsx          # Pipeline state: phase, progress, taskId, polling logic
├── lib/
│   ├── api.ts                        # Typed API functions (login, getFeed, acceptPaper, etc.)
│   ├── axios.ts                      # Axios instance: baseURL, withCredentials, 401 interceptor
│   ├── auth-errors.ts                # Error parsing for auth forms
│   ├── types.ts                      # PaperListItem, FeedStats, ExplainResponse, PipelineTaskStatus
│   ├── types/settings.ts             # UserSettings type
│   └── cn.ts                         # Class name combiner utility
├── middleware.ts                      # Optional auth guard (only if AUTH_SESSION_COOKIE_NAME env set)
├── next.config.ts                     # /feed → /dashboard redirect
├── tailwind.config.ts                 # Custom colors (stone, sage, moss, amber, ink) + radii + fonts
├── .env.example                       # Template for env vars
└── Specs: NEXTJS_UI_SPECIFICATION.md, UI_SPEC_CURSOR.md, API_SPECIFICATION.md, AI_SYSTEM_SPECIFICATION.md
```

## Pages & Routes

| Route | Auth | Component | Purpose |
|-------|------|-----------|---------|
| `/` | Public | `app/page.tsx` | Landing: hero, how-it-works, CTAs |
| `/login` | Public | `app/(auth)/login/page.tsx` | Login form |
| `/register` | Public | `app/(auth)/register/page.tsx` | Registration form |
| `/dashboard` | Protected | `app/(app)/dashboard/page.tsx` | Paper feed with accept/reject |
| `/library` | Protected | `app/(app)/library/page.tsx` | Accepted papers + explanations |
| `/terminal` | Protected | `app/(app)/terminal/page.tsx` | Settings (4 tabs) |
| `/feed` | — | Redirects to `/dashboard` | Via next.config.ts |

## API Integration (lib/api.ts)

All calls go through Axios with `withCredentials: true` (httpOnly cookies). 401 responses trigger auto-redirect to `/login`.

| Function | Method | Endpoint | Notes |
|----------|--------|----------|-------|
| `login()` | POST | `/auth/login` | Backend sets cookie |
| `register()` | POST | `/auth/register` | Backend sets cookie |
| `getFeed()` | GET | `/api/v1/feed` | Returns PaperListItem[] |
| `getFeedStats()` | GET | `/api/v1/feed/stats` | Returns FeedStats |
| `acceptPaper()` | POST | `/api/v1/feed/{id}/accept` | **Backend endpoint missing** |
| `rejectPaper()` | POST | `/api/v1/feed/{id}/reject` | **Backend endpoint missing** |
| `getLibrary()` | GET | `/api/v1/library` | Returns accepted papers |
| `explainPaper()` | POST | `/api/v1/library/{id}/explain` | **Backend endpoint missing** |
| `removeFromLibrary()` | DELETE | `/api/v1/library/{id}` | **Backend endpoint missing** |
| `getSettings()` | GET | `/api/v1/settings` | Returns UserSettings |
| `putSettings()` | PUT | `/api/v1/settings` | Partial update |
| `triggerPipeline()` | POST | `/api/v1/pipeline/trigger` | Returns { task_id } |
| `getPipelineStatus()` | GET | `/api/v1/pipeline/{id}/status` | **Backend endpoint missing** |
| `cancelPipeline()` | POST | `/api/v1/pipeline/{id}/cancel` | Backend returns static response |

## State Management

### Pipeline Context (`contexts/pipeline-context.tsx`)
Manages pipeline execution lifecycle:
- **States**: idle → running (with progress 0-100%) → idle/error
- **Polling**: GET `/api/v1/pipeline/{taskId}/status` every 2s, max 120 polls (4 min timeout)
- **Completion**: Detected by progress >= 100 or state matching `complete|done|success|finished`
- Used by: Sidebar trigger button, PipelinePill in topbar

### React Query (via `app/providers.tsx`)
- 30s staleTime, 1 retry, refetch on window focus
- Query keys: `["feed"]`, `["feedStats"]`, `["library"]`, `["settings"]`
- Mutations invalidate relevant queries (e.g., accept/reject invalidate `["feed"]`)
- `auth:logout` custom event clears entire query cache

## Design System ("Olive & Wheat")

### Colors (defined in globals.css + tailwind.config.ts)
- **Stone** (neutrals): 50 `#fcf9f3`, 100 `#f5efe4`, 200 `#e2d9c8`
- **Sage** (primary): 50 `#f4f6f0`, 200 `#c9cfa8`, 500 `#6b7c4f`, 700 `#454f33`
- **Moss** (pipeline/activity): `#4d5c32`, light `#eef2e4`
- **Amber** (links/emphasis): warm `#a67c38`, soft `#faf6e8`
- **Ink** (text): primary `#1c1917`, secondary `#57534e`, muted `#78716c`

### Typography
- **Inter**: UI text, headings (weights 500-700)
- **JetBrains Mono**: arXiv IDs, scores, timestamps, monospace data

### Border Radii
- lg: 16px, md: 12px, sm: 8px

**Important**: No blue primaries. The palette is intentionally warm/organic (olive, sage, wheat tones).

## Authentication Flow
1. User submits form on `/login` or `/register`
2. Backend sets httpOnly cookie in response header
3. Frontend redirects to `/dashboard` (or `?next` param)
4. All subsequent Axios requests auto-send cookie (`withCredentials: true`)
5. On 401: Axios interceptor dispatches `auth:logout` event → clears cache → redirects to `/login`

**Sign out**: Currently just navigates to `/login` — does NOT call backend `/auth/logout` endpoint.

## What Is Working (~85% complete)
- Landing page, login, register with error handling
- Full feed view: paper cards with scores, explanations, expand/collapse abstracts
- Accept/reject UI with required feedback modal (Zod validated)
- Library with client-side search, inline markdown explanations, remove action
- Terminal: all 4 tabs (Filtering with tag inputs, Library level selector, Pipeline trigger, Account display)
- Pipeline status polling with real-time progress pill
- Complete design system (Olive & Wheat tokens throughout)
- TypeScript strict, React Query caching, 401 auto-redirect

## What Is Missing / Not Working
1. **Backend endpoints not implemented**: accept, reject, explain, remove, pipeline status — UI calls them but backend will 404/405
2. **Sign out doesn't call API**: Just navigates away, cookie may persist
3. **Password change**: Account tab shows stub, no form or endpoint
4. **Library tabs** (All/Explained/Unread): Spec mentions them, only client-side search exists
5. **Pagination**: No infinite scroll or pagination for large feeds
6. **Notification config UI**: Time picker exists but backend has no scheduler
7. **"Explained" badge**: Spec mentions it for library cards, not implemented

## Inconsistencies to Watch
- **Auth response**: API spec says `{ token }` but frontend expects cookie auto-set (httpOnly). Both are true — backend sets cookie AND could return token, but frontend ignores token.
- **Explanation level**: Code uses `"kid"` but label shows "Simplified (kid)" — consistent in frontend but verify backend field value.
- **Pipeline status strings**: Context checks for `complete|done|success|finished` regex — backend must return one of these in the `state` field.
- **NEXT_PUBLIC_DEMO_EMAIL**: Used in sidebar/account tab for email display. Not a real user email query — just env var fallback.

## Environment Variables
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000          # Backend URL (required)
NEXT_PUBLIC_DEMO_EMAIL=you@research.example        # Display email (optional)
AUTH_SESSION_COOKIE_NAME=access_token              # Middleware guard (optional, disabled if unset)
```

## Development Notes
- CORS: Backend must allow `http://localhost:3000` with `allow_credentials=True`
- The `/feed` route redirects to `/dashboard` via `next.config.ts` — all feed logic lives on dashboard page
- Middleware auth guard is optional and typically disabled in local dev (cross-origin cookies aren't visible to Next.js middleware)
- `globals.css` contains `.explain-md` class for markdown rendering styles