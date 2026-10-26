# Accessibility Statement for SFP (Skills for Productivity)

We are committed to ensuring digital accessibility for all users, contributors, and developers, regardless of ability or technology used. We believe developer tools, agent interfaces, and command-line workflows should be accessible and inclusive to everyone.

---

## Scope & Measures

This statement applies to the **SFP** project, including:
- Command-line interfaces, scripts, and MCP server outputs.
- Documentation and markdown guides.
- The Antigravity / VS Code extension (`extensions/antigravity-hive`).

To uphold accessibility standards, we strive to:
- **Semantic Structure**: Maintain clean, structured markdown documentation using proper semantic headings, tables with header associations, descriptive link text, and alternative text for visual diagrams and assets.
- **Readable CLI Outputs**: Provide clear, high-contrast, uncluttered terminal output that works cleanly with screen readers, braille displays, and custom terminal color palettes. Avoid conveying information through color alone.
- **Editor Extension Accessibility**: Design webview interfaces and UI components in `extensions/antigravity-hive` conforming to WCAG 2.1 Level AA standards, ensuring full keyboard navigability, appropriate ARIA attributes, system high-contrast theme support, and scalable typography.
- **Machine & Agent Readability**: Ensure structured data outputs (JSON, JSON-RPC responses) are consistent, well-formed, and easily parsed by assistive automation tools.

---

## Known Limitations

While we strive for comprehensive accessibility, some areas may have limitations:
- **Mermaid & ASCII Architecture Diagrams**: Some historical architectural documentation contains complex diagrams that may be challenging for screen reader software to interpret sequentially. We are continuously adding prose summaries alongside complex diagrams.
- **Third-party Skills**: Skills aggregated from upstream third-party sources may vary in formatting and documentation accessibility.

---

## Feedback & Reporting Barriers

We welcome your feedback on the accessibility of SFP. If you encounter accessibility barriers, cannot access certain features, or have suggestions for improvements:

1. **Open an Issue**: File an issue using our [Bug Report Template](.github/ISSUE_TEMPLATE/bug_report.md) with the label `accessibility`.
2. **Contact Maintainers**: Reach out via GitHub issues or discussions on the [SFP repository](https://github.com/siddu1004/SFP).

Please include:
- A description of the barrier or inaccessible component.
- The assistive technology, operating system, and terminal/editor used.
- Suggestions or preferred formats where applicable.

We aim to acknowledge and address accessibility concerns promptly.
