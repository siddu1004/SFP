---
name: gsap
description: "Build high-performance web animations with GSAP (GreenSock Animation Platform) — tweens, timelines, ScrollTrigger, Flip, MorphSVG, SplitText, and physics. Use when implementing fluid transitions, scroll animations, SVG effects, or complex interactive motion."
---

# GSAP (GreenSock Animation Platform)

High-performance, battle-tested JavaScript animation library for modern web applications.

## Core Concepts

### 1. Basic Tweens
```javascript
import gsap from 'gsap';

// Move to target state
gsap.to('.card', {
  x: 100,
  opacity: 1,
  duration: 0.8,
  ease: 'power2.out'
});

// Animate from initial state
gsap.from('.hero-title', {
  y: 50,
  opacity: 0,
  duration: 1,
  ease: 'back.out(1.7)'
});
```

### 2. Timelines (Choreographed Sequences)
Avoid `setTimeout` or nested callbacks. Use Timelines for sequenced animations:
```javascript
const tl = gsap.timeline({ defaults: { ease: 'power3.out', duration: 0.6 } });

tl.from('.badge', { scale: 0, opacity: 0 })
  .from('.heading', { y: 30, opacity: 0 }, '-=0.3')
  .from('.description', { y: 20, opacity: 0 }, '-=0.2')
  .from('.cta-button', { scale: 0.9, opacity: 0 }, '-=0.2');
```

### 3. ScrollTrigger
```javascript
import { ScrollTrigger } from 'gsap/ScrollTrigger';
gsap.registerPlugin(ScrollTrigger);

gsap.to('.parallax-layer', {
  yPercent: -50,
  ease: 'none',
  scrollTrigger: {
    trigger: '.section',
    start: 'top bottom',
    end: 'bottom top',
    scrub: true
  }
});
```

### 4. Hardware Acceleration & Best Practices
- Animate `transform` (`x`, `y`, `scale`, `rotation`) and `opacity` rather than `top`, `left`, `width`, or `height`.
- Use `gsap.context()` in React (`useLayoutEffect` or `useEffect`) to ensure clean teardown and prevent memory leaks.
- Leverage `ScrollTrigger.refresh()` after dynamic DOM or image loads.
