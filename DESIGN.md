---
name: OpenMemory
description: A local-first, team-shared memory layer for AI engineering agents
colors:
  primary: "hsl(217, 91%, 60%)"
  bg-deep: "#020617"
  background: "hsl(222, 47%, 4%)"
  surface: "hsl(222, 47%, 6%)"
  muted: "hsl(217, 33%, 17%)"
typography:
  body:
    fontFamily: "var(--font-space-grotesk), system-ui, sans-serif"
  mono:
    fontFamily: "var(--font-jetbrains-mono), ui-monospace, monospace"
rounded:
  md: "0.75rem"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "hsl(210, 40%, 98%)"
    rounded: "calc({rounded.md} - 2px)"
    padding: "0.5rem 1rem"
---

# Design System: OpenMemory

## 1. Overview

**Creative North Star: "The Agent Control Center"**

OpenMemory is a precision instrument designed for observability and control. The aesthetic philosophy is technical, authoritative, and clean, reflecting its role as a local-LAN hub for AI agents. It prioritizes information density and instant responsiveness over decorative fluff. We explicitly reject bloated enterprise UI patterns and bubbly, playful colors in favor of a crisp, terminal-native environment.

**Key Characteristics:**
- High information density
- Crisp, technical contrast
- Native, local-first responsiveness
- Utilitarian structure

## 2. Colors

Technical navy and stark blues that feel native to a terminal environment.

### Primary
- **Agent Blue** (hsl(217, 91%, 60%)): Used for primary actions, focus rings, and active state highlights.

### Neutral
- **Background Dark** (hsl(222, 47%, 4%)): The foundational canvas.
- **Deep Slate** (#020617): Used in the radial background gradient for depth.
- **Surface Card** (hsl(222, 47%, 6%)): Slightly elevated surfaces for cards and popovers.
- **Muted Border** (hsl(217, 33%, 17%)): Used for dividers, inputs, and secondary elements.

### Named Rules
**The Precision Rule.** Do not dilute the interface with multiple accent colors. The primary blue carries the hierarchy; the rest of the interface relies on shade and contrast.

## 3. Typography

**Display Font:** Space Grotesk (with system-ui)
**Body Font:** Space Grotesk (with system-ui)
**Label/Mono Font:** JetBrains Mono (with ui-monospace)

**Character:** Technical and highly legible. The pairing of a grotesque sans with a strict monospace reinforces the developer-first tooling nature.

### Hierarchy
- **Body** (400, 0.875rem, normal): The default text for general content and descriptions.
- **Heading** (500, 0.9375rem, normal): For card titles and section headers.
- **Label** (500, 0.75rem, normal): For metadata, small tags, and secondary information.
- **Caption** (400, 0.6875rem, normal): For subtle timestamp or extremely dense data.

## 4. Elevation

OpenMemory uses a flat-by-default, tonal layering approach combined with subtle glassmorphism (`backdrop-filter: blur(12px)`) for floating panels. Depth is conveyed primarily through background lightness and border contrast, not heavy drop shadows.

### Shadow Vocabulary
- **Glass Panel** (`0 8px 32px 0 rgba(0, 0, 0, 0.37)`): Used for elevated overlays and modals over the deep background.

## 5. Components

### Buttons
- **Shape:** Gently rounded (0.75rem / 12px for containers, minus offset for inner buttons)
- **Primary:** Agent Blue background with white text.
- **Hover / Focus:** Clear focus rings with offset, slight opacity drop on hover.
- **Ghost:** Transparent background with muted text, turning to accent on hover.

### Cards / Containers
- **Corner Style:** 12px radius.
- **Background:** Surface Card color (hsl(222, 47%, 6%)) or translucent glass.
- **Border:** Subtle 1px border using Muted Border.
- **Internal Padding:** 1rem to 1.5rem depending on viewport.

### Inputs / Fields
- **Style:** Muted Border stroke, background matches surface.
- **Focus:** 2px solid primary blue ring with a 2px offset.

## 6. Do's and Don'ts

### Do:
- **Do** maintain high information density for developer clarity.
- **Do** use JetBrains Mono for IDs, tokens, and code snippets.
- **Do** respect `prefers-reduced-motion` for all transitions.

### Don't:
- **Don't** use bloated enterprise UI patterns.
- **Don't** use bright, playful, or "bubbly" colors.
- **Don't** use the saturated AI-app "cream/sand" default; keep it crisp and dark.
