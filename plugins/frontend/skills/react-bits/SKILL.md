---
name: react-bits
description: "Curated collection of rich, animated React components, interactive text, dynamic backgrounds, audio synthesizers, and micro-interactions. Use when building eye-catching landing pages, creative interfaces, and engaging frontend experiences."
---

# React Bits

A comprehensive collection of animated, interactive React components designed to make modern web applications visually stunning and engaging.

## Component Categories

### 1. Interactive Text Effects
- **SplitText / BlurText**: Staggered letter-by-letter or word-by-word reveals using CSS transforms and spring physics.
- **TrueFocus**: Interactive focus rings and highlighted text states on hover.
- **DecryptedText**: Hacker/cyberpunk character scrambling and decryption reveals.
- **WaveText**: Sine-wave modulated typographic oscillations.

### 2. Creative Backgrounds & Canvases
- **Particles / Aurora**: GPU-accelerated WebGL shader backgrounds and particle clouds.
- **GridDistortion / Squares**: Interactive canvas grids responsive to cursor velocity.
- **Hyperspeed**: High-speed warp tunnel canvas animations for dynamic hero sections.

### 3. Micro-Interactions & UI Elements
- **Magnetic Buttons**: Elements that pull toward cursor position with spring damping.
- **TiltedCard**: 3D perspective tilt reacting to mouse position with specular highlight reflections.
- **InfiniteMenu**: Smooth circular or carousel menu navigation with inertial scrolling.

### 4. Integration Guidelines
- Combine with TailwindCSS or Vanilla CSS modules.
- Ensure all WebGL/Canvas effects unmount cleanly and cancel `requestAnimationFrame`.
- Guard effects with `prefers-reduced-motion` media queries for accessibility.
