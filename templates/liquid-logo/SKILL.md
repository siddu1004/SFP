---
name: liquid-logo
description: Turn a logo or image into an animated liquid-metal effect with Liquid Logo, a WebGL fragment-shader tool, or reuse its shader in your own page. Use when the user wants an animated chrome or liquid metal logo, a flowing edge-following shader over an image, an exportable PNG or MP4 of it, or help adapting the Liquid Logo GLSL shader, presets or controls. Runs fully in the browser.
---

# Liquid Logo

[Liquid Logo](https://github.com/collidingScopes/liquid-logo) is a browser tool and a small WebGL project: a fragment shader detects the edges of a logo, builds a vector field around them, applies noise and flow, and renders a metallic sheen with a colour palette. Its README and the source that matters are bundled in `reference/`.

## Use the tool

It is a static site with no build step. Clone the repository, serve the folder with a local server (`python3 -m http.server`, then open `http://localhost:8000`), upload a logo, tune the controls, and export an image or an MP4. Everything is processed on the device, so the image is not uploaded. A clean, high-contrast image with simple edges works best. Shortcuts: Space pauses, R randomizes, S saves a screenshot, V records video.

## Reuse the effect in your own page

- `reference/fragment-shader.glsl` and `reference/vertex-shader.glsl` are the effect. `reference/shaders.js` shows how they are loaded.
- `reference/main.js` shows the WebGL setup: the texture from the image, the uniforms and the animation loop. `reference/presets.js` holds the named parameter sets, which are good starting values.
- Pass the logo as a texture and update the time uniform each frame, as `main.js` does. Keep the canvas size and the texture size in step to avoid stretching.

## Notes

- The shader started from XorDev's "Plasma" work, which the README credits. Keep that credit and the MIT licence when copying code.
- Heavy shaders cost GPU time on every frame. Pause the animation when the canvas is off screen, and offer a still image for visitors who prefer reduced motion.
- MP4 export uses a muxer library that is bundled in the project; the README describes it. For a plain logo animation in a page, a recorded video or a WebP is cheaper to serve than running the shader.
