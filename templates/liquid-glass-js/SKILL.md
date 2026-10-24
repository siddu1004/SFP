---
name: liquid-glass-js
description: Add Apple Liquid Glass-style buttons and containers to a web page with liquid-glass-js, a plain JavaScript and WebGL library with real-time refraction, blur and nested glass. Use when the user wants a glassmorphism or liquid glass button, pill, circle or panel with a refraction effect, a glass UI that samples the page behind it, or help tuning edge, rim, blur and tint of a glass effect. Not for a plain CSS backdrop-filter blur.
---

# liquid-glass-js

[liquid-glass-js](https://github.com/dashersw/liquid-glass-js) draws glass buttons and containers with WebGL shaders that refract and blur the page behind them. It has no build step and no npm package: the library is two source files, `container.js` and `button.js`, plus two small stylesheets. They are bundled in `reference/` with the project's README, so use them from there.

## Use it

1. Copy `reference/container.js`, `reference/button.js`, `reference/glass.css` and `reference/styles.css` into the user's project (keep `container.js` before `button.js`, since `Button` extends `Container`).
2. Load `html2canvas` before them. The library uses it to capture the page for the refraction.
3. Create glass with the classes, as `reference/readme.md` shows:

```javascript
const button = new Button({ text: 'Save', size: 28, type: 'pill', tintOpacity: 0.3, onClick: () => {} })
document.body.appendChild(button.element)

const container = new Container({ borderRadius: 24, type: 'pill' })
container.addChild(button)          // nested glass samples the parent
document.body.appendChild(container.element)
```

Shapes are `'rounded'`, `'circle'` and `'pill'`. The tuning parameters (edge, rim and base intensity, blur radius, tint) and their ranges are in the README's table.

## Things to check

- It needs WebGL 2 and a local server (WebGL and canvas capture do not work from a `file://` page): `npx serve .`.
- The glass shows whatever is behind it, so put it over an image or a gradient. On a flat colour there is nothing to refract.
- It samples the page with `html2canvas`, so cross-origin images need CORS headers or they will not appear in the effect.
- For a React app, create the instances in an effect after mount and add `button.element` to a ref, since the library works on DOM nodes.
- Read `reference/container.js` before changing behaviour: the shader and the uniforms are in it.
