---
name: interface-review
description: "Review UI code systematically across accessibility, layout, writing, typography, and polish. Produces prioritized, evidence-based file:line findings table. Use when reviewing UI code, evaluating design quality, checking UX polish, or conducting pre-merge frontend craft audits."
---

# Review the interface as one system

A strong interface is not five independent audits stapled together. Position and spacing carry hierarchy before a word is read, the words themselves do the explaining, type makes them legible, and polish is what makes the result feel deliberate rather than assembled. Review the whole experience, then consolidate into one prioritized verdict.

## Use This Skill When

- Reviewing front-end pull requests, components, or screens for design craft and usability.
- Conducting systematic accessibility, layout, copy, typography, or UI polish audits.
- Identifying visual inconsistencies, broken keyboard navigation, contrast failures, or missing focus states.
- Auditing UI code pre-merge to ensure compliance with design system tokens and responsive rules.

## Operating Rules

1. **Slow the interface down**: Walk it as a keyboard-only user first — every flow must complete without mouse input.
2. **Squint and stress-test**: Squint to check if hierarchy holds, resize viewports to catch bad wrapping, and replay animations at 10% speed to expose stutter and bad easing.
3. **Match the project's styling system**: Express findings and fixes in the codebase's existing conventions (Tailwind, CSS Modules, styled-components). Never introduce a second styling approach.
4. **Evidence-based findings**: Every finding cites `path/to/file:line`, quotes current code, and suggests an exact diff.
5. **Review order**: Foundational failures must not be hidden by polish:
   1. Accessibility
   2. Layout
   3. Writing
   4. Typography
   5. UI polish

## Step-by-Step Review Workflow

### 1. Resolve Scope & Mode

- `quick`: Primary path and high-traffic states only. Cap at 5 findings (HIGH and MEDIUM only).
- `full`: Entire requested surface across all 5 domains, including empty, loading, error, and narrow states. Cap at 15 findings.

### 2. Reconnaissance

Check framework, styling system, component library, design tokens, supported viewports, and localization setup.

### 3. Domain Checks

#### 1. Accessibility Floor
- **Native Elements First**: Use `<button>` for actions, `<a href>` for navigation. Never `<div onClick>`.
- **Visible Focus Rings**: Style `:focus-visible` with minimum 2px solid perimeter. Never `outline: none` without verified replacement.
- **Full Keyboard Support**: Escape closes overlays, arrow keys move within composite widgets (tabs, menus), Tab moves between widgets. Roving tabindex (`0` on active, `-1` on rest).
- **Focus Trapping**: Modals must trap focus, set `inert` on background, restore focus on close, and use `overscroll-behavior: contain`.
- **Target Sizes**: 44×44px touch targets minimum (24×24px WCAG AA minimum). Use pseudo-elements to expand hit targets if visual element is small.
- **Labels & Forms**: Form inputs require explicit labels (not placeholders). Autocomplete and correct `inputmode`. Paste must not be blocked.
- **Accessible Names**: Icon buttons require descriptive `aria-label`. Decorative elements require `aria-hidden="true"`.
- **Redundant Status**: Status must not rely on color alone (pair with icon, badge, or text). Ensure WCAG AA contrast (4.5:1 normal text, 3:1 large text/UI controls).
- **Reduced Motion**: Wrap animations in `@media (prefers-reduced-motion: no-preference)`. Under reduced motion, replace movement with subtle opacity crossfades.

#### 2. Layout & Spacing
- **Negative Space First**: Group with whitespace, then background cards, separator lines last. Inter-group gap >= 2× intra-group gap.
- **Control Distinction**: Interactive elements must look interactive; never style controls identically to adjacent static text.
- **Alignment**: Align to shared edges. Use logical CSS properties (`padding-inline-start`, `margin-inline-end`) for direction independence.
- **Visual Clearance**: Minimum 12px between adjacent bordered/filled controls, 24px around borderless icon controls.
- **Responsive Resilience**: Breakpoints derived from content, not arbitrary device presets. Container queries for component adaptation. Prevent text clipping and overflow.

#### 3. Writing & Copy
- **Consistent Voice, Contextual Tone**: Neutral/minimal for routine settings; calm and serious for errors/destructive flows; warm for empty states.
- **Verb-First Actions**: Button labels begin with concrete verbs ("Save draft", "Delete project", "Export CSV"). Never vague "OK" or "Yes".
- **Self-Descriptive Links**: Link text must make sense out of context ("Read billing guide", never bare "Click here" or "Learn more").
- **Localization-Safe Strings**: Use templated strings with pluralization arguments; never concatenate sentences around variables.

#### 4. Typography & Readability
- **Hierarchy Scale**: Clear size/weight distinctions between page title, section header, body, and caption.
- **Measure & Line Length**: Keep body text line length between 45 and 75 characters for optimal reading ergonomics.
- **Line Heights**: Minimum 1.5 for body text, tighter (1.1-1.25) for large display headings.

#### 5. UI Polish & Details
- **Hover/Active States**: Every interactive control provides instant visual feedback on hover, active, and focus.
- **Layout Shift Prevention**: Reserve aspect-ratio boxes or dimensions for images, skeletons, and dynamic data to eliminate Cumulative Layout Shift (CLS).
- **Micro-Interactions**: Easing functions should feel physical (ease-out for entries, ease-in for exits, durations 150-300ms).

## Report Output Format

Format the final findings in a single prioritized Markdown table:

| Severity | Domain | Location | Issue | Suggested Change |
|---|---|---|---|---|
| HIGH | Accessibility | `src/components/Modal.tsx:42` | Missing focus trap and ESC key listener | Wrap with FocusScope / add onKeyDown Escape |
| MEDIUM | Writing | `src/pages/Settings.tsx:110` | Consequential action button labeled "OK" | Change button label to "Revoke API Key" |
| LOW | Polish | `src/styles/card.css:15` | Hover transform causes subpixel blur | Add `backface-visibility: hidden` or use transform-gpu |

## Sources

- [W3C WAI ARIA Authoring Practices Guide (APG)](https://www.w3.org/WAI/ARIA/apg/)
- [WCAG 2.2 Guidelines](https://www.w3.org/TR/WCAG22/)
- [Vercel Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines)
