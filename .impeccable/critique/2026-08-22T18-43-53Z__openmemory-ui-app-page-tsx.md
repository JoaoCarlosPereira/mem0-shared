---
target: openmemory/ui/app/page.tsx
total_score: 22
p0_count: 1
p1_count: 2
timestamp: 2026-08-22T18-43-53Z
slug: openmemory-ui-app-page-tsx
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Skeletons/hints OK; archive/pause fail silently |
| 2 | Match System / Real World | 3 | Marketing tagline on internal tool is odd |
| 3 | User Control and Freedom | 2 | No dismiss for Install; no undo for archive |
| 4 | Consistency and Standards | 2 | Search → `/memories` vs pagination stays on `?`; duplicate taglines |
| 5 | Error Prevention | 3 | Confirm delete + policy; good |
| 6 | Recognition Rather Than Recall | 2 | No clear “Memories” page title; dead clear-filters state |
| 7 | Flexibility and Efficiency | 1 | No shortcuts; Install always blocks returning power users |
| 8 | Aesthetic and Minimalist Design | 1 | Three jobs on one screen; rainbow KPIs; competing Install `h1` |
| 9 | Error Recovery | 3 | Retry on metrics/memories; archive/pause recovery is weak |
| 10 | Help and Documentation | 2 | Install docs strong; memory ops thin |
| **Total** | | **22/40** | **Acceptable** |

## Anti-Patterns Verdict

**LLM assessment**: Yes, it reads as an AI-generated SaaS dashboard. It relies heavily on saturated AI grammar (uppercase tracking-widest eyebrow taglines), identical fade-slide-down staggers on every block, and a hero-metric wall of KPI cards with rainbow accents. The multi-accent palette violates the **Precision Rule** from `DESIGN.md`, and the glass/rounded-2xl chrome strays from the "Control Center" mandate.

**Deterministic scan**: The CLI detector (`detect.mjs`) returned 0 findings, meaning no strict structural anti-patterns were caught by rules alone. The issues here are holistic composition and architectural layout rather than syntax-level bad practices.

**Visual overlays**: Skipped. No browser automation tool was available in this session to inject the overlay.

## Overall Impression
The page is trying to be three different things at once: a status dashboard, an onboarding wizard, and a memory workbench. While the dark technical direction is correct, the layout creates high cognitive load and buries the primary user job (viewing/managing memories) under a mountain of setup and generic metrics.

## What's Working
1. **Operational honesty in metrics**: Queue depth, worker hints, stalled/failed alerts (`OverviewMetrics`) match LAN ops reality.
2. **Install content quality**: Group lock, token banner, shell variants, and copy affordances are concrete and task-focused.
3. **Delete path discipline**: `ConfirmDeleteDialog` + deletion-policy gating aligns well with the memory-protection culture.

## Priority Issues

**[P0] No single primary job on home**
- **What**: Tagline → 5 KPIs → full Install → filters → table.
- **Why it matters**: Breaks the “Agent Control Center” concept; high cognitive load; nothing acts as the hero task.
- **Fix**: Create one primary path (e.g. memories/status). Move Install to `/install` or collapse it. Cap KPIs to ≤4, alert-first.
- **Suggested command**: `$impeccable layout`

**[P1] Always-on Install for returning users**
- **What**: The full wizard appears on every home load.
- **Why it matters**: Patronizing to returning users; delays time-to-value for power users checking their memory streams.
- **Fix**: Use progressive disclosure — collapse to “Reinstalar / novo host” after first success, or show only when no token/group is present.
- **Suggested command**: `$impeccable onboard`

**[P1] Motion / accessibility gap**
- **What**: `animation.css` gates visibility with `opacity: 0` but includes zero `prefers-reduced-motion` fallbacks.
- **Why it matters**: Violates PRODUCT/DESIGN constraints. Users heavily dependent on accessibility tools may get blank/delayed content.
- **Fix**: Make content visible by default; reduce/disable animations entirely under `prefers-reduced-motion`.
- **Suggested command**: `$impeccable animate`

**[P2] Rainbow KPIs + side-stripe vs brand**
- **What**: Multi-accent `KpiCard` + `border-l-2`.
- **Why it matters**: Breaks the DESIGN.md Precision Rule (primary blue only) and relies on color alone for status.
- **Fix**: Stick to Agent Blue and tonal hierarchy. Alerts should use a specific color (rose) plus text/icon, rather than painting five different hues.
- **Suggested command**: `$impeccable colorize`

**[P2] Search from home abandons the page**
- **What**: `MemoryFilters` search forces `router.push('/memories?...')`.
- **Why it matters**: Breaks continuity and is inconsistent with in-page pagination.
- **Fix**: Keep the user on `/` with query params, or make home a true dashboard without an embedded full memory search.
- **Suggested command**: `$impeccable clarify`

## Persona Red Flags

**Alex (Power User)**
- The primary task (scan/search memories) is buried under the Install block.
- No keyboard shortcuts for search, filters, or bulk actions.
- Search navigates away from the page, causing friction.
- Uniform entrance animations are not skippable.

**Sam (Accessibility-Dependent User)**
- Animated sections start invisible; screen readers or keyboard navigation may hit empty or delayed regions.
- No `prefers-reduced-motion` support anywhere.
- Search icon is decorative, but input has only a placeholder (weak labeling).
- Alert/status rely too heavily on color-coding without sufficient text contrast.

## Minor Observations
- The tagline is duplicated: once as a page eyebrow and again in the Install description.
- `MemoriesSection` empty-state “clear filters” uses an unused local state (`selectedCategory`/`selectedClient`) making it a dead path.
- Archive/pause errors only show up in `console.error` without a visible toast.
- Mixed icon packs (`lucide-react` vs `react-icons/fi`).

## Questions to Consider
- If this is a **control center**, why is the first scrollable third a **setup wizard** every day?
- What would a confident home look like with **one** sentence of status and a memory stream — and Install behind a door?
- Would the team tolerate a home that feels more like **Linear’s inbox** (dense list + status) than a **SaaS metric collage**?
