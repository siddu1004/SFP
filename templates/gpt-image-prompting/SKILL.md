---
name: gpt-image-prompting
description: "Engineer detailed prompts and visual composition specifications for GPT-4o, DALL-E 3, and generative image models based on awesome-gpt-image-2 techniques. Use when creating UI mockups, icons, banners, and diagrams."
---

# GPT-4o & Generative Image Prompt Engineering

Visual composition and prompt engineering strategies for GPT-4o and advanced diffusion models. Synthesizes proven lighting, framing, aspect ratio, style tokens, and negative prompt controls to generate production-quality UI assets, icons, product photography, and architectural diagrams.

## Use this skill when
- Designing user-interface banners, splash screens, or application icons with AI image generators.
- Formulating precise visual composition prompts with camera angles, lighting styles, and color palettes.
- Creating technical diagrams, isometric concept art, or branded marketing assets.

## Steps
1. **Establish the visual style archetype**:
   Choose a deliberate aesthetic foundation:
   - *Technical/Architectural*: Isometric render, clean lines, neutral background, CAD-style shading.
   - *Modern Digital Product*: Flat bento grid, soft ambient occlusion, pastel UI accents, high legibility.
   - *Editorial/Cinematic*: Natural daylight, 35mm film grain, shallow depth of field, warm color grading.
2. **Compose the prompt structure**:
   Structure prompt tokens in hierarchy of importance:
   `[Subject + Core Action] + [Environment / Backdrop] + [Lighting & Atmosphere] + [Camera Lens & Angle] + [Color Palette & Texture]`
3. **Enforce technical quality parameters**:
   - Specify aspect ratio matching container constraints (`--ar 16:9`, `--ar 1:1`, `--ar 3:2`).
   - Specify rendering details: "octane render, subsurface scattering, minimal ray-traced shadows".
4. **Refine text rendering**:
   For images containing text, enclose exact phrases in double quotes ("Hello World") and instruct the generator to keep text centered, legible, and unembellished.
5. **Iterate with delta adjustments**:
   Adjust one attribute at a time (e.g. swap lighting from "direct spotlight" to "diffuse overcast") to converge on the desired visual.

## Checks
- Verify lighting direction is consistent across all elements in multi-object compositions.
- Ensure text labels in generated graphics are spelled correctly without hallucinated glyphs.
- Confirm aspect ratio matches target display dimensions.

## Pitfalls
- Avoid overloading prompt with contradictory buzzwords; specify concrete physical attributes instead.
- Avoid cluttered backgrounds when generating product UI assets or icons.

## Sources
- [Awesome GPT Image 2 Techniques](https://github.com/freestylefly/awesome-gpt-image-2)
