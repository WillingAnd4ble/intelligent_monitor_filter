# UI Design Specification
**Project:** Agent-based Information System for Personalized arXiv Publication Monitoring  
**Stack:** Next.js · Tailwind CSS · shadcn/ui · Framer Motion

---

## 1. Design Philosophy

### Core Principles
- **Signal over noise** — Every element earns its space. No decorative chrome.
- **Editorial clarity** — Typography does the heavy lifting; layout breathes.
- **Calm intelligence** — The system is working hard in the background. The UI should feel effortless.
- **Precision aesthetics** — Monospace for data, humanist sans for prose. Tight grids, deliberate whitespace.

### Tone References
- Planetscale dashboard (dark emerald/forest night palette, precision data UI)
- Stripe (clean financial clarity, typographic confidence)
- Linear.app (information density without clutter)
- Vercel (monochrome baseline — we add life with emerald)
- Raycast (tight dark surfaces, crisp accent pops)

---

## 2. Design Tokens

> **Color story:** The palette takes its cue from bioluminescence — deep forest at rest, lit from within by emerald when something is alive and active. Backgrounds are near-black with a barely-perceptible green undertone; they read as rich, not cold. The emerald accent (`#10B981` → `#34D399`) carries all meaning: accepted papers, links, focus states, AI activity. Teal (`#2DD4BF`) signals the system thinking — pipeline pulses, processing states. Nothing red, nothing yellow. Dismissal and errors use a cool slate (`#64748B`) — neutral, not punishing.

### 2.1 Color Palette

```
Theme: Dark-first. Forest night — deep, natural, intelligent.
All surfaces carry a subtle green undertone; nothing reads as neutral grey.

Background layers (z-axis stacking):
  --bg-base:        #070D0A   // deepest layer — page background (near-black, forest-tinted)
  --bg-surface:     #0C1410   // cards, panels — just enough lift
  --bg-elevated:    #111E16   // modals, popovers, hover states
  --bg-subtle:      #0F1913   // sidebar, nav — slightly warmer than surface

Borders:
  --border-dim:     #162119   // hairline dividers, barely visible
  --border-default: #1F3228   // standard card/input borders
  --border-active:  #2A4A37   // focused inputs, hovered cards

Text:
  --text-primary:   #EDF5EF   // headings, labels — cool white with a breath of green
  --text-secondary: #7EA88B   // body copy, descriptions — sage
  --text-muted:     #3A5443   // timestamps, metadata, placeholders — forest shadow
  --text-inverse:   #070D0A   // text rendered on bright/accent backgrounds

Accent — Emerald Spectrum (the hero color):
  --accent-500:     #10B981   // emerald-500: primary CTA, focus rings, key highlights
  --accent-400:     #34D399   // emerald-400: hover states on accent elements
  --accent-300:     #6EE7B7   // emerald-300: subtle glow, chip text, "Show more" links
  --accent-200:     #A7F3D0   // emerald-200: very soft highlight, rarely used
  --accent-900:     #022C22   // emerald-950: tag/badge background fills

Secondary — Cyan / Teal (pipeline, info, AI activity):
  --teal-400:       #2DD4BF   // pipeline running pulse, info states
  --teal-300:       #5EEAD4   // teal highlights
  --teal-900:       #042F2E   // teal badge backgrounds

Semantic:
  --accepted:       #34D399   // accepted paper state (bright emerald)
  --accepted-bg:    #022C22
  --processing:     #2DD4BF   // pipeline running/active (teal)
  --processing-bg:  #042F2E
  --dismissed:      #64748B   // rejected/dismissed — cool slate, neutral non-aggressive
  --dismissed-bg:   #1A2535
  --info:           #38BDF8   // sky blue for system info, read-only states

Score colors (agent_score 0–10):
  --score-high:     #34D399   // 8.0–10.0  bright emerald
  --score-mid:      #2DD4BF   // 5.0–7.9   teal
  --score-low:      #3A5443   // 0.0–4.9   muted forest (not grey, not yellow)
```

### 2.2 Typography

