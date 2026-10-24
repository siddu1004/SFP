---
name: shadergradient
description: Add an animated 3D shader gradient background to a React, Next.js, Vue or Nuxt site with ShaderGradient (@shadergradient/react, @shadergradient/vue). Use when the user wants a moving gradient, an animated plane, sphere or water-plane backdrop, a gradient configured from a shadergradient.co URL, or help with its props such as color1, uSpeed, cDistance and grain. Also for Figma and Framer gradient components.
---

# ShaderGradient

[ShaderGradient](https://github.com/ruucm/shadergradient) renders a customizable moving 3D gradient with three.js. The README and the Vue guide are bundled in `reference/`: `reference/readme.md` has install, usage and the full prop list, and `reference/vue.md` covers Vue 3 and Nuxt.

## React

```bash
npm i @shadergradient/react @react-three/fiber three three-stdlib camera-controls
npm i -D @types/three
```

```tsx
import { ShaderGradientCanvas, ShaderGradient } from '@shadergradient/react'

<ShaderGradientCanvas style={{ position: 'absolute', inset: 0 }} pixelDensity={1.5} fov={45}>
  <ShaderGradient cDistance={32} cPolarAngle={125} />
</ShaderGradientCanvas>
```

To reuse a design made at shadergradient.co/customize, pass the copied address as `urlString` with `control='query'`.

## Check before you write code

- **Versions.** The right `@react-three/fiber` depends on the app: Next.js 15 App Router needs React 19 with R3F 9, while Next 14, Next 15 Pages and Vite work with matching 8.x or 9.x. The compatibility table is in `reference/readme.md`.
- **Next.js.** The gradient is a client-side canvas; put it in a client component and give it a fallback if the page renders on the server.
- **Packages.** `@shadergradient/react` ships only the renderer. It has no store or controls: drive it with props, state of your own or the query string. `@shadergradient/ui` is not on npm.
- **Props.** `type` is `plane`, `sphere` or `waterPlane`. The colours are `color1`, `color2`, `color3`. Motion is `animate`, `uSpeed`, `uStrength`, `uDensity`, `uFrequency`, `uAmplitude`. The camera is `cAzimuthAngle`, `cPolarAngle`, `cDistance`, `cameraZoom`. The full list is in the README.
- **Cost.** A full-screen WebGL canvas uses the GPU all the time. Lower `pixelDensity`, turn `animate` off when it does not need to move, and use the canvas's lazy-load options for a gradient below the fold.
- **Reduced motion.** Turn animation off for visitors who ask for it with `prefers-reduced-motion`.
