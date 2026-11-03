---
name: apple-design-review
description: "Review UIs against Apple Human Interface Guidelines for Flutter, React Native, and other frameworks, ensuring accessibility, platform conventions, and design craft. Use when reviewing a UI for clarity, deference, depth and platform conventions in any framework."
---

> Written for SFP in its own words from the project at https://github.com/dickwu/apple-design-skill (upstream license: none).

# Apple Design Skill

## Use this skill when
- You need to audit or improve a mobile or desktop app's UI.
- You want to ensure your app adheres to Apple's Human Interface Guidelines.
- You're working with Flutter, React Native, Tauri, Electron, SwiftUI, UIKit, or AppKit.

## What it is
This AI skill reviews user interfaces against Apple's Human Interface Guidelines (HIG) for various frameworks. It checks accessibility, platform conventions, visual design, interaction, and content writing. The skill also supports specialized modes for app icons, accessibility audits, dark mode, Liquid Glass, iPhone Duo layouts, Apple Pay, code audits, onboarding flows, permissions, forms, generative AI, widgets, and Live Activities.

## Steps
1. **Install the Skill**: Use the skills CLI to install the skill for your preferred agent or clone the repository manually.
   ```bash
   npx skills add dickwu/apple-design-skill
   ```
2. **Trigger a Review**: Ask your agent to review your UI against Apple's HIG, specifying the framework and any additional details like accessibility or iPhone Duo support.
3. **Review the Report**: The skill will generate a detailed report with findings, explanations, and fixes tailored to your framework.

## Checks
- Ensure all guidelines are up-to-date by running the `pull-hig.mjs` script if necessary.
- Verify that the skill is correctly installed and configured for your agent.
- Confirm that the review covers all relevant aspects of Apple's HIG, including accessibility, platform conventions, visual design, interaction, and content writing.

## Pitfalls
- Make sure to specify the correct framework when triggering a review to ensure accurate translations and fixes.
- Be aware that some specialized modes may require additional configuration or specific code patterns.
- Regularly update the guidelines to incorporate any changes made by Apple.