```
Font Stack:
  Display/Headings:   'Inter', system-ui, sans-serif  (weights: 500, 600, 700)
  Body/UI:            'Inter', system-ui, sans-serif  (weights: 400, 500)
  Monospace/Data:     'JetBrains Mono', 'Fira Code', monospace  (weights: 400, 500)

Scale (rem, line-height):
  --text-xs:    0.75rem  / 1.0rem   // labels, badges, timestamps
  --text-sm:    0.875rem / 1.25rem  // metadata, secondary text
  --text-base:  1rem     / 1.5rem   // body copy
  --text-lg:    1.125rem / 1.75rem  // card titles, section headers
  --text-xl:    1.25rem  / 1.75rem  // page sub-headings
  --text-2xl:   1.5rem   / 2rem     // page headings
  --text-3xl:   1.875rem / 2.25rem  // hero text
  --text-5xl:   3rem     / 3.5rem   // landing hero

Monospace is used for:
  - arXiv paper IDs        (arxiv:2401.12345)
  - agent_score values     (9.5)
  - timestamps / dates
  - pipeline progress %    (65%)
  - pipeline state labels  (PROCESSING_PDFS)
```

### 2.3 Spacing & Layout

```
Base unit: 4px (0.25rem)
Scale: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96

Content widths:
  --max-content:   1200px   // main layout container
  --max-prose:     680px    // article/explanation text
  --sidebar-width: 240px    // left nav

Border radius:
  --radius-sm:   4px    // tags, badges, inputs
  --radius-md:   8px    // cards, buttons
  --radius-lg:   12px   // modals, panels
  --radius-xl:   16px   // large cards, sheets
  --radius-full: 9999px // pill shapes, avatars
```

### 2.4 Shadows & Elevation

```
--shadow-sm:    0 1px 3px rgba(0,0,0,0.5), 0 1px 2px rgba(0,0,0,0.7)
--shadow-md:    0 4px 16px rgba(0,0,0,0.6)
--shadow-lg:    0 16px 48px rgba(0,0,0,0.7)
--glow-accent:  0 0 24px rgba(16,185,129,0.12)   // emerald card focus glow
--glow-strong:  0 0 40px rgba(52,211,153,0.18)   // hero elements, active pipeline
```

### 2.5 Motion

```
Easing:
  --ease-out:   cubic-bezier(0.16, 1, 0.3, 1)   // entrance animations
  --ease-in:    cubic-bezier(0.4, 0, 1, 1)       // exit animations
  --ease-spring:cubic-bezier(0.34, 1.56, 0.64, 1)// playful spring

Durations:
  --dur-fast:   100ms   // micro-interactions (hover, active)
  --dur-base:   200ms   // most transitions
  --dur-slow:   350ms   // panel slides, page transitions
  --dur-enter:  500ms   // page-level entrances

Principles:
  - No animation unless it communicates state change
  - Cards fade + translateY(8px) on enter
  - Score badges count up on first render
  - Reject modal slides up from bottom on mobile
  - Skeleton loaders instead of spinners for async content
```

---

## 3. Global Layout & Navigation

### 3.1 App Shell

```
┌─────────────────────────────────────────────────────┐
│  TOPBAR (fixed, h=56px, bg=--bg-subtle, blur)        │
│  [Logo + wordmark]          [Pipeline status] [Avatar]│
├──────────────┬──────────────────────────────────────┤
│              │                                       │
│  SIDEBAR     │   MAIN CONTENT AREA                  │
│  w=240px     │   flex-1, overflow-y scroll           │
│  (fixed)     │   px=32, py=32, max-w=1200            │
│              │                                       │
└──────────────┴──────────────────────────────────────┘
```

**Topbar anatomy:**
- Left: Logo mark (small geometric/abstract glyph in `--accent-500`) + wordmark "arxiv**lens**" in Inter 500
- Center: Nothing (clean)
- Right: `PipelineStatusPill` → `UserAvatar` dropdown

**PipelineStatusPill (topbar):**
- Idle: dim dot + "Idle" text in `--text-muted`
- Running: animated pulsing teal dot + "Running · 65%" in `--teal-400`, `--glow-strong` ring
- Error: slate dot + "Error" in `--dismissed`
- Clicking opens a small popover with the last run's details

