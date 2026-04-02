# Web UI Specification — Cursor design workspace

**Product:** Agent-based personalized arXiv publication monitoring (feed, library, pipeline terminal).  
**Scope:** Design tokens, layout, and component rules.

**Next.js implementation (for agents):** use **`NEXTJS_UI_SPECIFICATION.md`** in this folder — full API mapping, routes, components, and **inline-only** Library Explain UX aligned with `API_SPECIFICATION.md` at repo root.

**Selected visual design:** **Olive & wheat** — wheat-paper neutrals, yellow-green olive (`#6b7c4f`) as primary chrome, butter-amber (`#a67c38`) for links and emphasis, moss green (`#4d5c32`) for pipeline / activity. No blue or violet in the primary palette.

**Static HTML mockup (browse locally):** shared **`styles.css`** (tokens + app shell + feed card) and **`pages.css`** (landing, library, terminal, auth). Pages:

| File | Content |
|------|---------|
| `index.html` | Landing — hero, how it works, feed preview, footer |
| `feed.html` | App — today’s feed, stats, two paper cards |
| `library.html` | App — library grid + **Explain (inline)** demo under one card |
| `terminal.html` | App — settings (filtering, library prefs, pipeline, account) |
| `login.html` | Auth — centered sign-in card |
| `register.html` | Auth — registration card |

---

## 1. Design goals

| Goal | Intent |
|------|--------|
| **Signal over noise** | Dense information (scores, IDs, pipeline state) stays scannable; decorative chrome is minimal. |
| **Long-session comfort** | Warm off-whites and muted contrasts reduce eye strain during reading and triage. |
| **Trust & clarity** | Actions (accept/reject/save) are obvious; AI explanations read as supporting content, not marketing. |
| **Consistency** | One monospace voice for data; one sans voice for UI copy. |

---

## 2. Global layout (app shell)

- **Top bar (~58px):** Wordmark left; pipeline status pill right. Frosted warm background, bottom border `stone-200`.
- **Sidebar (~232px desktop):** Nav — Feed (`/feed`), Library (`/library`), Terminal (`/terminal`); primary **Trigger run**; footer with account hint.
- **Main:** Scrollable content, max width ~1180px, padding ~36px / 40px.
- **Mobile:** Sidebar hidden; top bar remains (see `styles.css` breakpoint).

---

## 3. Color system — Olive & wheat (canonical)

Warm editorial palette. Surfaces are never cold white alone; primary UI chrome is **olive**; **moss** differentiates pipeline state; **amber** supports links and secondary emphasis.

| Token | Hex | Usage |
|-------|-----|--------|
| `--stone-50` | `#fcf9f3` | Page background |
| `--stone-100` | `#f5efe4` | Gradient stop, hover fills |
| `--stone-200` | `#e2d9c8` | Borders, dividers |
| `--sage-50` | `#f4f6f0` | Tinted panels, tags, agent block |
| `--sage-200` | `#c9cfa8` | Soft borders, score strip start |
| `--sage-500` | `#6b7c4f` | **Primary:** CTAs, nav label, focus brand, tag borders |
| `--sage-700` | `#454f33` | Headings on page, strong headings, score badge |
| `--moss` | `#4d5c32` | Pipeline pill text/dot, idle/running emphasis |
| `--moss-light` | `#eef2e4` | Pipeline pill background |
| `--amber-warm` | `#a67c38` | “Show more”, tertiary emphasis |
| `--amber-soft` | `#faf6e8` | Badge / highlight backgrounds (if used) |
| `--text-primary` | `#1c1917` | Body emphasis |
| `--text-secondary` | `#57534e` | Secondary copy |
| `--text-muted` | `#78716c` | Metadata, timestamps |

**Score strip:** Linear gradient `sage-200` → `sage-500`.  
**Shadows on primary actions:** `rgba(107, 124, 79, 0.35)` for trigger button.  
**Pipeline pill border:** `rgba(77, 92, 50, 0.28)`.

**Semantic (align with UI):** success / accepted → olive tones; dismissed / neutral → muted slate; avoid blue for “info” — use warm slate or amber on soft cream.

**Score bands (0–10):** low → warm muted grey-brown; mid → moss/olive family; high → `sage-700` / `sage-500`.

---

## 4. Typography

- **UI / headings:** `Inter`, `system-ui`, sans — weights 500–700.
- **Data:** `JetBrains Mono`, `ui-monospace` — arXiv IDs, scores, dates, pipeline labels.

Scale: ~11px nav labels → 13–15px body → ~1.85rem page title; line-height ≥ 1.4 for body.

**Radii:** `--radius-lg` 16px (cards, pills), `--radius-md` 12px (nav, buttons), `--radius-sm` 8px (tags).

---

## 5. Key screens (content requirements)

1. **Landing:** Hero, value prop, CTAs, how it works.
2. **Feed (`/feed`):** Title + date; stats row; paper cards (score strip, tags, title, authors, agent block, abstract, actions).
3. **Library:** Search, filters, compact cards; **inline Explain** panel only (see `NEXTJS_UI_SPECIFICATION.md` §12).
4. **Terminal:** Tabs for filtering, library prefs, pipeline, account.

---

## 6. Component notes

- **Paper card:** Score strip on top; monospace metadata; agent rationale in `sage-50` with `sage-200` border.
- **Buttons:** Primary `sage-500` / hover `sage-700`; outline and ghost; accept uses `sage-50` + `sage-500` border.
- **Pipeline pill:** Moss dot + `moss-light` fill; running state can add pulse (respect reduced motion).
- **Inputs (future):** `stone-100` background, `stone-200` border, focus ring `sage-500`.

---

## 7. Accessibility

- Focus visible on all controls; minimum ~44px touch targets.
- Score + state not conveyed by color alone (text/icon paired).
- Respect `prefers-reduced-motion` for pulses in production.

---

*Derived from project `UI_DESIGN_SPECIFICATION.md`, narrowed to the selected Olive & wheat mockup.*
