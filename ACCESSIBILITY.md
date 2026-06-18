# Accessibility (WCAG 2.1 AA) — UM Research Dashboard

This document describes the accessibility work done on the frontend and how the
dashboard maps to the **Web Content Accessibility Guidelines (WCAG) 2.1 Level AA**.

- **Target conformance:** WCAG 2.1, Level AA
- **Scope:** the Next.js frontend in `frontend/` (dashboard at `/` and the faculty
  profile route `/authors/[id]`)
- **Last reviewed:** 2026-06-13

---

## 1. Summary of what was implemented

| Area | What was done | Files |
|------|---------------|-------|
| Language of page | `<html lang="en">` | `app/layout.tsx` |
| Skip link | "Skip to main content" link, visually hidden until focused, jumps to `#main-content` | `app/layout.tsx`, `app/globals.css`, `app/page.tsx`, `app/authors/[id]/page.tsx` |
| Landmarks | `<header>`, `<nav>`, `<main id="main-content">`, `<footer>` on both routes | `app/page.tsx`, `app/authors/[id]/page.tsx`, `Header.tsx` |
| Tabs (ARIA pattern) | `role="tablist"` / `role="tab"` with `aria-selected`, `aria-controls`, roving `tabindex`, and ←/→/Home/End keyboard navigation; panels are `role="tabpanel"` linked back via `aria-labelledby` | `Header.tsx`, `app/page.tsx` |
| Keyboard-operable table rows | Clickable rows expose `role="button"`, `tabIndex=0`, and Enter/Space activation | `DataTable.tsx` |
| Form controls labelled | All search boxes and the year/type selects have `aria-label`s (or linked `<label>`); the global search is a labelled `combobox` with a `listbox` of `option`s | `Header.tsx`, `Authors.tsx`, `Journals.tsx`, `Patents.tsx`, `Publications.tsx`, `CitationSources.tsx` |
| Icon-only controls | ORCID / Scholar links, the close (✕) and back (←) buttons have text or `aria-label`; the emoji itself is `aria-hidden` | `Authors.tsx`, `CitationSources.tsx`, `app/authors/[id]/page.tsx` |
| Charts text alternatives | Every Chart.js canvas is `role="img"` with an auto-generated data summary `aria-label`; decorative sparklines are `aria-hidden` | `charts/BarChart.tsx`, `charts/HorizontalBarChart.tsx`, `charts/LineChart.tsx`, `charts/SparklineChart.tsx` |
| Map text alternative | The SVG bubble map is `role="img"` with an `aria-label` summarising the top collaborating countries | `tabs/Collaborations.tsx` |
| Status messages | Data-unavailable banners use `role="alert"` | `ErrorBanner.tsx` |
| Visible focus | Global `:focus-visible` outline (3px UM-red, 2px offset) on all interactive elements | `app/globals.css` |
| Reduced motion | `@media (prefers-reduced-motion: reduce)` neutralises animations/transitions | `app/globals.css` |
| Table semantics | `<th scope="col">` headers | `DataTable.tsx` |

---

## 2. Mapping to WCAG 2.1 AA success criteria

### Perceivable
- **1.1.1 Non-text Content (A):** Charts and the collaboration map carry
  `role="img"` + descriptive `aria-label`s; purely decorative emoji/icons/sparklines
  are `aria-hidden="true"`.
- **1.3.1 Info & Relationships (A):** Semantic landmarks, data tables with `<th scope>`,
  ARIA tabs/tabpanels, labelled form fields.
- **1.3.2 Meaningful Sequence (A):** DOM order matches visual order; hidden tab panels
  use the `hidden` attribute so they are skipped by assistive tech.
- **1.4.1 Use of Color (A):** Information is never conveyed by color alone — OA status,
  source, and ranks all carry text labels.
- **1.4.3 Contrast (Minimum) (AA):** Body text `#1A1D23` and muted text `#6B7280` on
  white/light backgrounds meet ≥4.5:1; navy/red on white and white-on-navy meet AA.
  (The unused `--um-text-light` token was confirmed not applied to any text.)
- **1.4.10 Reflow / 1.4.4 Resize Text:** Layout is responsive (CSS grid/flex with
  breakpoints); `rem`-based sizing supports zoom.

### Operable
- **2.1.1 Keyboard (A):** All interactive elements are reachable and operable by
  keyboard — tabs (arrow keys), clickable table rows (Enter/Space), search results
  (Enter/Space), buttons, links, selects.
- **2.1.2 No Keyboard Trap (A):** No focus traps; the profile is a full page (no modal).
- **2.4.1 Bypass Blocks (A):** Skip-to-content link.
- **2.4.3 Focus Order (A):** Logical, source-order focus; roving tabindex in the tablist.
- **2.4.7 Focus Visible (AA):** Global `:focus-visible` outline.
- **2.3.3 Animation from Interactions (AAA, honored):** `prefers-reduced-motion` support.

### Understandable
- **3.1.1 Language of Page (A):** `lang="en"`.
- **3.2.x Predictable:** Consistent header/tab navigation across views; links that open
  new tabs announce "(opens in a new tab)".
- **3.3.2 Labels or Instructions (A):** Every input/select is labelled.

### Robust
- **4.1.2 Name, Role, Value (A):** Correct roles/states on tabs, tabpanels, combobox,
  listbox/options, image charts, and icon buttons.
- **4.1.3 Status Messages (AA):** Error/availability banners use `role="alert"`.

---

## 3. Keyboard reference

| Control | Keys |
|---------|------|
| Tab bar | `←` / `→` move between tabs, `Home` / `End` jump to first/last, `Enter`/`Space`/click activate |
| Author / clickable rows | `Tab` to focus, `Enter` or `Space` to open |
| Global search results | `Tab` to focus an option, `Enter`/`Space` to go |
| Skip link | `Tab` once on page load, `Enter` |
| Everything else | Standard `Tab` / `Shift+Tab`, `Enter`/`Space` |

---

## 4. Known limitations / follow-ups

- **Chart detail:** charts expose a *summary* of the top values via `aria-label`, not a
  full per-point data table. For full AAA-level parity, consider a visually-hidden
  `<table>` mirror of each chart's data.
- **Color contrast audit:** values were reviewed against AA by inspection; run an
  automated contrast pass (axe / Lighthouse) as a regression guard.
- **No automated a11y tests yet:** recommend adding `@axe-core/playwright` or
  `jest-axe` to CI.

## 5. How to test

```bash
# Lighthouse (Chrome) accessibility audit
npx lighthouse http://localhost:8000 --only-categories=accessibility --view

# axe CLI
npx @axe-core/cli http://localhost:8000
```

Manual checks: unplug the mouse and navigate the whole dashboard with the keyboard;
run VoiceOver (⌘+F5 on macOS) over the tabs, a data table, a chart, and a faculty
profile.