**Sidebar:**
- `--bg-subtle` background, `1px` right border in `--border-dim`
- Nav items: icon (16px) + label, `--text-secondary` default, `--text-primary` + `--accent-900` background when active
- Nav structure:
  ```
  ─ Feed            [/dashboard]
  ─ Library         [/library]
  ─ Terminal        [/terminal]
  ── ── ── ── ──
  ─ Trigger Run     [button, not a link]
  ```
- Bottom: user email in `--text-muted` `--text-xs`, "Sign out" link

**Mobile (< 768px):**
- Sidebar collapses to bottom tab bar (4 items: Feed, Library, Terminal, Menu)
- Topbar retains logo + pipeline pill only

---

## 4. Pages

---

### 4.1 `/` — Landing Page

**Purpose:** Explain the product to a new visitor, drive them to register.

**Layout:** Full-width, no sidebar. Single-column, centered.

```
┌──────────────────────────────────────────────┐
│  NAVBAR (transparent → frosted on scroll)     │
│  Logo                         [Login] [Start] │
├──────────────────────────────────────────────┤
│                                               │
│  HERO SECTION                                 │
│  (100vh, centered vertically)                 │
│                                               │
│    [micro badge]                              │
│    "Powered by LLM Agents"                    │
│                                               │
│    Your personal research                     │
│    intelligence layer                         │
│    for arXiv.                                 │
│                                               │
│    [Body: 2 lines max, ~text-lg]              │
│    "Stop drowning in papers. Set your goal,   │
│     let the agent find what matters."         │
│                                               │
│    [Get started →]  [See how it works]        │
│                                               │
│    [Faint grid/mesh gradient bg]              │
│                                               │
├──────────────────────────────────────────────┤
│  HOW IT WORKS (3-column icon + text)          │
│  ① Set your goal  ② Agent filters  ③ Read    │
├──────────────────────────────────────────────┤
│  EXAMPLE FEED CARD (static mockup, blurred)   │
│  "See what your daily feed looks like"         │
├──────────────────────────────────────────────┤
│  FOOTER (minimal: copyright + github link)    │
└──────────────────────────────────────────────┘
```

**Hero typography:**
- Badge: `--text-xs` monospace, `--accent-900` bg, `--accent-300` text, `--radius-full`
- H1: `--text-5xl`, weight 700, `--text-primary`, max-width 640px
- Body: `--text-lg`, `--text-secondary`
- CTA primary: solid `--accent-500` bg, white text, `--radius-md`, h=44px, px=24px
- CTA secondary: `--border-default` border, `--text-secondary`, same size, transparent bg

**Background treatment:**
- Radial gradient from `rgba(16,185,129,0.07)` centered at top → fully transparent at 60% height
- Fine dot grid at 1.5% opacity: `radial-gradient(circle, #34D399 1px, transparent 1px)` at 28px spacing
- Together these create depth: a faint bioluminescent pulse from above

---

### 4.2 `/dashboard` — Feed Page

**Purpose:** Daily paper recommendations. Primary interaction surface.

```
┌─ SIDEBAR ─┬──────────────────────────────────┐
│           │  HEADER (sticky, bg=--bg-base)    │
│           │  "Today's Feed"   [date, mono]    │
│           │                                   │
│           │  STATS ROW (3 pills)              │
│           │  [254 scraped] [23 evaluated]     │
│           │  [4 recommended]                  │
│           │                                   │
│           │  FEED LIST                        │
│           │  ┌─────────────────────────────┐ │
│           │  │ PAPER CARD                  │ │
│           │  └─────────────────────────────┘ │
│           │  ┌─────────────────────────────┐ │
│           │  │ PAPER CARD                  │ │
│           │  └─────────────────────────────┘ │
│           │  ...                              │
└───────────┴──────────────────────────────────┘
```

#### Stats Row

