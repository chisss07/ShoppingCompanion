# Shopping Companion — UI/UX Design Document

**Version:** 1.0
**Date:** 2026-03-15
**Status:** Ready for Developer Handoff

---

## Table of Contents

1. Design Philosophy
2. Design System (Color, Typography, Spacing, Components, Status Indicators, Iconography)
3. Accessibility (WCAG 2.1 AA)
4. Layout and Navigation Architecture
5. Screen Specifications (all 4 major screens)
6. Interaction Patterns
7. Text-Based Wireframes (6 layouts)
8. Motion and Animation
9. Edge Cases and Empty States
10. Design Decisions Log

---

## 1. Design Philosophy

**Trust through transparency.** Users are making financial decisions. Every element communicates honesty — accurate data attribution, visible source names, clear timestamps, no hidden fees buried in fine print. The design avoids dark patterns entirely.

**Clarity under complexity.** Price comparison involves dense data tables, multiple vendors, shipping nuances, and model variants. The design system converts this complexity into scannable hierarchies. The best deal is visually obvious within two seconds of results loading.

**Speed as a feature.** AI-powered search takes time. The interface makes the wait productive by showing real-time progress — users feel the system working for them, not simply waiting on a spinner.

**Calm confidence.** The visual language is professional and restrained. Warm neutrals, a focused primary accent, and generous whitespace create an environment where users can think and decide, not feel pressured.

---

## 2. Design System

### 2.1 Color Palette

All colors are specified in HSL. Contrast ratios confirm WCAG 2.1 AA compliance.

#### Primary Brand Color — Indigo

Indigo sits between authoritative navy and energetic blue, signaling both reliability and modernity.

| Token | HSL Value | Hex | Usage |
|---|---|---|---|
| `color-primary-900` | 235 60% 20% | #1A1F52 | Dark text on light backgrounds |
| `color-primary-800` | 235 55% 30% | #283080 | Section headings |
| `color-primary-700` | 235 52% 40% | #3645AE | Link hover states |
| `color-primary-600` | 235 50% 50% | #4059D9 | Primary interactive elements, focus rings |
| `color-primary-500` | 235 70% 60% | #6B7FEF | Icons, secondary actions |
| `color-primary-400` | 235 80% 72% | #8FA0F6 | Disabled states, decorative |
| `color-primary-100` | 235 80% 95% | #EEF0FD | Selected row backgrounds, hover tints |
| `color-primary-050` | 235 80% 98% | #F7F8FE | Subtle page tinting |

#### Semantic Colors

**Success — Emerald** (best deal, in-stock, price drop):

| Token | HSL Value | Hex | Usage |
|---|---|---|---|
| `color-success-700` | 152 60% 28% | #1C7A4A | Text on light success backgrounds |
| `color-success-500` | 152 65% 42% | #28A062 | Best deal badge background |
| `color-success-100` | 152 60% 93% | #E6F7EE | Best deal card background tint |

**Warning — Amber** (limited stock, price increase):

| Token | HSL Value | Hex | Usage |
|---|---|---|---|
| `color-warning-700` | 38 90% 30% | #8A5200 | Text on warning backgrounds |
| `color-warning-500` | 38 95% 48% | #F5A000 | Limited stock badge |
| `color-warning-100` | 38 90% 93% | #FEF3D9 | Warning tint backgrounds |

**Danger — Red** (out-of-stock, price increase badge):

| Token | HSL Value | Hex | Usage |
|---|---|---|---|
| `color-danger-700` | 4 75% 35% | #A32020 | Text on danger backgrounds |
| `color-danger-500` | 4 80% 55% | #D93535 | Out-of-stock badge, price increase icon |
| `color-danger-100` | 4 80% 95% | #FDEEEE | Out-of-stock tint |

#### Neutral Palette

| Token | HSL Value | Hex | Usage |
|---|---|---|---|
| `color-neutral-950` | 220 15% 10% | #161A22 | Primary body text |
| `color-neutral-800` | 220 12% 20% | #2C3140 | Secondary headings |
| `color-neutral-700` | 220 10% 35% | #515969 | Secondary text, metadata |
| `color-neutral-500` | 220 8% 55% | #808996 | Placeholder text, dividers |
| `color-neutral-300` | 220 8% 80% | #C4C8D0 | Borders, table lines |
| `color-neutral-200` | 220 8% 90% | #E2E4E9 | Input borders, card borders |
| `color-neutral-100` | 220 8% 95% | #F1F2F5 | Sidebar background, zebra rows |
| `color-neutral-050` | 220 8% 98% | #F9F9FB | Page background |
| `color-white` | — | #FFFFFF | Card surfaces, input backgrounds |

