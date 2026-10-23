---
name: framer-motion
description: "Production-ready motion library for React. Use for declaratively animating layout transitions, gestures (drag, hover, tap), enter/exit animations with AnimatePresence, scroll-linked animations, and physics-based spring motions."
---

# Framer Motion (Motion for React)

Declarative, gesture-driven motion library for React and Next.js applications.

## Core Patterns

### 1. Basic Component Animation
```tsx
import { motion } from 'framer-motion';

export function Card() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      className="card"
    >
      Content
    </motion.div>
  );
}
```

### 2. Enter / Exit Transitions with AnimatePresence
```tsx
import { AnimatePresence, motion } from 'framer-motion';

export function NotificationList({ items }) {
  return (
    <AnimatePresence>
      {items.map((item) => (
        <motion.div
          key={item.id}
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        >
          {item.message}
        </motion.div>
      ))}
    </AnimatePresence>
  );
}
```

### 3. Layout Animations (`layout` prop)
Automatic smooth FLIP animation when layout changes occur:
```tsx
<motion.div layout className="accordion-content">
  {expanded && <Details />}
</motion.div>
```

### 4. Gestures and Drag
```tsx
<motion.div
  drag
  dragConstraints={{ left: -100, right: 100, top: -100, bottom: 100 }}
  dragElastic={0.2}
  whileDrag={{ scale: 1.1, cursor: 'grabbing' }}
/>
```