Three inline pills, `--bg-surface`, `--border-dim` border, `--radius-full`:
```
[  📄 254 scraped today  ]  [  🤖 23 evaluated  ]  [  ✦ 4 recommended  ]
```
- Numbers in `--text-primary` Inter 600
- Labels in `--text-muted` `--text-sm`
- Icon in `--accent-400`

#### Paper Card

The centerpiece component. Full-width within content column.

```
┌──────────────────────────────────────────────────────────┐
│  SCORE BAR  ████████░░  9.5                              │
│  (4px tall strip at the very top of card, accent color)  │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  [cs.AI] [cs.LG]           arxiv:2401.12345  2023-01-10  │
│                                                          │
│  LLM Agents in the Wild                                  │
│  (--text-lg, weight 600, --text-primary)                 │
│                                                          │
│  John Doe, Jane Smith, +3 more                           │
│  (--text-sm, --text-muted)                               │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ AGENT EXPLANATION (highlighted block)            │   │
│  │ "This paper directly addresses your goal of..."   │   │
│  │ (--bg-elevated, left border 2px --accent-500)     │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ABSTRACT (collapsed to 3 lines by default)              │
│  "This paper discusses multi-agent..."  [Show more]      │
│                                                          │
│  ──────────────────────────────────────────────────      │
│  [↗ arXiv]  [⬇ PDF]          [✓ Accept]  [✗ Reject]    │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**Card details:**
- `--bg-surface` background, `1px` `--border-default` border, `--radius-xl`
- Score bar: full-width strip at top, color interpolates `--score-low` → `--score-high` based on value, `--radius-xl` on top corners only
- Score badge: positioned absolute top-right, monospace `9.5`, `--text-xl` weight 700
- Category tags: `--accent-900` bg, `--accent-300` text, `--radius-sm`, `--text-xs` monospace uppercase
- arXiv ID + date: `--text-xs` monospace, `--text-muted`, right-aligned
- Title: `--text-lg` weight 600, `--text-primary`, no underline
- Authors: `--text-sm`, `--text-muted`
- Agent explanation block: `--bg-elevated`, left `3px` border `--accent-500`, `--radius-sm`, py=12 px=16, `--text-sm` `--text-secondary`
- Abstract: `--text-sm`, `--text-secondary`, line-clamp-3, "Show more" in `--accent-400`
- Footer divider: `1px` `--border-dim`
- Action buttons:
  - Accept: `--accepted` text + border, hover fills `--accepted-bg`, icon: checkmark
  - Reject: `--dismissed` text + border, hover fills `--dismissed-bg`, icon: ×
  - arXiv / PDF: ghost, `--text-muted`, icon only at `<sm`

**Card hover state:**
- Border transitions to `--border-active`
- `--glow-accent` box-shadow
- 200ms ease transition

**Empty state (no feed):**
```
┌────────────────────────────────────┐
│           [large icon]             │
│  No papers yet for today           │
│  --text-secondary, centered        │
│  [Trigger pipeline →]              │
└────────────────────────────────────┘
```

#### Reject Modal

Triggered by "Reject" button. Slides up from bottom (mobile) or centered dialog (desktop).

```
┌─────────────────────────────────────┐
│  Why are you rejecting this paper?  │
│                                     │
│  [Paper title, truncated, --text-sm]│
│                                     │
│  ┌─────────────────────────────┐    │
│  │ Textarea                    │    │
│  │ "Too theoretical, I need…"  │    │
│  │ min-h: 100px                │    │
│  └─────────────────────────────┘    │
│  --text-xs --text-muted: "Your      │
│  feedback trains the filter."       │
│                                     │
│  [Cancel]          [Reject paper →] │
└─────────────────────────────────────┘
```

- `--bg-elevated`, `--border-default` border, `--radius-xl`
- Backdrop: `rgba(4,6,5,0.8)` blur(8px) — forest-tinted dark veil
- Textarea: `--bg-base` bg, `--border-default` border, `--radius-md`, `--text-primary`, resize-none
- Focus ring on textarea: `--accent-500` 2px
- Reject button: `--dismissed-bg` bg, `--text-primary` text, `--dismissed` border, disabled and dimmed until textarea has content

---

### 4.3 `/library` — Personal Library

**Purpose:** Browse saved (accepted) papers, trigger AI explanations.

**Layout:** Same shell. Header + filter controls + paper grid.

```
┌─ SIDEBAR ─┬──────────────────────────────────┐
│           │  "Library"     [search input]     │
│           │  12 papers                        │
│           │                                   │
│           │  FILTER ROW                       │
│           │  [All] [Explained] [Unread]        │
│           │                                   │
│           │  PAPER GRID (2-col on lg+)         │
│           │  ┌──────────┐  ┌──────────┐       │
│           │  │ LIB CARD │  │ LIB CARD │       │
│           │  └──────────┘  └──────────┘       │
│           │  ...                              │
└───────────┴──────────────────────────────────┘
```

#### Library Paper Card

Compact version of the Feed card. Grid layout (2 columns on desktop, 1 on mobile).

```
┌────────────────────────────────────┐
│  [cs.AI]               score: 9.5  │
│                                    │
│  LLM Agents in the Wild            │
│  (--text-base, weight 600)         │
│                                    │
│  John Doe · 2023-01-10             │
│                                    │
│  ───────────────────────────────   │
│  [↗ arXiv]  [Explain]  [🗑 Remove] │
└────────────────────────────────────┘
```

- No abstract shown by default
- "Explain" button: `--accent-500` border, `--accent-400` text, icon: sparkles ✦
- If explanation exists: badge "Explained" in `--success` color top-right corner

#### Explanation Panel

Clicking "Explain" opens an **inline expansion** below the card (not a modal):

```
┌────────────────────────────────────────────┐
│  ✦ AI Explanation · professional level      │
│  ─────────────────────────────────────      │
│  [Markdown rendered content]               │
│                                            │
│  Headings in --text-lg, --text-primary     │
│  Body in --text-base, --text-secondary     │
│  Code blocks in monospace --bg-base        │
│                                            │
│  [Close explanation]                       │
└────────────────────────────────────────────┘
```

- Smooth expand: `max-height` animation, 350ms `--ease-out`
- Markdown rendered with `react-markdown` + `remark-gfm`
- Loading state: 3-line skeleton shimmer in `--bg-elevated`

#### Search Input (library header)

```
┌─────────────────────────────────┐
│ 🔍  Search titles, authors…     │
└─────────────────────────────────┘
```

- `--bg-surface` bg, `--border-default` border, `--radius-md`
- `--text-sm`, placeholder in `--text-muted`
- Focus: border transitions to `--accent-500`, subtle `--glow-accent`
- Width: 240px, expands to 320px on focus (animated)

---

### 4.4 `/terminal` — Settings Page

**Purpose:** Configure filtering goals, categories, authors, topics, and personal preferences. Named "Terminal" to reinforce the technical, precision feel.

**Layout:** Two-column content area. Left: navigation tabs. Right: settings form panel.

```
┌─ SIDEBAR ─┬────────────────────────────────────────┐
│           │  "Terminal"                             │
│           │                                        │
│           │  ┌───────────┬──────────────────────┐  │
│           │  │ TABS      │  SETTINGS PANEL       │  │
│           │  │           │                       │  │
│           │  │ Filtering │                       │  │
│           │  │ Library   │                       │  │
│           │  │ Pipeline  │                       │  │
│           │  │ Account   │                       │  │
│           │  └───────────┴──────────────────────┘  │
└───────────┴────────────────────────────────────────┘
```

**Tab styling:**
- Vertical tabs on left, `w=180px`, `--bg-surface` bg
- Active tab: `--accent-500` left `3px` border, `--text-primary`
- Inactive: `--text-muted`, no border
- Tabs: Filtering · Library · Pipeline · Account

#### Tab: Filtering

```
FILTERING GOAL
──────────────────────────────────────────────
[Textarea — large]
"Find papers related to LLM agents and 
 multi-agent coordination systems."
