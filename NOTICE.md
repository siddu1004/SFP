# Third-party notices

SFP collects skills written by other people. Each skill keeps the license of the project it came from, and each category folder holds copies of those licenses in `plugins/<category>/LICENSES/`.

| Source | License | Notes |
|---|---|---|
| [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | Apache-2.0 | https://github.com/pbakaus/impeccable |
| [Imaidazo/taste-skill-plugin](https://github.com/Imaidazo/taste-skill-plugin) | MIT | https://github.com/Imaidazo/taste-skill-plugin |
| [emilkowalski/skills](https://github.com/emilkowalski/skills) | MIT | https://github.com/emilkowalski/skills |
| [bergside/awesome-design-skills](https://github.com/bergside/awesome-design-skills) | MIT | |
| [usestrix/strix](https://github.com/usestrix/strix) | Apache-2.0 | |
| [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | Apache-2.0 | Anthropic |
| [Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach) | MIT | |
| [harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) | MIT | |
| [public-apis/public-apis](https://github.com/public-apis/public-apis) | MIT | https://github.com/public-apis/public-apis |
| [tashfeenahmed/freellmapi](https://github.com/tashfeenahmed/freellmapi) | MIT | https://github.com/tashfeenahmed/freellmapi |
| [web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines) | MIT | Vercel Labs |
| teach-me | MIT | https://github.com/ahmed3bead/teach-me |
| marketing-psychology | MIT | https://github.com/grayskripko/marketing-skills |
| design-skills | MIT | https://cuellarfr.github.io/design-skills/ (Carlos Cuellar) |
| task-observer, headroom | MIT | https://petrovicistefan.ro (Stefan Petrovici) |
| gia-chief-of-staff | MIT | https://aceexperts.org/gia (Advanced Consulting Experts, LLC) |
| cowork-plugin-management | Apache-2.0 | Anthropic |
| Anthropic example skills (algorithmic-art, brand-guidelines, canvas-design, internal-comms, mcp-builder, slack-gif-creator, theme-factory, web-artifacts-builder) | Apache-2.0 | Anthropic |
| [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code) | MIT | |
| [diegosouzapw/OmniRoute](https://github.com/diegosouzapw/OmniRoute) | MIT | |
| [career-ops-hq/career-ops](https://github.com/career-ops-hq/career-ops) | MIT | Installed from siddu1004's fork branch that keeps your data across plugin updates |
| [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem) | Apache-2.0 | |

`career` and `session-memory` are installed from their own repos and are not copied into SFP.

Plugins with no public source repo (the rows from teach-me down to the Anthropic example skills) are kept as snapshots in `vendor/`, each with its license file. Not included, because their licenses do not allow republishing: Greenhouse's plugin (customer use only), Anthropic's docx, pdf, pptx, xlsx and browser skills (all rights reserved), and claude-mem-cowork (noncommercial only).

The tooling in `scripts/`, the router skill in `templates/sfp/` and the `public-apis` skill wrapper in `templates/public-apis/` were written for SFP.
