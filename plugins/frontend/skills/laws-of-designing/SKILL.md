---
name: laws-of-designing
description: Follow these 20 foundational UX laws and core design principles whenever designing, building, reviewing, or revising a user interface. Applies across layouts, navigation, onboarding, forms, settings, dashboards, and interactive flows to minimize confusion, reduce friction, prevent errors, and optimize task completion.
---

# Laws of Designing (UX Design Instructions)

Follow these instructions whenever you design, build, critique, or revise a user interface. Apply them across layouts, navigation, onboarding, forms, settings, dashboards, and interactive flows.

Your goal is to minimize confusion, reduce cognitive effort, prevent mistakes, and help users complete their intended task as quickly and pleasantly as possible.

---

## The 20 Laws of UX Design

### 1. Reduce Choices per Screen: Hick's Law
*The time required to make a decision increases with the number and complexity of available choices.*
- Give each screen one clear, unambiguous purpose.
- Remove irrelevant, secondary, or low-priority options from the primary view.
- Break complicated multi-stage decisions into bite-sized progressive steps.
- Pre-select or prominently recommend an option when users may hesitate or struggle to choose.

### 2. Make Targets Large: Fitts's Law
*Large, nearby targets are significantly faster and easier to accurately interact with.*
- Make buttons, links, and input controls sufficiently large to click or tap without precision anxiety (minimum 44x44px for touch targets).
- Provide generous clickable padding around controls rather than restricting clicks to text or small glyphs.
- Avoid tiny standalone icons as the sole interaction target.
- Expand the hit area around important controls using visual boundaries or invisible padding.

### 3. Follow Familiar Patterns: Jakob's Law
*Users spend most of their time on other products and expect your product to work like products they already understand.*
- Use established, battle-tested interface conventions and standards.
- Place primary navigation, search, settings, and profile controls where users universally expect them (e.g., top-right for account, top/side for navigation).
- Use standard, recognized iconography (magnifying glass for search, gear for settings, cart for checkout).
- Do not invent novel interaction mechanics unless doing so provides an undeniable, 10x user advantage.

### 4. Group Related Information: Law of Proximity
*Elements positioned near one another are perceived by the human visual system as related.*
- Place related labels, helper texts, inputs, and controls directly adjacent to one another.
- Use intentional spacing hierarchies (tight spacing between related items, looser spacing between distinct groups).
- Separate unrelated groupings with extra whitespace rather than relying strictly on heavy borders or dividers.
- Let whitespace establish the structural hierarchy before reaching for lines or background cards.

### 5. Break Content Into Chunks: Miller's Law
*Working memory can only comfortably process a limited amount of discrete information at once (typically 5 to 7 items).*
- Divide long, dense content into small, meaningful, digestible chunks.
- Break multi-field forms and elaborate configurations into distinct, sequential steps or fieldsets.
- Use clear visual headings, scannable bullet points, and concise section labels.
- Avoid forcing users to memorize numbers, IDs, or settings across disparate screens.

### 6. Respond Within 400 Milliseconds: Doherty Threshold
*Productivity and user engagement soar when computer systems and users interact at a pace that ensures neither has to wait (<400ms).*
- Acknowledge every click, tap, submission, and keystroke immediately.
- Display instant feedback: loading skeletons, spinner indicators, progress bars, or state transitions when work cannot be completed synchronously.
- Use optimistic UI updates for safe, reversible actions (e.g., likes, toggles, additions).
- Never leave users wondering whether an action registered or whether the system is frozen.

### 7. Highlight the Primary Action: Von Restorff Effect (Isolation Effect)
*When multiple similar objects are present, the one that differs from the rest is most likely to be remembered and acted upon.*
- Give the primary call-to-action (CTA) the strongest visual prominence (contrasting brand color, weight, elevated surface).
- Maintain strictly one dominant, unmistakable primary action per section or viewport.
- Subordinate secondary actions with ghost, outline, or subtle neutral treatments.
- Prevent button fatigue: never have multiple saturated buttons screaming for attention simultaneously.