**Page background:** `color-neutral-050` (#F9F9FB). This off-white reduces eye strain and makes pure-white card surfaces float cleanly.

---

### 2.2 Typography Scale

**Primary Typeface: Inter** (fallback: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif)
Chosen for exceptional legibility at small sizes, extensive weight range, and tabular number support — critical for price comparison tables.

**Monospace for prices and numeric data: "JetBrains Mono"** (fallback: "Fira Code", monospace)
Ensures column alignment in tables without fixed widths, and subtly signals numerical precision.

| Token | Size | Line Height | Weight | Letter Spacing | Usage |
|---|---|---|---|---|---|
| `text-heading-1` | 32px / 2rem | 1.2 | 700 | -0.02em | Page titles |
| `text-heading-2` | 24px / 1.5rem | 1.3 | 600 | -0.01em | Section headings |
| `text-heading-3` | 20px / 1.25rem | 1.4 | 600 | -0.005em | Card titles, sub-sections |
| `text-heading-4` | 16px / 1rem | 1.4 | 600 | 0 | Table column headers |
| `text-body-lg` | 16px / 1rem | 1.6 | 400 | 0 | Primary reading text |
| `text-body-md` | 14px / 0.875rem | 1.6 | 400 | 0 | Secondary content, card body |
| `text-body-sm` | 12px / 0.75rem | 1.5 | 400 | 0.01em | Metadata, timestamps, captions |
| `text-label-md` | 14px / 0.875rem | 1.4 | 500 | 0.02em | Form labels, button text |
| `text-label-sm` | 12px / 0.75rem | 1.4 | 500 | 0.04em | Badge text, chip labels |
| `text-price-lg` | 28px / 1.75rem | 1.1 | 700 | -0.01em | Best deal price, hero price |
| `text-price-md` | 20px / 1.25rem | 1.2 | 600 | 0 | Comparison table prices |
| `text-price-sm` | 16px / 1rem | 1.3 | 500 | 0 | Inline prices, small cards |

All price tokens use JetBrains Mono. All others use Inter.

---

### 2.3 Spacing and Grid

**Base unit: 4px.** All spacing is a multiple of 4px.

| Token | Value | Common Usage |
|---|---|---|
| `space-1` | 4px | Icon-to-label gaps, tight badge padding |
| `space-2` | 8px | Internal component padding (small) |
| `space-3` | 12px | Badge and chip padding |
| `space-4` | 16px | Standard component padding |
| `space-5` | 20px | Card internal padding |
| `space-6` | 24px | Section gaps within a card |
| `space-8` | 32px | Between cards, between sections |
| `space-10` | 40px | Major section separators |
| `space-12` | 48px | Page-level vertical rhythm |

**Grid:**
- Desktop: 12-column, 24px gutters, 1280px max width, 40px horizontal page padding
- Tablet (768–1279px): 8-column, 20px gutters
- Mobile (below 768px): 4-column, 16px gutters, 16px horizontal page padding

**Border Radius:**

| Token | Value | Usage |
|---|---|---|
| `radius-sm` | 4px | Badges, chips, small tags |
| `radius-md` | 8px | Buttons, input fields |
| `radius-lg` | 12px | Cards |
| `radius-xl` | 16px | Modals, large panels |
| `radius-full` | 9999px | Avatar thumbnails, pill badges |

**Elevation (Box Shadows):**

| Token | CSS | Usage |
|---|---|---|
| `shadow-sm` | 0 1px 3px rgba(0,0,0,0.08) | Cards at rest |
| `shadow-md` | 0 4px 12px rgba(0,0,0,0.10) | Cards on hover, dropdowns |
| `shadow-lg` | 0 8px 24px rgba(0,0,0,0.12) | Modals, autocomplete panel |
| `shadow-focus` | 0 0 0 3px rgba(64,89,217,0.35) | Focus ring on all interactive elements |

---

### 2.4 Component Library

#### Buttons

**Primary Button:** Background `color-primary-600`, white text, `text-label-md`, `radius-md`, 12px/20px padding. Hover: `color-primary-700` + `shadow-md`. Active: `color-primary-800` + scale(0.98). Disabled: `color-primary-400`, cursor not-allowed. Focus: `shadow-focus`.

**Secondary Button:** White background, 1.5px border `color-neutral-300`, `color-neutral-800` text. Hover: border `color-primary-500`, background `color-primary-050`.

**Ghost Button:** No background, no border, `color-primary-600` text. Hover: background `color-primary-050`. Used for sidebar actions and inline text actions.

**Icon Button:** 36x36px (default), 32x32px (small). Same states as Ghost Button. Must always have `aria-label`.

---

#### Input Fields

**Search Input (hero, large variant):**
- Height: 56px
- Font: `text-body-lg`, minimum 16px (prevents iOS zoom)
- Border: 2px solid `color-neutral-200`
- Border radius: `radius-md`
- Background: white
- Left padding: 52px (accommodates search icon at 20px)
- Right padding: 100px (accommodates Search button)
- Focus: border `color-primary-600`, `shadow-focus`
- Placeholder: `color-neutral-500`

**Standard Input:** 44px height, `text-body-md`, 1.5px border `color-neutral-200`, `radius-md`.

---

#### Cards

**Standard Card:** White background, 1px border `color-neutral-200`, `radius-lg`, `shadow-sm`, `space-5` padding. Hover (interactive): `shadow-md`, border `color-neutral-300`.

**Best Deal Card:** Left border 3px solid `color-success-500`, background `color-success-100`, "Best Deal" badge pinned to top-right corner.

**Comparison Source Card:** Standard card with source logo (32px height, max 120px width), price in `text-price-md`, availability badge, rating, shipping, and return data in a compact attribute list.

**History Item Card:** 72px tall on desktop. Left: search term + date metadata. Right: price range + price change indicator. On hover: "Re-run Search" action button appears (see animation spec). Active state: left accent border `color-primary-600`, background `color-primary-050`.

**Alternative Model Card:** 220px wide (desktop), full-width (mobile). Contains: 80x80px product thumbnail, product name (max 2 lines), differentiator line in italic `color-primary-700`, "From $XXX" price, 2–3 spec-diff chips, and "Search this model" ghost button.

---

#### Badges and Chips

**Availability Badge (pill):** `radius-full`, 2px top/bottom padding, 10px left/right padding, `text-label-sm`, all-caps, letter-spacing 0.06em.

| State | Background | Text | Label |
|---|---|---|---|
| In Stock | `color-success-100` | `color-success-700` | IN STOCK |
| Limited | `color-warning-100` | `color-warning-700` | LIMITED |
| Out of Stock | `color-danger-100` | `color-danger-700` | OUT OF STOCK |
| Unknown | `color-neutral-100` | `color-neutral-700` | CHECKING... |

**Price Change Badge:**

| State | Icon | Color | Format |
|---|---|---|---|
| Price dropped | Down arrow | `color-success-700` | -$12.00 (8%) |
| Price increased | Up arrow | `color-danger-700` | +$8.00 (5%) |
| No change | Dash | `color-neutral-500` | No change |
| New search | Star | `color-primary-500` | New |

**Source Chip:** `color-neutral-100` background, 1px `color-neutral-200` border, `text-label-sm`, retailer favicon (14px) + name, `radius-sm`.

**AI Badge:** Small badge for all AI-generated content. Indigo-to-violet gradient background, white text, "AI Summary" label with a sparkle icon. Applied to the AI summary card and alternative models section header.

---

#### Autocomplete Dropdown

- Positioned 4px below the search input, full input width
- Background: white, 1px `color-neutral-200` border, `radius-lg`, `shadow-lg`
- Max height: 320px with internal scroll
- Row height: 44px minimum

Row anatomy (left to right): search icon (generic completions) or 32x32px product thumbnail (recognized products) — suggestion text with matching characters bolded — optional category chip — arrow icon on far right on hover/focus.

Row states: Hover: `color-primary-050` background. Keyboard focused: `color-primary-100` background + 3px left border `color-primary-600`.

Suggestion groups: "Recent searches" (if applicable, up to 3) then "Suggestions" (AI completions, up to 4) then always-present final row: "Search for '{query}'".

---

#### Progress Tracker

Displayed below the search bar during an active AI search, driven by WebSocket events.

**Structure:** A horizontal track with discrete steps. Each step represents one data source. Steps resolve left-to-right as WebSocket events arrive. Between steps: a connecting line that fills with `color-success-500` when the left step resolves.

**Step states:**
- Pending: hollow circle, `color-neutral-300` border
- Active: filled circle, pulsing glow animation in `color-primary-400`
- Complete: filled `color-success-500` with checkmark
- Timed out: filled, `color-danger-500`, X icon
- Rate limited: filled, `color-warning-500`, pause icon

Each step label: retailer name in `text-body-sm`, `color-neutral-700`, below the node circle.

**Status text line:** Below the step row. Italic, `color-neutral-700`. Updates in real time with each WebSocket event via a 100ms cross-fade. Examples: "Checking Amazon..." / "Got 3 results from Best Buy" / "Comparing prices..."

**Tracker lifecycle:** Slides down 200ms ease-out when search starts. When all steps resolve, waits 600ms, then slides up + fades out while results render below.

---

#### Skeleton Screens

Skeleton screens use an animated shimmer: a CSS gradient scanning left-to-right on a 2-second cycle.

Shimmer: `linear-gradient(90deg, color-neutral-100 25%, color-neutral-200 50%, color-neutral-100 75%)`, background-size 200%, animated from `-100% 0` to `100% 0`.

Element types:
- **Text skeleton:** Rounded pill shapes matching the text height. Alternating short (40–70%) and long (80–95%) widths to mimic paragraph flow.
- **Image skeleton:** Rectangle at image dimensions, `radius-md`.
- **Price skeleton:** 80px wide x 28px tall, `radius-sm`.
- **Card skeleton:** Full card outline with internal skeleton rows.

Real content replaces skeleton sections progressively as data streams in. A skeleton element never partially overlaps real content within the same row.

---

### 2.5 Status Indicators

#### Source Status (Progress Tracker)

| State | Visual | Description |
|---|---|---|
| Queued | Hollow circle, neutral border | Source not yet contacted |
| Active | Filled circle, pulsing glow | Request in flight |
| Results returned | Filled circle, checkmark, success green | Data received |
| Timed out | Filled circle, X, danger red | Source did not respond |
| Rate limited | Filled circle, pause, warning amber | Source returned retry signal |

#### Deal Quality

| Indicator | Visual | Placement |
|---|---|---|
| Best Deal | Green left border + "Best Deal" badge | Source card |
| Good Value | Blue left border | Source card |
| Higher Price | No special treatment | Source card |
| Highest Price | Light red tint | Comparison table row |

#### Price Trend (History)

| Trend | Icon | Color | Behavior |
|---|---|---|---|
| Dropped significantly (>10%) | Bold down arrow | `color-success-500` | Animated bounce on first render |
| Dropped slightly | Down arrow | `color-success-700` | Static |
| Unchanged | Horizontal dash | `color-neutral-500` | Static |
| Increased slightly | Up arrow | `color-danger-500` | Static |
| Increased significantly (>10%) | Bold up arrow + exclamation | `color-danger-700` | Red pulsing dot |

---

### 2.6 Iconography

Icon library: **Phosphor Icons** (phosphoricons.com)
Default weight: Regular. Headings and primary actions: Bold. Metadata and decorative: Light.

Icons at 16px must have `aria-hidden="true"` with a sibling text label. Stand-alone icon buttons must have `aria-label` on the button element.

| Context | Icon Name | Size |
|---|---|---|
| Search field | MagnifyingGlass | 20px |
| History sidebar | ClockCounterClockwise | 20px |
| Re-run search | ArrowsCounterClockwise | 16px |
| Price drop | ArrowDown | 16px |
| Price rise | ArrowUp | 16px |
| External link | ArrowSquareOut | 16px |
| Best deal | Star (Bold, filled) | 16px |
| AI summary | Sparkle | 16px |
| Close | X | 16px |
| Filter | Funnel | 20px |
| Sort | ArrowsDownUp | 16px |
| Alternative model | ArrowsLeftRight | 16px |
| Step complete | Check | 14px (inside circle) |
| Warning | Warning | 16px |

---

## 3. Accessibility

Target: **WCAG 2.1 Level AA** minimum throughout.

### 3.1 Color Contrast

- Normal text (below 18px regular / 14px bold): 4.5:1 minimum
- Large text (18px+ regular / 14px+ bold): 3:1 minimum
- UI components and graphical objects: 3:1 minimum
- Color is never the sole means of conveying information — always paired with text, icon, or pattern

Verified key pairs:
- `color-neutral-950` on `color-neutral-050`: 17.8:1 (AAA)
- `color-primary-600` on white: 4.7:1 (AA)
- `color-success-700` on `color-success-100`: 5.1:1 (AA)
- `color-warning-700` on `color-warning-100`: 4.8:1 (AA)
- `color-danger-700` on `color-danger-100`: 5.6:1 (AA)

### 3.2 Focus Management

- All interactive elements: visible `shadow-focus` ring (3px, `color-primary-600` at 35% opacity, 2px offset)
- Focus order follows visual reading order (left to right, top to bottom)
- When results render after a search, focus moves to `h2#results-heading` so screen reader users hear the context change
- Modals trap focus within using a focus trap utility; closing returns focus to the triggering element

### 3.3 Keyboard Navigation

- `Cmd+K` (Mac) / `Ctrl+K` (Win/Linux): focus the search bar from anywhere in the app (announced in `aria-label`)
- Autocomplete: Arrow Down opens dropdown from search field; Up/Down navigate; Enter selects; Escape closes and returns focus to input
- Comparison table: Arrow keys navigate cell-by-cell; screen reader announces column and row headers
- History sidebar items: focusable buttons; Spacebar or Enter selects
- Progress tracker: `aria-live="polite"` region; each status update announced without interrupting user focus

### 3.4 Screen Reader Support

- Semantic HTML: `<header>`, `<nav>`, `<main>`, `<aside>` (sidebar), `<section aria-labelledby>`, `<footer>`
- `<h1>` once per page. `<h2>` for major sections. `<h3>` for cards. Heading hierarchy never skips levels.
- Comparison table: `<th scope="col">` for column headers, `<th scope="row">` for row labels
- Price change badges: Full reading, e.g., "Price dropped twelve dollars, eight percent since last search"
- Availability badges: `role="img"` with descriptive `aria-label`
- AI summary: Prefixed with visually hidden text "AI-generated summary:"
- Skeleton screens: `aria-busy="true"` on loading regions, `aria-label="Loading results"` on container

### 3.5 Motion

All animations respect `prefers-reduced-motion`. When reduced motion is preferred:
- Progress tracker step transitions are instant
- Skeleton shimmer replaced with static 50% opacity fill
- Card hover shadows appear instantly (no transition)
- Progress tracker slide-down is instant

No animation loops indefinitely unless providing real-time information (e.g., the active-step pulse). That pulse reverts to a static fill in reduced-motion mode.

### 3.6 Text Scaling and Touch

- All font sizes in `rem` units
- UI remains usable and unclipped at 200% browser zoom
- No text is placed inside images or rendered as graphics
- All interactive elements: minimum 44x44px touch target
- Minimum 8px spacing between adjacent touch targets

---

## 4. Layout and Navigation Architecture

### 4.1 Global Shell

**Zone 1: Top Bar (Desktop) — 60px**
- Background: white, bottom border 1px `color-neutral-200`
- Left: Application wordmark "Shopping Companion" in `text-heading-4`, `color-primary-800`
- Center: Compact search input (visible on all pages except the Search home page, where the hero bar is present)
- Right: Settings icon button

**Zone 1: Top Bar (Mobile) — 56px**
- Left: Hamburger menu icon (opens history drawer)
- Center: App wordmark
- Right: Search icon button (triggers full-screen search overlay)
- Bottom shadow: `shadow-sm`

**Zone 2: History Sidebar (Desktop only) — 280px fixed, collapsible to 56px**
- Background: `color-neutral-100`
- Right border: 1px `color-neutral-200`
- Contents: "History" header, filter input, scrollable history list
- Collapse button: chevron icon at top-right, toggles width with 200ms ease transition
- Collapsed state: only a ClockCounterClockwise icon per history item; tooltip on hover shows the search term

**Zone 3: Main Content Area**
- Fills remaining width after sidebar
- Horizontal padding: `space-10` desktop, `space-4` mobile
- Vertical padding: `space-8` top
- Max content width for readable areas: 960px, centered

---

### 4.2 Navigation Flow

```
[Search Page / Home]
        |
        | User submits search
        v
[Results Page]  <--- (also accessible by clicking any history item)
        |
        | User clicks "View Full Comparison"
        v
[Comparison Detail Page]
        |
        | Back button or browser back
        v
[Results Page]  (scroll position and state preserved — no re-fetch)

[History Sidebar / History Page]
        |
        | Click a history item
        v
[Results Page (from cache, with "Last updated X" banner)]

        | Click "Re-run Search"
        v
[Results Page (fresh search — progress tracker runs again)]
```

**URL structure:**
- `/` — Search home
- `/results?q={query}&id={search_id}` — Results page
- `/results/{search_id}/compare` — Comparison detail
- `/history` — Full history page (mobile primary; desktop shows sidebar instead)

**State persistence:** Navigating from Results to Comparison Detail and back restores scroll position. Selecting a different history item cross-fades the main area (150ms) without re-fetching cached results. The search input always reflects the current view's query.

---

### 4.3 Responsive Strategy

**Desktop (1280px+):** Full sidebar (280px) + main content. Top bar compact search. 3-column comparison card grid. Full comparison table without horizontal scroll (on 1440px+).

**Tablet (768–1279px):** Sidebar collapses to icon-only (56px) by default. Comparison table horizontally scrollable with sticky first column. 2-column comparison card grid.

**Mobile (below 768px):** Sidebar hidden, accessible via hamburger drawer. Full-screen search overlay on search icon tap. Single-column card layout. Comparison table replaced with an accordion-style per-attribute view (each attribute row expands to show all sources' values). History via bottom navigation "History" tab.

**Bottom Navigation Bar (Mobile only) — 56px + safe area inset**
- Background: white, top border `color-neutral-200`
- Four items: Search, Results, History, Compare
- Active: `color-primary-600` icon + label. Inactive: `color-neutral-500`.
- Hidden when a full-screen overlay is active.

---

## 5. Screen Specifications

### 5.1 Search Page (Home)

**Purpose:** The entry point. The sole goal is to get the user to submit a search with minimum friction.

**Top Bar:** Simplified — wordmark left only, settings icon right. No compact search bar (hero bar is prominent and visible).

**Hero Section (vertically centered in main area):**
- Tagline: `text-heading-2`, "Find the best price, instantly." in `color-neutral-800`
- Sub-tagline: `text-body-lg`, `color-neutral-700`: "AI-powered comparison across dozens of retailers."
- 16px gap between tagline lines, 32px before search bar

**Search Bar:**
- Width: 680px (desktop), 100% minus `space-8` margins (mobile)
- Horizontally centered
- Large variant (56px height), left magnifying glass icon, right "Search" primary button separated by 1px `color-neutral-200` divider
- Below: up to 5 suggestion chips for popular/recent searches (`text-label-sm`, `radius-full`, `color-neutral-100`)

**Autocomplete:** Appears after 300ms debounce, 2+ characters typed. Max 7 suggestions. Groups: Recent searches (up to 3), AI suggestions (up to 4), always-present "Search for '{query}'" final row.

**Trust Indicators (below search, `space-8` gap):**
Three callouts as icon + single-line text in `text-body-sm`, `color-neutral-600`:
1. CheckCircle + "Real-time prices from 20+ sources"
2. Sparkle + "AI comparison and recommendations"
3. ClockCounterClockwise + "Search history with price tracking"

**History Sidebar:** Fully visible and interactive. Clicking any item navigates to that result set.

---

### 5.2 Results Page

**Purpose:** Display AI-powered search results with price comparison cards, AI summary, and alternative models.

**Page Header (main content):**
- `text-heading-2`: Search query in quotes
- `text-body-sm`, `color-neutral-600`: "{N} results from {M} sources · Updated {time}"
- Right-aligned: "Sort by: Best Price" dropdown + "Filter" icon button

**Progress Tracker:** Appears immediately below the page header during loading. Slides down 200ms. Disappears 600ms after all steps complete.

**AI Summary Card (full width, appears below tracker or header):**
- AI badge top-left
- `text-heading-3`: "Best option for most buyers"
- 2–4 sentences of AI-generated analysis
- Bottom row: 3 summary chips (lowest price, fastest delivery, best returns)
- Subtle gradient background: white to `color-primary-050` (top-left to bottom-right)
- Right border: 3px solid `color-primary-400`

**Price Comparison Section:**
- `text-heading-3`: "Price Comparison"
- `text-body-sm` sub: "Prices include estimated shipping to your region"
- 3-column card grid (desktop), 2-column (tablet), 1-column (mobile)
- Cards ordered best-to-worst by total price
- First card uses Best Deal Card variant

Each comparison source card contains:
- Source logo (max 32px height)
- Seller name (if different from source), `text-heading-4`
- Availability badge
- Price: `text-price-md`, `color-primary-900`
- Shipping: "Free" in `color-success-700` or "+ $X.XX" in `color-neutral-700`
- Total: `text-body-sm`, `color-neutral-500`
- Star rating (filled/half/empty stars) + review count
- Return policy (1 line, `text-body-sm`)
- "View Deal" primary button (full-width, opens product URL in new tab)
- "View Full Comparison" ghost text link below button

**Alternative Models Section:**
- `text-heading-3`: "You Might Also Consider" with AI badge
- `text-body-sm`: "Newer releases and alternative models worth comparing"
- Horizontal scrolling row of Alternative Model Cards (desktop), vertical stack (mobile)
- Each card: 220px wide, product thumbnail, name, differentiator line, "From $XXX", spec-diff chips, "Search this model" ghost button

---

### 5.3 Comparison Detail Page

**Purpose:** Deep, structured side-by-side comparison of all sources for a single product.

**Breadcrumb:** `text-body-sm` below the top bar: "Search / {Product Name} / Comparison". Links in `color-primary-600`.

**Page Header:**
- Product name `text-heading-1`
- Product image: 120x120px
- Summary row: best price, number of sources, last updated timestamp

**Comparison Table:**
- Full-width, horizontally scrollable on tablet/mobile
- First column sticky: attribute label
- Subsequent columns: one per source, ordered best-to-worst by price
- Best-price column: `color-primary-050` column background + "Best" label in header
- Attributes (rows): Price, Shipping cost, Total cost (bold), Availability, Estimated delivery, Seller rating, Seller type, Return policy, Warranty, Product condition, Link (external)
- Table controls above: "Columns" dropdown, "Attributes" dropdown, sortable by clicking column headers

**AI Analysis (below table):**
- "Detailed AI Analysis" heading with AI badge
- 3–5 paragraphs: best overall, best for delivery, best for returns, items to watch
- Initially shows 2 paragraphs with "Show more" ghost button

**Related Searches:**
- `text-heading-3` "Related Searches"
- Up to 5 AI-generated query chips

---

### 5.4 History Page

(Full-screen view for mobile; also accessible via direct URL on desktop.)

**Page Header:**
- `text-heading-1`: "Search History"
- `text-body-md`, `color-neutral-600`: "{N} searches"
- Right: "Clear All" destructive ghost button (requires confirmation)

**Filter and Sort Bar:**
- Keyword filter input (smaller variant)
- Sort dropdown: "Most Recent" / "Oldest" / "Biggest Price Drop" / "Highest Price Increase"
- Date range filter: From/To date inputs

**History List:**
- Grouped by date: "Today", "Yesterday", "This Week", "Earlier" — group headers in `text-label-sm`, `color-neutral-500`, all-caps
- Within groups: newest-first by default

Each history item:
- Left: Search term (`text-heading-4`), date + time (`text-body-sm`, `color-neutral-600`)
- Middle: Retailer source chips (up to 3, "+N more" if applicable)
- Right: Price range + price change badge
- Hover/focus: reveals Re-run Search (ArrowsCounterClockwise) and Delete (Trash) icon buttons
- Tap/click anywhere: navigate to cached results

**Empty State:**
- SVG line-art illustration: magnifying glass over a clock
- `text-heading-3`: "No search history yet"
- `text-body-md`: "Your past searches will appear here so you can track prices over time."
- Primary button: "Start Searching"

**Price Alert Placeholder:**
- Small bell icon button on each history item
- Tooltip: "Price alerts coming soon"
- Visually present to set expectations for upcoming functionality

---

## 6. Interaction Patterns

### 6.1 Search Experience

1. User focuses the search bar (or presses `Cmd+K`). `shadow-focus` ring appears.
2. After typing 2 characters, a 300ms debounce timer starts.
3. Autocomplete dropdown appears with 150ms fade-in + 4px upward translate.
4. Suggestions load with a brief shimmer skeleton (200–400ms).
5. User types freely while dropdown is open; suggestions update in real time.
6. Pressing Enter or clicking "Search" submits the query.
7. On submission: the "Search" button shows a spinner, the progress tracker slides down.

**Input clearing:** Once 1+ characters are typed, an "X" icon button appears at the far right (replaces Search button position while typing). Clearing closes the dropdown and returns focus to the input.

---

### 6.2 Real-Time Progress Indicators (WebSocket)

| Event | UI Response |
|---|---|
| `search.started` | Tracker slides down, all steps in Queued state |
| `source.checking {id}` | That step transitions to Active (pulse animation) |
| `source.results {id, count}` | Step transitions to Complete, count badge appears |
| `source.timeout {id}` | Step transitions to Timed Out (red X) |
| `source.ratelimited {id}` | Step transitions to Rate Limited (amber pause) |
| `ai.analyzing` | A separate "AI Analysis" step at the end activates |
| `search.complete` | All steps complete, 600ms delay, tracker slides up + fades out; results render |

**Partial results rendering:** As each source completes, its result card begins rendering below the tracker — cards animate in with 200ms fade + 8px upward translate, staggered 50ms per card. The tracker does not dismiss until all sources have resolved.

**Status text** updates with each event using a 100ms cross-fade. Examples: "Checking 5 sources..." → "Got 12 results from Amazon" → "Analyzing prices..." → "Done. Showing 28 results from 6 sources."

---

### 6.3 Loading and Skeleton States

**Initial search:** Progress tracker appears → AI Summary Card skeleton → 3 comparison card skeletons. Skeletons replace progressively with real content (200ms fade per card) as data arrives. AI Summary skeleton remains until AI analysis completes.

**Re-run search:** Main content cross-fades to skeleton state (150ms fade-out, 100ms pause, skeleton fades in). "Refreshing prices..." banner appears at top of main content. Progress tracker runs standard sequence.

**Cached history result (no re-fetch):** Main content cross-fades from previous (150ms). No progress tracker. "Last updated {time ago}" label prominently in page header. "Re-run for fresh prices" secondary button in header.

---

## 7. Text-Based Wireframes

### 7.1 Search Page — Desktop

```
+-------------------------------------------------------------------+
| [TOP BAR - 60px]                                                  |
|  Shopping Companion                              [Settings Icon]  |
+---------------------------+---------------------------------------+
| [SIDEBAR - 280px]         | [MAIN CONTENT AREA]                  |
|                           |                                       |
| HISTORY                   |          (vertical center)           |
| [Search filter input]     |                                       |
| ---                       |   Find the best price, instantly.    |
| [History Item]            |   AI-powered comparison across       |
|   Sony WH-1000XM5         |   dozens of retailers.               |
|   Today, 2:14 PM          |                                       |
|   $279-$349   v -$12      |   +----------------------------------+|
| ---                       |   | [icon] Search for anything...   ||
| [History Item]            |   |                      [SEARCH]   ||
|   iPad Pro M4             |   +----------------------------------+|
|   Yesterday               |                                       |
|   $899-$1,049  No change  |   [Sony WH-1000XM5] [iPad] [Desk]   |
| ---                       |                                       |
| [History Item]            |   [Check] Real-time prices 20+ srcs  |
|   Standing Desk           |   [Spark] AI comparison & recs       |
|   Mar 10                  |   [Clock] Search history & tracking  |
|   $349-$620   ^ +$30      |                                       |
| ---                       |                                       |
| [History Item]            |                                       |
|   AirPods Pro 3           |                                       |
|   Mar 8                   |                                       |
|   $199-$249   v -$20      |                                       |
| ---                       |                                       |
| [+ 12 more]               |                                       |
+---------------------------+---------------------------------------+
```

---

### 7.2 Search Page — Mobile

```
+------------------------------------------+
| [TOP BAR - 56px]                         |
| [Menu]  Shopping Companion  [Search Ico] |
+------------------------------------------+
|                                          |
|                                          |
|    Find the best price, instantly.       |
|    AI-powered comparison across          |
|    dozens of retailers.                  |
|                                          |
|  +--------------------------------------+|
|  | [icon]  Search for anything...      ||
|  +--------------------------------------+|
|  |         [   SEARCH   ]              ||
|  +--------------------------------------+|
|                                          |
|  [Sony WH-1000XM5] [iPad Pro] [Desk]   |
|                                          |
|  [Check] Real-time prices from 20+      |
|  [Spark] AI comparison                  |
|  [Clock] Price tracking history         |
|                                          |
+------------------------------------------+
| [Search]  [Results]  [History] [Compare] |
+------------------------------------------+
```

---

### 7.3 Results Page — Desktop

```
+-------------------------------------------------------------------+
| [TOP BAR]                                                         |
|  Shopping Companion  [== Sony WH-1000XM5 ==========] [SEARCH]   |
+---------------------------+---------------------------------------+
| [SIDEBAR]                 | [MAIN CONTENT AREA]                  |
|                           |                                       |
| HISTORY                   |  "Sony WH-1000XM5 Headphones"  [h2] |
|                           |  28 results from 6 sources · 2:14 PM |
| [> Sony WH-1000XM5 ACTIVE]|  [Sort: Best Price v]    [Filter]   |
| ---                       |  ----------------------------------- |
| [History Item]            |                                       |
|   iPad Pro M4             |  [PROGRESS TRACKER]                  |
|   Yesterday               |  [Amzn] [BstB] [Wlmt] [Tgt] [B&H]  |
|   $899-$1,049             |   [ok]  [>>>]  [ok]   [ ]    [ ]    |
| ---                       |   Checking Best Buy...               |
| [History Item]            |  ----------------------------------- |
|   Standing Desk           |                                       |
|   Mar 10                  |  [AI SUMMARY CARD - full width]      |
|   $349-$620               |  [AI badge]  Best option for most... |
|                           |  Amazon at $279 free ship is lowest  |
|                           |  total of 6 sources. Best Buy matches|
|                           |  with same-day pickup available.     |
|                           |  [Lowest: Amazon] [Fast: BB] [Ret: ] |
|                           |  ----------------------------------- |
|                           |                                       |
|                           |  PRICE COMPARISON                    |
|                           |  Prices include estimated shipping   |
|                           |                                       |
|  [BEST DEAL CARD]         |  [SOURCE CARD]  [SOURCE CARD]        |
|  [Amazon logo]  IN STOCK  |  [BestBuy]      [Walmart]            |
|  $279.00                  |  IN STOCK       LIMITED              |
|  Free shipping            |  $279.00        $289.00              |
|  Total: $279.00           |  Free ship      Free ship            |
|  **** 4.2k reviews        |  Total: $279    Total: $289          |
|  30-day free returns      |  **** 2.1k      **** 8k              |
|  [    VIEW DEAL    ]      |  15-day ret     15-day ret           |
|  View Full Comparison     |  [VIEW DEAL]    [VIEW DEAL]          |
|                           |  Full Cmp       Full Cmp             |
|                           |  ----------------------------------- |
|                           |                                       |
|                           |  YOU MIGHT ALSO CONSIDER   [AI]      |
|                           |  Newer releases and alternatives     |
|                           |                                       |
|                           |  [XM6 card] [Bose] [AirPods] [XM4]  |
|                           |  Newer mdl  Compet  Apple   Older    |
|                           |  $329       $299    $249    $199     |
|                           |  [Search]   [Srch]  [Srch]  [Srch]  |
|                           |                                       |
+---------------------------+---------------------------------------+
```

---

### 7.4 Results Page — Mobile

```
+------------------------------------------+
| [TOP BAR - 56px]                         |
| [Menu]  Shopping Companion  [Search]     |
+------------------------------------------+
|                                          |
|  "Sony WH-1000XM5 Headphones"           |
|  28 results · 6 sources · 2:14 PM       |
|  [Sort: Best Price v]     [Filter]      |
|  -------------------------------------- |
|                                          |
|  [PROGRESS TRACKER]                     |
|  [Amzn][BstB][Wlmt][Tgt][Cst][B&H]    |
|   [ok]  [ok]  [ok]  [>>]  [  ]  [  ]  |
|  Checking Target...                     |
|  -------------------------------------- |
|                                          |
|  [AI SUMMARY CARD]                      |
|  [AI]  Best option for most buyers      |
|  Amazon at $279 free shipping is        |
|  the lowest total. Best Buy matches     |
|  with same-day pickup option.           |
|  [Lowest: Amazon] [Fast: BestBuy]       |
|  -------------------------------------- |
|                                          |
|  PRICE COMPARISON                       |
|                                          |
|  +--------------------------------------+|
|  | [BEST DEAL]  Amazon    IN STOCK     ||
|  | $279.00  Free ship     Tot: $279    ||
|  | **** 4,200 reviews                  ||
|  | 30-day free returns                 ||
|  | [         VIEW DEAL         ]       ||
|  | View Full Comparison                ||
|  +--------------------------------------+|
|                                          |
|  +--------------------------------------+|
|  | Best Buy              IN STOCK      ||
|  | $279.00  Free ship    Tot: $279     ||
|  | **** 2,100 reviews                  ||
|  | 15-day returns                      ||
|  | [         VIEW DEAL         ]       ||
|  +--------------------------------------+|
|                                          |
|  +--------------------------------------+|
|  | Walmart               LIMITED       ||
|  | $289.00  Free ship    Tot: $289     ||
|  +--------------------------------------+|
|                                          |
|  YOU MIGHT ALSO CONSIDER  [AI]         |
|  > Sony WH-1000XM6 (Newer)  — $329    |
|  > Bose QC45 (Competitor)   — $299    |
|  > AirPods Pro 2 (Apple)    — $249    |
|  [Show all alternatives]               |
|                                          |
+------------------------------------------+
| [Search]  [Results]  [History] [Compare] |
+------------------------------------------+
```

---

### 7.5 Comparison Detail Page — Desktop

```
+-------------------------------------------------------------------+
| [TOP BAR]                                                         |
|  Shopping Companion  [== Sony WH-1000XM5 ==========] [SEARCH]   |
+---------------------------+---------------------------------------+
| [SIDEBAR]                 | [MAIN CONTENT AREA]                  |
|                           |                                       |
| HISTORY                   |  Search / Sony WH-1000XM5 / Compare  |
|                           |                                       |
| [> Sony WH-1000XM5 ACTIVE]|  +------+  Sony WH-1000XM5          |
| ---                       |  | img  |  Wireless Noise-Cancelling |
| [History Item]            |  | 120px|  Headphones                |
|   iPad Pro M4             |  +------+  Best: $279.00             |
|   Yesterday               |           6 sources · Updated 2:14PM |
|                           |  [Columns v] [Attributes v] [Sort v] |
|                           |                                       |
|                           | +-------+--------+--------+----------+
|                           | |ATTR   | AMAZON | BESTBUY| WALMART  |
|                           | |       | [BEST] |        |          |
|                           | +-------+--------+--------+----------+
|                           | |Price  | $279   | $279   | $289     |
|                           | +-------+--------+--------+----------+
|                           | |Ship.  | Free   | Free   | Free     |
|                           | +-------+--------+--------+----------+
|                           | |Total  | $279   | $279   | $289     |
|                           | +-------+--------+--------+----------+
|                           | |Avail. |IN STOCK|IN STOCK| LIMITED  |
|                           | +-------+--------+--------+----------+
|                           | |Deliv. | 2 days | Pickup | 3-5 days |
|                           | +-------+--------+--------+----------+
|                           | |Rating | **** ½ | **** ½ | ****     |
|                           | |       | 4.2(2k)| 4.4(1k)| 4.1(8k) |
|                           | +-------+--------+--------+----------+
|                           | |Seller |Official|Official|Marketplace|
|                           | +-------+--------+--------+----------+
|                           | |Return | 30-day | 15-day | 15-day   |
|                           | +-------+--------+--------+----------+
|                           | |Warr.  | 1-year | 1-year | 1-year   |
|                           | +-------+--------+--------+----------+
|                           | |Cond.  | New    | New    | New      |
|                           | +-------+--------+--------+----------+
|                           | |Link   |  [->]  |  [->]  |  [->]   |
|                           | +-------+--------+--------+----------+
|                           |                                       |
|                           |  [AI]  DETAILED AI ANALYSIS          |
|                           |  Amazon and Best Buy are tied at...  |
|                           |  [Show more]                         |
|                           |                                       |
|                           |  RELATED SEARCHES                    |
|                           |  [Sony XM6] [Bose QC45] [AirPods]   |
|                           |                                       |
+---------------------------+---------------------------------------+
```

---

### 7.6 History Page — Desktop

```
+-------------------------------------------------------------------+
| [TOP BAR]                                                         |
|  Shopping Companion  [== (empty) ==========================]     |
+---------------------------+---------------------------------------+
| [SIDEBAR]                 | [MAIN CONTENT AREA]                  |
|                           |                                       |
| HISTORY                   |  Search History              [h1]    |
|                           |  42 searches                         |
| [> Sony WH-1000XM5 ACTIVE]|                          [CLEAR ALL] |
| [History Item]            |  ----------------------------------- |
|   iPad Pro M4             |                                       |
|   Yesterday               |  [Filter history...]  [Sort: Recent] |
| [History Item]            |  [From: ___________] [To: _________] |
|   Standing Desk           |                                       |
|   Mar 10                  |  TODAY                               |
| (list continues)          |                                       |
|                           |  +-----------------------------------+|
|                           |  | Sony WH-1000XM5    Today 2:14 PM ||
|                           |  | [Amazon] [BestBuy] [+4 more]     ||
|                           |  | $279-$349          v -$12 (4%)   ||
|                           |  |                [Re-run] [Delete] ||
|                           |  +-----------------------------------+|
|                           |                                       |
|                           |  +-----------------------------------+|
|                           |  | iPad Pro M4 11"    Today 10:05AM ||
|                           |  | [Amazon] [BestBuy] [Apple] [+2]  ||
|                           |  | $899-$1,099        No change     ||
|                           |  |                [Re-run] [Delete] ||
|                           |  +-----------------------------------+|
|                           |                                       |
|                           |  YESTERDAY                           |
|                           |                                       |
|                           |  +-----------------------------------+|
|                           |  | Standing Desk L-Shape    Mar 14  ||
|                           |  | [Wayfair] [Amazon] [IKEA]        ||
|                           |  | $349-$620          ^ +$30 (5%)  ||
|                           |  +-----------------------------------+|
|                           |                                       |
|                           |  THIS WEEK                           |
|                           |                                       |
|                           |  +-----------------------------------+|
|                           |  | AirPods Pro 3            Mar 12  ||
|                           |  | [Apple] [Amazon] [BestBuy]       ||
|                           |  | $199-$249          v -$20 (8%)  ||
|                           |  +-----------------------------------+|
|                           |                                       |
|                           |  EARLIER                             |
|                           |                                       |
|                           |  +-----------------------------------+|
|                           |  | 4K OLED TV 65"           Mar 5   ||
|                           |  | [Samsung] [Sony] [LG] [+3]       ||
|                           |  | $899-$1,800        No change     ||
|                           |  +-----------------------------------+|
|                           |                                       |
+---------------------------+---------------------------------------+
```

---

## 8. Motion and Animation

### 8.1 Principles

Motion serves one of three purposes: feedback (confirming an action occurred), continuity (tracking state changes), or attention direction (drawing eyes to newly important information). Motion is never decorative.

### 8.2 Timing Functions

| Token | CSS Value | Usage |
|---|---|---|
| `ease-in-out` | cubic-bezier(0.4, 0, 0.2, 1) | Default transitions |
| `ease-out` | cubic-bezier(0, 0, 0.2, 1) | Elements entering the screen |
| `ease-in` | cubic-bezier(0.4, 0, 1, 1) | Elements leaving the screen |
| `spring` | cubic-bezier(0.34, 1.56, 0.64, 1) | Interactive feedback (button press, selection) |

### 8.3 Duration Standards

| Context | Duration |
|---|---|
| Micro-interactions (hover, focus) | 100ms |
| Component state changes (badge color) | 150ms |
| Panel transitions (slide-in, slide-out) | 200ms |
| Page-level content transitions | 250ms |
| Results card cascade | 200ms per card + 50ms stagger |
| Progress tracker dismiss delay | 600ms hold, then 200ms out |

### 8.4 Key Animation Specifications

**Progress tracker active step:** Radial pulse scales 100% to 160%, fades 40% to 0% opacity, 1.2s loop. Stops instantly on state transition. In reduced-motion mode: static fill, no animation.

**Result card entry:** `opacity 0→1`, `translateY(8px)→0`, 200ms ease-out, staggered 50ms per card.

**Skeleton shimmer:** Gradient scans left-to-right at 2s linear infinite. Replaced with static 50% opacity fill in reduced-motion mode.

**Price drop badge (significant drops):** Single spring animation on first render: scale 0.8→1.1→1.0, 300ms. Does not repeat.

**History item hover:** Re-run and Delete buttons transition from `opacity: 0, translateX(8px)` to resting position over 150ms ease-out. Price badge shifts left 8px simultaneously.

---

## 9. Edge Cases and Empty States

### No Results Found

- SVG illustration: magnifying glass with question mark
- `text-heading-3`: "No results found for '{query}'"
- `text-body-md`: "We searched {N} sources and couldn't find this product. Try refining your search."
- AI-generated "Did you mean..." spelling/correction chips
- Primary button: "Try a different search" (clears and focuses search bar)

### All Sources Timed Out

- Amber warning banner at top of results area
- Partial results shown (if any) with staleness annotation on each card
- "Try again" secondary button to re-trigger the WebSocket search

### Single Source Result

- AI Summary Card notes: "We only received results from one source. Comparison data is limited."
- No "Best Deal" badge (no comparison possible)
- "Check again later" secondary button

### Network Offline State

- Persistent banner below top bar: "You're offline. Searches are unavailable. Cached results are still accessible."
- Search bar disabled (`cursor: not-allowed`, visually grayed)
- History items with cached results remain clickable with a "Cached" chip indicator
- History items without cache: grayed out, non-interactive

### Stale Cache (History items older than 7 days)

- Timestamp in `color-warning-700`
- Small "7+ days old" chip
- Tooltip: "Prices may have changed significantly. Re-run to get current prices."

### No History (Empty Sidebar/History Page)

- Sidebar: italic `color-neutral-500` text — "Your search history will appear here." with ClockCounterClockwise icon
- History page: full empty state with illustration, heading, body, and "Start Searching" primary button

### Very Long Search Query (120+ characters)

- Input truncates displayed text with ellipsis; full text is stored and used for the search
- Results page heading truncates to 80 characters with tooltip on hover showing full query

---

## 10. Design Decisions Log

**Decision 001: Persistent sidebar history on desktop vs. separate history page**
Chosen: Persistent sidebar. Price comparison is iterative — users frequently return to previous searches. A persistent sidebar makes this access zero-cost. A dedicated history page would require navigating away from active results, breaking the user's flow.

**Decision 002: WebSocket step-tracker instead of a single loading spinner**
Chosen: Step-by-step progress tracker. AI searches take 5–15 seconds. A spinner for this duration provides no information. The progress tracker demonstrates value — users see the app querying 6+ sources simultaneously. User perception of wait time decreases when meaningful progress is visible. Fake percentage bars were rejected for being inherently inaccurate with parallel async processes.

**Decision 003: AI content visually distinguished with an AI badge**
Chosen: Consistent AI badge on all AI-generated content. Regulatory and trust landscape requires transparency. Users also make better decisions when they can distinguish raw scraped data from AI interpretation. The badge is subtle but present.

**Decision 004: Monospace typeface for all price values**
Chosen: JetBrains Mono for prices. Tabular number alignment in comparison tables is critical for price scanning. Monospace ensures vertical alignment without fixed column widths, enabling flexible responsive layouts. The visual distinction also helps users' eyes locate price data instantly in dense cards. Inter's tabular-nums feature was considered but found insufficiently distinct at small sizes.

**Decision 005: Best deal card uses a left border, not a full background color**
Chosen: 3px left border in `color-success-500` plus a subtle tint. A full-color card background would dominate the 3-column grid and draw the eye before the user could read competing prices. The left border signals distinction clearly without overpowering the layout.

**Decision 006: Show-all results, not infinite scroll**
Chosen: Show all results (up to 20), with a "Show more" button if needed. Price comparison users want to see all options before deciding. Infinite scroll obscures the total count and leaves users uncertain whether they've seen everything. A show-all approach provides closure.

**Decision 007: Bottom navigation on mobile instead of hamburger-only**
Chosen: Persistent bottom navigation bar (4 items). Bottom nav is the dominant mobile navigation convention across iOS and Android. It keeps primary destinations thumb-accessible and is more discoverable for new users than a hidden hamburger menu.

---

*End of Shopping Companion UI/UX Design Document v1.0*

*All screens, components, states, and decisions documented for development handoff. Updates should be added to Section 10 with a new numbered entry and version note.*
