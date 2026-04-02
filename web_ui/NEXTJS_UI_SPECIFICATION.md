# Next.js Frontend Specification — arXiv Lens

**Audience:** Engineers and AI coding agents implementing the web application.  
**Backend:** FastAPI REST API (see repository root). **Design:** Olive & wheat (warm editorial UI, no blue/violet primaries).  
**HTML/CSS reference:** `web_ui/` (`styles.css`, `pages.css`, `*.html`).

---

## 1. How this document relates to the repo

Read in this order when implementing:

| Document | Path | Use |
|----------|------|-----|
| **API contract** | `API_SPECIFICATION.md` | Endpoints, methods, JSON shapes, auth (httpOnly cookie), errors |
| **Data model** | `DATABASE_SPECIFICATION.md` | Field names for `UserSettings`, `UserPaper`, `PaperExplanation`, enums |
| **Original UI notes** | `UI_DESIGN_SPECIFICATION.md` | Extra interaction notes (some tokens differ; **prefer this file + mockups** for visuals) |
| **Infra** | `INFRA_DATAFLOW_SPECIFICATION.md` | Deployment, env wiring if relevant |
| **This spec** | `web_ui/NEXTJS_UI_SPECIFICATION.md` | Next.js structure, routes, components, **API ↔ UI mapping**, Olive & wheat tokens |

**Non-goals:** This document does not redefine backend behavior; if the API returns a field not listed here, follow the API.

---

## 2. Product summary

**arXiv Lens** is a logged-in web app where researchers set a **natural-language filtering goal** and arXiv categories/topics. A background **pipeline** scrapes and evaluates papers; the **Feed** shows daily recommendations with scores and short agent rationales. Users **accept** or **reject** (with required feedback on reject). **Library** stores accepted papers; users can request a **longer AI explanation** (markdown), shown **inline under the card** (canonical UX). **Terminal** holds settings (goal, tags, pipeline trigger, preferences).

---

## 3. Technology stack (recommended)

| Layer | Choice | Notes |
|-------|--------|--------|
| Framework | **Next.js** (App Router, **React 18+**) | Use `app/` directory |
| Language | **TypeScript** | Strict mode |
| Styling | **Tailwind CSS** + **CSS variables** | Map `web_ui/styles.css` `:root` tokens into `tailwind.config` theme extension |
| Components | **shadcn/ui** (optional) | Align Radix primitives with Olive & wheat tokens |
| Markdown | **react-markdown** + **remark-gfm** | Library explanations from API are markdown strings |
| HTTP | **fetch** (or axios) | `credentials: 'include'` for cookie auth |
| Forms | **react-hook-form** + **zod** (optional) | Reject modal, settings, auth |

---

## 4. Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Yes | Base URL of FastAPI (e.g. `https://api.example.com` or `http://localhost:8000`) — no trailing slash |
| `NEXT_PUBLIC_APP_URL` | Optional | Canonical site URL for links/metadata |

All API calls: `` `${NEXT_PUBLIC_API_URL}/api/v1/...` `` unless your infra uses a Next.js rewrite (document the rewrite in `next.config.js` if so).

---

## 5. Authentication model (must match API)

Per `API_SPECIFICATION.md` §1.2:

- Backend sets an **httpOnly**, **Secure**, **SameSite=Lax** **cookie** on successful login/register — **not** `localStorage` JWT for primary session.
- Frontend: every mutating or protected request must send cookies (`credentials: 'include'` in fetch).
- On **401**: clear client user state and **redirect to `/login`**.
- Implement **middleware** (`middleware.ts`) or **layout guards** for protected routes: unauthenticated users hitting `/feed`, `/library`, `/terminal` → redirect `/login`.

**Public routes:** `/`, `/login`, `/register` (exact paths may follow your `app/` tree; names must stay consistent).

---

## 6. Route map (App Router)

Suggested URL → file mapping:

| URL | File | Access |
|-----|------|--------|
| `/` | `app/page.tsx` | Public — landing |
| `/login` | `app/(auth)/login/page.tsx` | Public |
| `/register` | `app/(auth)/register/page.tsx` | Public |
| `/feed` | `app/(app)/feed/page.tsx` | Protected — **daily feed** (same as legacy doc’s “dashboard”) |
| `/library` | `app/(app)/library/page.tsx` | Protected |
| `/terminal` | `app/(app)/terminal/page.tsx` | Protected |

