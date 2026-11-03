---
name: penmentor
description: "Corrects handwritten math visually using a local model, enhancing learning through feedback and interactive animations. Use when checking handwritten math work visually with a local model."
---

> Written for SFP in its own words from the project at https://github.com/AbdullahAlhariri/penmentor (upstream license: MIT).

# Handwritten Math Correction with Local Model
## Use this skill when
- You need immediate feedback on your handwritten math problems.
- You want to learn calculus or other mathematical concepts interactively.
- You prefer visual aids like 3Blue1Brown-style animations for understanding.

## What it is
This skill allows an AI coding agent to analyze and correct handwritten math problems using a local model. It provides feedback, hints, and interactive animations to enhance learning, similar to having a teacher review your work.

## Steps
1. **Clone the Repository**: 
   ```sh
   git clone https://github.com/AbdullahAlhariri/penmentor ~/src/penmentor
   ```
2. **Run Self-Test**:
   ```sh
   ~/src/penmentor/bin/penmentor --selftest
   ```
3. **Configure Settings**: 
   - Open the settings to select your preferred AI agent (Claude, Codex, or Antigravity).
4. **Bind to a Key**: 
   - Bind `bin/penmentor` to a key using your window manager configuration (e.g., i3).

## Checks
- Ensure all dependencies (`rofi`, `slop`, `xdotool`, and PyQt6) are installed.
- Verify that the selected AI agent is logged in and accessible.

## Pitfalls
- **Dependency Issues**: Missing dependencies can prevent the tool from running. Ensure all prerequisites are met.
- **Configuration Errors**: Incorrect settings or key bindings may lead to functionality issues. Double-check configurations.
- **Performance**: Running local models and interactive animations can be resource-intensive. Ensure your system meets the requirements.
