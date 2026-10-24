---
name: react-three-fiber
description: Build 3D scenes in React with React Three Fiber (@react-three/fiber), the React renderer for three.js. Use when the user wants 3D in a React or Next.js app, a Canvas with meshes, lights and cameras, animation with useFrame, loading models or textures, pointer events on 3D objects, on-demand rendering and performance work, a v8 to v9 migration, or to fix a React Three Fiber problem such as setState in a render loop or a Next.js server-component error.
---

# React Three Fiber

[React Three Fiber](https://github.com/pmndrs/react-three-fiber) (R3F) renders three.js with React: three.js objects are written as JSX, and hooks give access to the render loop and the scene. The project's own docs are bundled in `reference/`. Read the file that matches the task instead of all of them.

| Task | Read |
|---|---|
| What it is, a first scene | `reference/introduction.md` |
| Install for Vite, Next.js, React Native or a CDN | `reference/installation.md` |
| `Canvas` props: `frameloop`, `dpr`, `shadows`, `camera`, `gl` | `reference/canvas.md` |
| `useFrame`, `useThree`, `useLoader`, `useGraph` | `reference/hooks.md` |
| JSX objects, constructor `args`, `attach`, props, `dispose` | `reference/objects.md` |
| Pointer events, `onClick`, `onPointerOver`, event propagation | `reference/events.md` |
| Animation with `useFrame` and springs | `reference/basic-animations.md` |
| Loading glTF models and textures | `reference/loading-models.md`, `reference/loading-textures.md` |
| Why it is fast, how objects map to JSX | `reference/how-it-works.md` |
| Common mistakes | `reference/pitfalls.md` |
| Frame rate, instancing, on-demand rendering, level of detail | `reference/scaling-performance.md` |
| TypeScript types and JSX typing | `reference/typescript.md` |
| Upgrading from v8 | `reference/v9-migration-guide.md` |
| Testing | `reference/testing.md` |

## The rules that prevent most problems

These come from the bundled docs; the details and examples are in `reference/pitfalls.md` and `reference/scaling-performance.md`.

- **Install** `three` and `@react-three/fiber`. R3F must pair with the matching major version of React, like react-dom does: check the version note in `reference/installation.md` before choosing versions.
- **Do not call `setState` in `useFrame`** or in fast events. Mutate refs and use the frame `delta` instead, so the animation does not depend on the frame rate.
- **Do not create objects in a loop.** Allocate vectors, colours and materials once and reuse them.
- **Load assets with `useLoader`**, which caches and suspends, rather than calling a loader in render.
- **Reuse geometries and materials**, and use instancing for many copies of the same mesh.
- **Render on demand** (`frameloop="demand"`) when nothing animates all the time, and call `invalidate()` to draw a frame.
- **Mount with care.** Toggling `visible` is cheaper than mounting and unmounting a heavy component.
- **In Next.js**, add `three` to `transpilePackages` in `next.config.js` (see `reference/installation.md`). R3F components use hooks and browser APIs, so keep them in a client component (`"use client"`).

## Working method

1. Read the file for the task above before writing code, and use the API shown there. R3F changes between major versions.
2. Start from the smallest `Canvas` that works, check it renders, then add objects, lights and motion.
3. For performance problems, measure first (the performance monitoring section in `reference/scaling-performance.md`), then apply the matching technique.