Use a **layout** `app/(app)/layout.tsx` with the **app shell** (top bar + sidebar + outlet). Landing and auth use `app/(auth)/layout.tsx` or minimal layout without shell.

**Naming:** The API uses “feed” as the resource; using `/feed` keeps URLs aligned. If you prefer `/dashboard`, add a **redirect** from `/dashboard` → `/feed` for bookmarks.

---

## 7. Design system — Olive & wheat (canonical)

**Principle:** Warm paper backgrounds, **olive** (`#6b7c4f`) for primary actions and chrome, **moss** (`#4d5c32`) for pipeline / activity, **amber** (`#a67c38`) for links and “show more”. **No blue or violet** as primary UI colors.

### 7.1 CSS variables (implement as Tailwind theme)

| Token | Hex | Usage |
|-------|-----|--------|
| `--stone-50` | `#fcf9f3` | Page background |
| `--stone-100` | `#f5efe4` | Hover, secondary surfaces |
| `--stone-200` | `#e2d9c8` | Borders, inputs |
| `--sage-50` | `#f4f6f0` | Panels, tags, agent/explain blocks |
| `--sage-200` | `#c9cfa8` | Soft borders, score strip start |
| `--sage-500` | `#6b7c4f` | **Primary:** buttons, nav emphasis, focus rings |
| `--sage-700` | `#454f33` | Headings on page, score text |
| `--moss` | `#4d5c32` | Pipeline pill text/dot |
| `--moss-light` | `#eef2e4` | Pipeline pill background |
| `--amber-warm` | `#a67c38` | Links, secondary emphasis |
| `--amber-soft` | `#faf6e8` | Soft highlights |
| `--text-primary` | `#1c1917` | Body text |
| `--text-secondary` | `#57534e` | Secondary |
| `--text-muted` | `#78716c` | Metadata |

**Fonts:** `Inter` (UI), `JetBrains Mono` (arxiv IDs, scores, dates, pipeline states).  
**Radii:** `--radius-lg` 16px (cards), `--radius-md` 12px (buttons), `--radius-sm` 8px (tags).

---

## 8. TypeScript types (mirror API)

Align with `GET /api/v1/feed` and `GET /api/v1/library` item shape:

```typescript
type PaperListItem = {
  user_paper_id: string; // UUID
  paper_id: string; // e.g. "arxiv:2401.12345"
  title: string;
  authors: string[];
  abstract: string;
  agent_score: number | null;
  agent_explanation: string | null;
  source_url: string;
};
```

**Feed stats** (`GET /api/v1/feed/stats`):

```typescript
type FeedStats = {
  total_scraped_today: number;
  evaluated_by_agent: number;
  recommended_today: number;
};
```

**Explain response** (`POST /api/v1/library/{user_paper_id}/explain`):

```typescript
type ExplainResponse = {
  level: string; // e.g. "professional" — matches `library_explanation_level` in settings
  explanation: string; // markdown
};
```

**Settings** (`GET`/`PUT /api/v1/settings`): body should match `UserSettings` in `DATABASE_SPECIFICATION.md` (use exact field names: `filtering_goal`, `categories`, `topics`, `authors`, `content_interest`, `pdf_parser_mode`, `library_explanation_level`, `notification_time`, `notification_channel`). If `GET` response shape is not fully documented in `API_SPECIFICATION.md`, **derive from DB** and keep types in `lib/types/settings.ts`.

**Explanation levels (DB):** `library_explanation_level` and cached explanations use values such as **`professional` | `student` | `kid`** (see `Database` — `PaperExplanation.explanation_level`). Map UI labels: “Simplified” → **`kid`** if the product keeps that naming.

**Pipeline** (`GET /api/v1/pipeline/{task_id}/status`):

```typescript
type PipelineTaskStatus = {
  task_id: string;
  state: string; // e.g. "PROCESSING_PDFS"
  progress: number; // 0–100
};
```

---

## 9. API ↔ screen mapping