### 8. Place Key Actions Nearby: Fitts's Law & Spatial Affinity
*Interaction becomes faster and more natural when important targets reside close to the user's current spatial focus.*
- Anchor actions directly adjacent to the content they modify or control.
- Place form submission and validation buttons immediately adjacent to the final input field.
- Position frequent or repetitive actions within effortless reach of the cursor or thumb zone.
- Avoid forcing unnecessary eye-tracking travel across wide displays to find a submit button.

### 9. Put Essentials First: Serial Position Effect
*People remember and prioritize the first (Primacy) and last (Recency) items in a sequence most clearly.*
- Place crucial information, high-value navigation, and core value propositions first.
- Anchor final deliverables, takeaways, or primary conversions at the conclusion of the flow.
- Relegate supplementary context or low-priority details to the middle.
- Order menus, lists, and options in direct alignment with user priority and task frequency.

### 10. End Flows Memorably: Peak-End Rule
*Users judge an overall experience largely by its emotional peak and the quality of its conclusion.*
- Design a satisfying, reassuring, and celebratory completion state.
- Clearly confirm what the user just accomplished (e.g., "Order #1234 Placed", "Invoice Sent").
- Explicitly set expectations by explaining what happens next and offering logical follow-up actions.
- Never abandon the user on a blank, ambiguous, or dead-end screen.

### 11. Show Visible Progress: Zeigarnik Effect
*Incomplete tasks occupy mental bandwidth and motivate users to return and finish them.*
- Clearly visualize progress: step numbers, completed checkmarks, and percentage bars.
- Automatically persist user draft progress to localStorage or database backend.
- Make resuming interrupted workflows completely frictionless with "Continue where you left off" prompts.
- Use structured checklists and milestones for complex multi-step onboarding or profile completion.

### 12. Simplify Complex Interfaces: Law of Prägnanz (Simplicity)
*The human eye seeks simplicity, order, and harmony in ambiguous or complex visual structures.*
- Favor clean, geometric layouts and instantly recognizable visual patterns.
- Eliminate visual noise, unnecessary ornament, redundant borders, and extraneous badges.
- Create an intuitive visual hierarchy with consistent typography scales and deliberate contrast.
- Ensure the user can grasp the structure, status, and affordances of the page in under 3 seconds.

### 13. Use Sensible Defaults: Hick's Law & Cognitive Offloading
*Smart, pre-configured defaults drastically reduce cognitive fatigue and decision paralysis.*
- Pre-select the safest, most common, or best-practice option by default.
- Leverage contextual data (time zone, currency, browser language, prior selections) to eliminate manual entry.
- Never use default selections that bind users to irreversible or unexpected financial/privacy commitments.
- Ensure every defaulted setting is effortlessly discoverable and editable.

### 14. Prevent Errors Proactively: Postel's Law (Robustness Principle)
*Be conservative in what you produce, and liberal in what you accept from others.*
- Accept forgiving inputs: format phone numbers, dates, credit cards, and postal codes flexibly without throwing strict validation errors.
- Clearly explain formatting requirements and validation rules upfront, before the user hits Submit.
- Proactively disable or visually explain unavailable actions rather than allowing a doomed click.
- Require explicit confirmation dialogs with clear consequences before executing irreversible or destructive actions.

### 15. Make Errors Recoverable: Postel's Law & Graceful Recovery
*Handle unexpected failures and user mistakes empathetically and constructively without creating roadblocks.*
- Never discard entered data when validation fails; preserve user input intact.
- Explain failures in human, jargon-free language: describe what happened, why, and how to resolve it.
- Highlight the exact field or step that requires attention and auto-focus or scroll to it.
- Offer instant recovery mechanisms: Undo toasts, Retry buttons, Restore Draft, or Back to Safety links.