(min-h: 120px, --text-base)

"Your natural language goal is analyzed by the
 GoalDistiller agent on save."  ← --text-xs --text-muted

[Save goal]  ← --accent-500 bg, full width

═══════════════════════════════════════════════

CATEGORIES
──────────────────────────────────────────────
[cs.AI ×]  [cs.LG ×]  [+ Add category]

arXiv category codes, e.g. cs.CV, math.OC

TOPICS
──────────────────────────────────────────────
[agents ×]  [RAG ×]  [+ Add topic]

Keywords used in BM25 lexical search

AUTHORS
──────────────────────────────────────────────
[Yann LeCun ×]  [+ Add author]

Author names to prioritize

[Save settings]  ← at bottom, accent button
```

**Tag/chip input component:**
- Existing tags: `--bg-elevated` bg, `--border-default` border, `--text-sm`, `×` remove button
- "Add" trigger: dashed border, `--text-muted`, clicking reveals inline text input
- Enter key or comma confirms new tag

#### Tab: Library

```
EXPLANATION LEVEL
──────────────────────────────────────────────
How should papers be explained to you?

○  Professional      (assumes domain expertise)
○  Student           (accessible but rigorous)
○  Simplified        (plain language, analogies)

(Radio group, custom styled, large click targets)

READING PREFERENCES
──────────────────────────────────────────────
Which sections interest you most?