| UI area | Method | Endpoint | Notes |
|---------|--------|----------|--------|
| Landing CTA | — | — | Links to `/register`, `/login`, `/feed` (demo) |
| Register / Login | `POST` | `/auth/register`, `/auth/login` | Cookie set by server |
| Feed list | `GET` | `/api/v1/feed` | Render `PaperCard` list |
| Feed stats | `GET` | `/api/v1/feed/stats` | Three stat pills |
| Accept | `POST` | `/api/v1/feed/{user_paper_id}/accept` | Remove or animate card out |
| Reject | `POST` | `/api/v1/feed/{user_paper_id}/reject` | **Body `{ comment: string }` required** — 202 Accepted |
| Library list | `GET` | `/api/v1/library` | Same item shape as feed |
| Explain | `POST` | `/api/v1/library/{user_paper_id}/explain` | Returns markdown; **inline UI** (see §12) |
| Remove from library | `DELETE` | `/api/v1/library/{user_paper_id}` | 204 |
| Settings | `GET`, `PUT` | `/api/v1/settings` | Terminal tabs |
| Trigger pipeline | `POST` | `/api/v1/pipeline/trigger` | Returns `{ task_id }` |
| Poll pipeline | `GET` | `/api/v1/pipeline/{task_id}/status` | Poll until terminal state |
| Cancel pipeline | `POST` | `/api/v1/pipeline/{task_id}/cancel` | Optional |

---

## 10. App shell (all protected pages)

**Required elements:**

1. **Top bar:** Wordmark **arxiv**lens** (link to `/feed`), **pipeline status** pill (right).  
2. **Sidebar:** Nav links **Feed** → `/feed`, **Library** → `/library`, **Terminal** → `/terminal`; **Trigger run** button → `POST /api/v1/pipeline/trigger` then poll; footer **email** + **Sign out** (clear session / call logout if API adds one).  
3. **Main:** Scrollable content, max width ~1180px, padding per mockup.

**Pipeline pill (states):**

- **Idle:** muted dot + “idle” / last completed  
- **Running:** moss dot + pulse (respect `prefers-reduced-motion`) + label `state` + `progress` % from API  
- **Error:** neutral slate styling + “Error”

**Removed from mockup (do not re-add unless product asks):** decorative logo square, avatar circle — **text-only brand** is fine.

---

## 11. Page specifications

### 11.1 Landing (`/`)

- Sections: nav (Log in / Get started), hero, “How it works” (3 steps), optional feed preview card, footer.  
- **No** app shell.  
- Links: `register`, `login`, optional `feed` for logged-in demo.

### 11.2 Feed (`/feed`)

- **Header:** “Today’s feed” + **today’s date** (mono, muted).  
- **Stats row:** `total_scraped_today`, `evaluated_by_agent`, `recommended_today`.  
- **List:** `PaperCard` per item.  
- **Paper card:** score strip (gradient by score band), categories (`paper_id` / categories if API adds them), title, authors, **agent_explanation** block, abstract clamp + “Show more”, actions: arXiv link (`source_url`), PDF if available, **Accept**, **Reject**.  
- **Reject:** modal with **required** `comment` textarea; submit → 202; optimistic UI optional.  
- **Empty:** copy + “Trigger pipeline” if no items.

### 11.3 Library (`/library`)

- **Toolbar:** search (client-side filter on title/authors by default), chips **All / Explained / Unread** (map to client filters or API query if added later).  
- **Cards:** compact: tag(s), score, title, meta line, actions **arXiv**, **Explain**, **Remove**.  
- **Explain — canonical: inline expansion only** (see §12).  
- **Badge “Explained”** if explanation exists for current user level (from cache or local state after fetch).

### 11.4 Terminal (`/terminal`)

- **Tabs:** Filtering / Library (prefs) / Pipeline / Account.  
- **Filtering:** `filtering_goal` textarea, `categories`, `topics`, `authors` — tag/chip inputs; save → `PUT /api/v1/settings`.  
- **Library prefs:** `library_explanation_level` radio (`professional` | `student` | `kid`), `content_interest` checkboxes.  
- **Pipeline:** `notification_time`, `pdf_parser_mode`, trigger button, **last run** summary (if API exposes it; else show task status from last `task_id` client-side).  
- **Account:** email read-only; **password change** is **not** in `API_SPECIFICATION.md` — hide or stub until backend exists.