### 16. Maintain Pattern Consistency: Law of Similarity
*Elements sharing visual characteristics (color, shape, typography) are perceived to share function.*
- Ensure components with identical functions share uniform visual appearance, hover states, and behaviors across the entire app.
- Standardize color semantics (e.g., green for positive/success, red for destructive/danger, blue/brand for interactive).
- Do not apply the same styling (e.g., blue background) to both non-interactive badges and clickable buttons.
- Reuse core design system tokens and established components before authoring ad-hoc styles.

### 17. Connect Related Elements Visually: Law of Uniform Connectedness
*Visual connections create the strongest perception of relationship between discrete elements.*
- Use subtle background cards, grouped containers, accent borders, or connecting lines to represent cohesive units.
- Visually link interactive triggers to the content drawers, popovers, or tables they govern.
- Keep disconnected concepts in visually distinct surfaces.
- Use visual connection intentionally to signal data binding or parent-child hierarchy, not for decoration.

### 18. Reduce Task Completion Time: Parkinson's Law
*Tasks expand to fill the perceived time and complexity allocated to them.*
- Minimize unnecessary steps: strip out superfluous confirmation gates and intermediary review screens.
- Auto-populate fields using existing account details or preceding steps.
- Offer power-user shortcuts (keyboard navigation, command palettes, bulk actions, 1-click clones).
- Optimize the happy path so users can achieve their goal in the fewest interactions possible.

### 19. Reveal Complexity Gradually: Tesler's Law (Conservation of Complexity)
*Every system has an inherent amount of complexity that cannot be eliminated—it can only be abstracted or distributed.*
- Present essential controls and core workflows upfront on clean surfaces.
- Disclose advanced configurations and edge cases progressively (via accordions, "Show Advanced Options", or modal sheets).
- Shift systemic complexity onto backend logic and automation rather than offloading it to the user.
- Shield users from database schemas, server endpoints, internal IDs, and lower-level plumbing.

### 20. Make Completion Feel Closer: Goal-Gradient Effect
*The closer users perceive themselves to be to their finish line, the faster and more eagerly they move toward it.*
- Emphasize progress already achieved early in the flow (e.g., "Step 1: Account Created - Complete!").
- Break long sequences into distinct, achievable milestones so the finish line is always in sight.
- Avoid 15-step endless wizards; frame workflows as 3 to 4 impactful milestones.
- Keep remaining milestones transparent, concrete, and visually immediate.

---

## Practical Implementation Workflow

When authoring or modifying any interface:

1. **Identify the Core Goal**: What single task did the user open this screen to accomplish?
2. **Shorten the Path**: What is the minimum number of clicks, inputs, and screens needed to achieve it?
3. **Establish Visual Dominance**: Is the next immediate action unmistakable?
4. **Prune Distractions**: Remove competing banners, redundant links, and visual clutter.
5. **Guarantee Immediate Feedback**: Does every interactive element react instantaneously (<400ms)?
6. **Eliminate Failure Modes**: Are inputs forgiving, rules explicit, and destructive actions guarded?
7. **Protect User Investment**: Is state saved automatically, and are errors easy to undo or fix?
8. **Celebrate Closure**: Does the flow finish with an explicit, satisfying confirmation of success?

---

## Conflict Resolution Matrix

When two design laws appear to compete in a specific scenario:
- **Hick's Law (Fewer choices) vs. Fitts's Law (Large targets)**: Prioritize Hick's Law first to eliminate clutter, then make the remaining essential options generously sized.
- **Jakob's Law (Familiarity) vs. Innovation**: Default to familiarity for navigation, authentication, and core mechanics. Reserve innovation for your product's unique value differentiator.
- **Tesler's Law (Hide complexity) vs. Power Users**: Use progressive disclosure (defaults on surface, toggles or hotkeys for power tools).

> **Golden Rule**: Always prioritize clarity, accessibility, user agency, and task completion. Do not apply laws mechanically—apply them with empathy for the user's immediate context.