☑ Introduction      ☑ Methodology
☑ Experiments       ☑ Conclusions
☐ Related Work      ☐ Appendix

[Save preferences]
```

**Radio group:**
- Each option is a full-width block `--bg-surface` border card
- Selected: `--border-active` border, `--accent-900` bg tint, `--accent-400` bullet
- Label in `--text-base` weight 500, description in `--text-sm` `--text-muted`

**Checkbox group:**
- Two-column grid
- Custom checkbox: 16×16px, `--border-default`, checked fills `--accent-500` with white checkmark

#### Tab: Pipeline

```
SCHEDULE
──────────────────────────────────────────────
Daily notification time
[09:00]  (time input, styled as text field)

PDF PARSER
──────────────────────────────────────────────
[ pypdfium ▾ ]  (select, same style as inputs)

MANUAL TRIGGER
──────────────────────────────────────────────
Run the pipeline now against today's arXiv feed.

[⚡ Trigger pipeline now]  ← full width, outlined --accent

LAST RUN
──────────────────────────────────────────────
Status:   COMPLETED
Started:  2026-04-01 08:55 UTC
Duration: 4m 23s
Papers:   254 scraped · 23 evaluated · 4 recommended
```

**Last run display:**
- Key-value pairs in a definition-list style
- Keys: `--text-sm` `--text-muted` monospace
- Values: `--text-sm` `--text-primary`
- Status badge: colored pill matching pipeline state colors

#### Tab: Account

```
EMAIL
──────────────────────────────────────────────
user@example.com  (read-only display)

CHANGE PASSWORD
──────────────────────────────────────────────
[Current password]
[New password]
[Confirm new password]
[Update password]

DANGER ZONE
──────────────────────────────────────────────
┌──────────────────────────────────────────┐
│  Delete Account                          │
│  This permanently removes all your data. │
│  [Delete my account]  ← --dismissed border, --dismissed text  │
└──────────────────────────────────────────┘
```

---

### 4.5 Auth Pages — `/login` and `/register`

**Layout:** Centered card, no sidebar, minimal nav.

```
                ┌──────────────────────────┐
[logo + name]   │                          │
                │  Welcome back            │
                │  --text-2xl weight 600   │
                │                          │
                │  [Email field]           │
                │  [Password field]        │
                │                          │
                │  [Sign in →]  full width │
                │                          │
                │  No account? Register    │
                └──────────────────────────┘
```

- Card: `--bg-surface`, `--border-default` border, `--radius-xl`, shadow-lg
- Card width: `max-w-sm` (384px), centered on page
- Page bg: `--bg-base` with faint grid pattern (same as landing)
- Input fields: `--bg-base`, `--border-default`, `--radius-md`, h=44px, `--text-primary`
- Focus ring: `--accent-500` 2px outline, 2px offset
- Submit button: `--accent-500` bg, white, full width, h=44px, `--radius-md`
- Error state: `--dismissed` border + `--text-muted` small text below field (calm, not alarming)

---

## 5. Component Library

### 5.1 Inputs

All inputs share a base style:
```
background:    --bg-base
border:        1px solid --border-default
border-radius: --radius-md
height:        40px (text inputs) / auto (textarea)
padding:       10px 14px
font:          --text-sm Inter
color:         --text-primary

