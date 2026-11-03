---
name: locomotive-scroll
description: "Implement smooth scrolling, parallax effects, and scroll-triggered animations using Locomotive Scroll. Use when adding smooth inertia scrolling, scroll-bound transforms, sticky containers, or scroll-reveal effects in web interfaces."
---

# Locomotive Scroll

Smooth scrolling and scroll-driven animation library (`locomotivemtl/locomotive-scroll`). Enables inertia scrolling, viewport detection, speed-differentiated parallax, and directional scroll events.

## Use This Skill When

- Adding smooth momentum scrolling to landing pages and editorial websites.
- Implementing parallax transforms driven by viewport scroll progress (`data-scroll-speed`).
- Triggering CSS classes or callbacks as elements enter or leave the viewport.

## Installation & Setup

```bash
npm install locomotive-scroll
```

```javascript
import LocomotiveScroll from 'locomotive-scroll';

const scroll = new LocomotiveScroll({
  el: document.querySelector('[data-scroll-container]'),
  smooth: true,
  multiplier: 1.0,
});
```

## HTML Markup Attributes

```html
<main data-scroll-container>
  <!-- Element moving faster than scroll rate -->
  <section data-scroll-section>
    <h1 data-scroll data-scroll-speed="2">Fast Header</h1>
    <p data-scroll data-scroll-speed="-1">Slow Floating Text</p>
  </section>

  <!-- Element triggering on-screen class -->
  <div data-scroll data-scroll-class="is-revealed" data-scroll-repeat="true">
    Revealed Block
  </div>
</main>
```

## Accessibility & Performance Checks

- [ ] Disable smooth scroll under `@media (prefers-reduced-motion: reduce)`.
- [ ] Call `scroll.update()` after asynchronous image loads or dynamic DOM mutations to recalculate scroll heights.
- [ ] Ensure native keyboard scrolling (`Space`, `PageDown`, arrow keys) remains functional.

## Sources

- [Locomotive Scroll GitHub Repository](https://github.com/locomotivemtl/locomotive-scroll)