### 11.5 Auth (`/login`, `/register`)

- Centered card on warm background; fields per API; success → cookie → redirect `/feed`.

---

## 12. Library “Explain” — inline expansion (mandatory UX)

**Do not implement a side drawer** for explanations; the product choice is **inline under the card**.

**Behavior:**

1. User clicks **Explain** on a library row identified by `user_paper_id`.  
2. UI sets loading state on that row (skeleton or spinner in the expansion area).  
3. `POST /api/v1/library/{user_paper_id}/explain` returns `{ level, explanation }`.  
4. Render a panel **immediately below** the card (same column), visually attached (see `.lib-card-stack` + `.explain-inline` in `pages.css`).  
5. Header: label e.g. `✦ AI explanation · {level}` and **Close** (collapses panel).  
6. Body: render `explanation` with **markdown** (headings, lists, fenced code).  
7. **Explain** toggles to **Hide** when open (or use a single toggle control).  
8. **Cache:** if the user reopens the same paper at the same `library_explanation_level`, backend may return cached text — still call POST or add GET if API adds idempotent fetch later.

**Accessibility:** `aria-expanded` on the trigger, `role="region"` + `aria-label` on the panel.

---

## 13. Score visualization

- **Strip at top of card:** interpolate color from low → high (use muted warm grey → moss/olive → deep sage per `UI_SPEC_CURSOR.md` / mockups).  
- **Numeric badge:** `agent_score` in monospace.  
- Expose `aria-label` e.g. `Score: 9.5 out of 10`.

---

## 14. Errors & empty states

- **Global:** toast or inline banner for API errors (`error.code`, `error.message`).  
- **Feed empty:** friendly copy + CTA to Terminal / trigger pipeline.  
- **Network failure:** retry on feed/library.  
- **Reject validation:** 400 if comment missing — show field error.

---

## 15. Accessibility

- Focus visible on all interactive elements.  
- Modal: `role="dialog"`, focus trap, Escape closes.  
- Color is not the only indicator for state (icons + text).  
- Respect `prefers-reduced-motion` for pipeline pulse.

---

## 16. Suggested `app/` tree

```
app/
  layout.tsx                 # fonts, html/body
  page.tsx                   # landing
  (auth)/
    login/page.tsx
    register/page.tsx
  (app)/
    layout.tsx               # AppShell (sidebar + topbar)
    feed/page.tsx
    library/page.tsx
    terminal/page.tsx
components/
  layout/
    AppShell.tsx
    Sidebar.tsx
    Topbar.tsx
    PipelinePill.tsx
  feed/
    PaperCard.tsx
    RejectModal.tsx
    FeedStats.tsx
  library/
    LibraryCard.tsx
    ExplanationInline.tsx    # markdown body
  terminal/
    FilteringForm.tsx
    LibraryPrefsForm.tsx
    PipelinePanel.tsx
  ui/                        # shadcn primitives
lib/
  api.ts                     # typed fetch wrappers
  types.ts
```

---

## 17. Compatibility checklist (before merge)

- [ ] All protected routes require session cookie.  
- [ ] Feed/library types match API JSON field names.  
- [ ] Reject always sends non-empty `comment`.  
- [ ] Explain uses **inline** panel only; markdown rendered safely (no raw HTML injection).  
- [ ] Pipeline trigger stores `task_id` and polls `status` until idle/complete/error.  
- [ ] Olive & wheat tokens applied consistently (no default blue primary buttons).  
- [ ] Mockups in `web_ui/` matched for layout parity (minus removed avatar/mark).

---

## 18. References

- `API_SPECIFICATION.md` — REST contract  
- `DATABASE_SPECIFICATION.md` — `UserSettings`, `UserPaper`, `PaperExplanation`  
- `UI_DESIGN_SPECIFICATION.md` — additional interaction notes (token names may differ; prefer **Olive & wheat** here)  
- `web_ui/styles.css`, `pages.css`, `*.html` — visual reference

---

*End of Next.js UI specification.*