:focus         border-color: --accent-500
               outline: none
               box-shadow: 0 0 0 3px rgba(16,185,129,0.18)

:disabled      opacity: 0.4
               cursor: not-allowed

::placeholder  color: --text-muted
```

### 5.2 Buttons

```
Primary:
  bg: --accent-500  |  text: white  |  hover: --accent-400 bg
  border-radius: --radius-md  |  h=40px  |  px=16px  |  font-weight: 500

Secondary (outlined):
  bg: transparent  |  text: --text-primary  |  border: --border-default
  hover: --bg-elevated bg

Ghost:
  bg: transparent  |  text: --text-secondary  |  no border
  hover: --bg-elevated bg  |  text: --text-primary

Destructive (delete account, irreversible):
  bg: --dismissed-bg  |  text: --text-primary  |  border: --dismissed
  hover: bg lightens to #243040

Accent outlined (reject, dismiss):
  bg: transparent  |  text: --dismissed  |  border: --dismissed
  hover: --dismissed-bg bg

All states:
  :focus-visible  ring: 2px --accent-500, offset: 2px
  :disabled       opacity: 0.4, cursor: not-allowed
  :active         scale: 0.97 (transform, 100ms)
```

### 5.3 Badge / Tag

```
Default:     bg: --bg-elevated   |  text: --text-secondary  |  border: --border-dim
Emerald:     bg: --accent-900    |  text: --accent-300                // category tags, key labels
Accepted:    bg: --accepted-bg   |  text: --accepted                  // "Accepted" state chip
Processing:  bg: --processing-bg |  text: --teal-400                  // pipeline state, "AI active"
Dismissed:   bg: --dismissed-bg  |  text: --dismissed                 // rejected papers
Info:        bg: #0C2A3F         |  text: --info                      // read-only system info

All: padding 2px 8px, --radius-full, --text-xs, font-weight: 500
     Monospace font for data values (scores, IDs, states)
```

### 5.4 Score Bar

```
<ScoreBar score={9.5} />

