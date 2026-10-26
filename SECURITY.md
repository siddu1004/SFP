# Security Policy

## Supported Versions

Security updates and bug fixes are actively provided for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| `main`  | :white_check_mark: |
| < 1.0   | :x:                |

We recommend always running against the latest commits on the `main` branch or the latest released package.

---

## Reporting a Vulnerability

We take the security of SFP and user environments seriously. If you discover a security vulnerability or sensitive issue in SFP, please do not report it through a public GitHub issue.

Instead, please report vulnerabilities via one of the following methods:

1. **GitHub Security Advisory (Preferred)**:
   Navigate to the [Security Advisories](https://github.com/siddu1004/SFP/security/advisories) page of this repository and click **"Report a vulnerability"**.

2. **Direct Contact**:
   Contact the maintainer directly via GitHub profile [siddu1004](https://github.com/siddu1004) or associated security contact channels.

### Information to Include in Your Report
To help us investigate and resolve the issue quickly, please include:
- A clear description of the vulnerability and its potential impact.
- Step-by-step instructions or proof-of-concept to reproduce the behavior.
- Affected components (e.g., MCP server, Hive engine, CLI scripts, local model router, or extensions).
- Any relevant logs, environment details, or remediation suggestions.

### Our Commitment
- We will acknowledge receipt of your vulnerability report within 48 hours.
- We will provide an assessment of the vulnerability and an estimated timeline for remediation.
- We will keep you informed of our progress as we work on a fix.
- We will credit you in the release notes upon patch publication (unless you prefer anonymity).

---

## Security Best Practices in SFP

- **API Keys & Secrets**: SFP's local model router and tools resolve keys strictly from environment variables. SFP never persists sensitive credentials or tokens in files or databases.
- **MCP Server Isolation**: The SFP MCP server uses Python standard library modules over `stdio` without external arbitrary network dependencies.
- **Skill Sources**: Only skills from verified, public repositories are indexed. Do not integrate private or untrusted repositories into `sources.json`.