Outer track:  h=4px, --bg-elevated, --radius-full, overflow:hidden
Inner fill:   width = (score/10)*100%, --radius-full
              color interpolation via hsl():
              score < 5 → --score-low  (#3A5443 muted forest)
              score < 8 → --score-mid  (#2DD4BF teal)
              score ≥ 8 → --score-high (#34D399 bright emerald)

Score label:  positioned absolute right, --text-xl monospace weight 700
              same color as bar fill
```

### 5.5 Skeleton Loader

```
Applied to: cards, explanation panels, stats

Pattern: rounded blocks matching content shape
Animation: shimmer sweep left-to-right
  background: linear-gradient(
    90deg,
    --bg-elevated 25%,
    --bg-surface 37%,
    --bg-elevated 63%
  )
  background-size: 400% 100%
  animation: shimmer 1.4s ease infinite
```

### 5.6 Pipeline Status Indicator

```
States and visual representations:

IDLE:
  dot: 8px circle, --text-muted color, no animation
  label: "Idle"

PENDING:
  dot: 8px, --teal-400, slow pulse (1.5s), opacity 0.6→1
  label: "Queued"

PROCESSING_PDFS / RUNNING / etc:
  dot: 8px, --teal-400, fast pulse (0.8s)
  outer ring: 16px, --teal-400 at 20% opacity, animated scale 1→1.8 + fade (1s loop)
  label: state name monospace lowercase → "processing pdfs"
  progress bar: thin 2px horizontal line below label, --teal-400 fill, animated width

COMPLETED:
  dot: 8px, --accepted, no animation
  label: "Completed" in --accepted

ERROR / FAILED:
  dot: 8px, --dismissed, no animation
  label: "Error" in --dismissed
```

---

## 6. Page Transitions & Micro-interactions

### Page Navigation
```
Enter: opacity 0→1, translateY 8px→0, duration: 300ms, ease: --ease-out
Exit:  opacity 1→0, duration: 150ms, ease: --ease-in
Stagger: card items enter with 40ms delay between each
```

### Feed Card Interactions
```
Accept action:
  1. Button briefly scales up (spring, 150ms)
  2. Card slides right + fades out (300ms, ease-in)
  3. Next card slides up to fill gap

Reject action:
  1. Modal animates in (translateY 20px→0, opacity 0→1)
  2. On confirm: card slides left + fades out
  3. Toast: "Paper rejected. Feedback noted." (4s, bottom-right)

Score badge: counts up from 0 on first render (500ms, ease-out)
```

### Toast Notifications
```
Position: bottom-right (desktop), bottom-center (mobile)
Entry:     translateY 100%→0, opacity 0→1, 250ms ease-out
Exit:      opacity 1→0, 200ms ease-in, after 4s
Stack:     multiple toasts stack vertically with 8px gap

Success: --accepted left border (3px) + icon
Dismiss: --dismissed left border (3px) + icon (paper rejected, item removed)
Info:    --accent-500 left border (3px) + icon (general system messages)
```

---

## 7. Responsive Behavior

```
Breakpoints (Tailwind defaults):
  sm:   640px
  md:   768px
  lg:   1024px
  xl:   1280px

< 768px (mobile):
  - Sidebar → bottom tab navigation (4 tabs)
  - Feed cards: full-width, single column
  - Library: single column grid
  - Terminal tabs: horizontal scroll tabs at top (not left sidebar)
  - Reject modal: bottom sheet (full width, rounded top corners)
  - Stats row: scrollable horizontal pills

768–1024px (tablet):
  - Sidebar collapses to icon-only (w=64px), labels on hover tooltip
  - Library: 2-column grid
  - Terminal: stacked (tabs on top, panel below)

> 1024px (desktop):
  - Full sidebar, 2-col library, 2-col terminal
```

---

## 8. Accessibility

- All interactive elements have visible `:focus-visible` rings (2px `--accent-500`, 2px offset)
- Color is never the sole indicator of state (always paired with icon or text label)
- Score bars include `aria-label="Score: 9.5 out of 10"`
- Reject modal traps focus; Escape closes it; `role="dialog"` + `aria-modal="true"`
- Cards use `article` elements with meaningful `aria-label`
- Reduced-motion: all `transform` + opacity animations wrapped in `@media (prefers-reduced-motion: no-preference)`
- Minimum touch target: 44×44px for all interactive elements
- Contrast: all text meets WCAG AA minimum (4.5:1 for normal, 3:1 for large text)

---

## 9. File & Component Structure (Next.js)

```
app/
  (auth)/
    login/page.tsx
    register/page.tsx
  (app)/
    layout.tsx              ← AppShell: sidebar + topbar
    dashboard/page.tsx
    library/page.tsx
    terminal/page.tsx
  page.tsx                  ← Landing

components/
  layout/
    AppShell.tsx
    Sidebar.tsx
    Topbar.tsx
    PipelineStatusPill.tsx
  feed/
    PaperCard.tsx
    ScoreBar.tsx
    RejectModal.tsx
    FeedStats.tsx
  library/
    LibraryCard.tsx
    ExplanationPanel.tsx
    SearchInput.tsx
  terminal/
    FilteringTab.tsx
    LibraryTab.tsx
    PipelineTab.tsx
    AccountTab.tsx
    TagInput.tsx
    ExplanationLevelPicker.tsx
  ui/                       ← shadcn/ui base components
    button.tsx
    input.tsx
    textarea.tsx
    badge.tsx
    skeleton.tsx
    toast.tsx
    dialog.tsx
    radio-group.tsx
    checkbox.tsx

lib/
  api.ts                    ← typed API client wrapping all endpoints
  auth.ts
  types.ts                  ← Paper, UserSettings, PipelineStatus, etc.
```
