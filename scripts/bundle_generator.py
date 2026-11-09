"""Full bundle partitioner for all unbundled skills in SFP."""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'mcp'))
import sfp_library as lib

def get_bundle_definitions():
    # Explicit mapping of bundle definitions
    # Each definition: (id, name, purpose, goal, when, [skills])
    return [
        # SFP meta
        ("sfp-hive-core", "SFP Hive Core", "extend",
         "Route, select, and adaptively rank skills for any IDE or workflow.",
         "Setting up or extending SFP hive routing and adaptive skill selection.",
         ["sfp", "sfp-hive"]),

        # Career
        ("career-acceleration", "Career Acceleration", "business",
         "Map career goals, extract target skills, and automate resume growth.",
         "Auditing career progression, scraping job openings, or upskilling for target roles.",
         ["career-ops", "scrape", "upskill"]),

        # Data APIs
        ("data-intel-search", "Data Intelligence and OSINT", "research",
         "Gather open-source intelligence, neural web search, and social graph data.",
         "Scraping web data, performing OSINT investigations, or querying social APIs.",
         ["data-scraper-agent", "exa-search", "osint-investigation", "agent-reach", "x-api"]),

        # Languages
        ("systems-programming", "Systems Programming Standards", "build",
         "Idiomatic systems programming patterns and core coding standards for compiled languages.",
         "Writing modern, memory-safe C++, Rust, and Java systems code.",
         ["cpp-coding-standards", "rust-patterns", "java-coding-standards", "kotlin-patterns"]),
        ("scripting-and-packaging", "Scripting and Packaging", "build",
         "Production-ready Python, Perl idioms, and self-contained installer generation.",
         "Packaging Python installers or writing robust automation scripts in Python and Perl.",
         ["python-patterns", "perl-patterns", "generating-python-installer"]),

        # Web3
        ("smart-contracts-evm", "Smart Contracts and EVM", "build",
         "Build, verify, and handle cryptographic math for Ethereum and EVM contracts.",
         "Working with EVM token decimals, Keccak256 hashes, and smart contract architecture.",
         ["evm-token-decimals", "nodejs-keccak256", "agent-payment-x402"]),
        ("web3-prediction-markets", "Web3 Prediction Markets and Oracles", "research",
         "Analyze prediction market mechanics, risk models, and decentralized oracle data.",
         "Designing or auditing prediction market contracts and liquidity mechanics.",
         ["prediction-market-oracle-research", "prediction-market-risk-review", "ito-baskets", "ito-compute", "ito-inference", "ito-training"]),

        # Networking
        ("homelab-infrastructure", "Homelab Infrastructure and VPN", "build",
         "Configure homelab DNS filtering, network readiness, VLANs, and WireGuard VPNs.",
         "Setting up private home lab routing, DNS protection with Pi-hole, and secure WireGuard tunnels.",
         ["homelab-network-readiness", "homelab-network-setup", "homelab-pihole-dns", "homelab-vlan-segmentation", "homelab-wireguard-vpn"]),
        ("enterprise-network-automation", "Enterprise Network Automation", "build",
         "Automate Cisco IOS device configuration, BGP diagnostics, and interface health checks.",
         "Validating enterprise switch configs, diagnosing BGP routing, and driving Netmiko SSH sessions.",
         ["cisco-ios-patterns", "netmiko-ssh-automation", "network-bgp-diagnostics", "network-config-validation", "network-interface-health"]),

        # Mobile
        ("ios-swift-mastery", "iOS and Swift Mastery", "build",
         "Architect modern Swift applications with Swift Concurrency, Actor persistence, and SwiftUI.",
         "Building native iOS and macOS apps using modern Swift 6 features and SwiftUI patterns.",
         ["write-swift", "swiftui-patterns", "swift-concurrency-6-2", "swift-actor-persistence", "swift-protocol-di-testing", "ios-icon-gen"]),
        ("cross-platform-mobile", "Cross-Platform Mobile and Android", "build",
         "Architect multiplatform mobile experiences with Compose, React Native, and on-device models.",
         "Building cross-platform apps with Android clean architecture, Compose, or React Native.",
         ["android-clean-architecture", "compose-multiplatform-patterns", "react-native-patterns", "kotlin-coroutines-flows", "foundation-models-on-device"]),

        # AI/ML
        ("mle-production-pipeline", "Production ML Engineering", "build",
         "Design end-to-end reproducible machine learning workflows, evaluation, and serving.",
         "Deploying ML pipelines, training PyTorch architectures, or designing recommendation systems.",
         ["mle-workflow", "ml-adoption-playbook", "pytorch-patterns", "recsys-pipeline-architect"]),
        ("prompt-engineering-optimization", "Prompt Engineering and Cost Optimization", "speed",
         "Optimize prompt token budgets, caching strategies, and structured LLM parsing.",
         "Lowering token costs, optimizing system prompts, or caching prompt prefixes.",
         ["prompt-optimizer", "prompt-master", "cost-aware-llm-pipeline", "prompt-caching-strategy", "regex-vs-llm-structured-text"]),
        ("multimodal-and-nlp", "Multimodal AI and Specialized NLP", "create",
         "Generate media with Fal AI, process low-resource Indic languages, and leverage local LLMs.",
         "Building multimodal generation pipelines or tokenizing complex linguistic scripts.",
         ["fal-ai-media", "bengali-nlp", "colibri"]),

        # Industry
        ("healthcare-compliance-cdss", "Healthcare Systems and HIPAA Compliance", "secure",
         "Build HIPAA-compliant healthcare applications, clinical decision support, and EMR integrations.",
         "Developing digital health systems, handling protected health information, and auditing EHR interfaces.",
         ["hipaa-compliance", "healthcare-phi-compliance", "healthcare-cdss-patterns", "healthcare-emr-patterns", "healthcare-eval-harness"]),
        ("supply-chain-logistics", "Supply Chain and Trade Logistics", "business",
         "Optimize inventory demand, carrier relationships, customs trade compliance, and reverse logistics.",
         "Planning manufacturing scheduling, tracking customs compliance, or handling logistics exceptions.",
         ["supply-chain-and-logistics", "logistics-exception-management", "customs-trade-compliance", "carrier-relationship-management", "inventory-demand-planning", "production-scheduling", "quality-nonconformance", "returns-reverse-logistics", "energy-procurement"]),

        # Devops
        ("git-ops-and-pr-automation", "GitOps and PR Automation", "deploy",
         "Automate PR reviews, merge batch queues, green gate validation, and branch maintenance.",
         "Merging PR queues in batches, enforcing green test gates, or cleaning stale Git branches.",
         ["github-ops", "green-prs", "merge-batch", "merge-prs", "quality-scan", "sweep-reds", "validate-release-green"]),
        ("cloud-containers-uncloud", "Cloud Container Operations", "deploy",
         "Deploy multi-node services across Kubernetes, Uncloud clusters, and declarative Nix environments.",
         "Running Kubernetes manifests, managing Uncloud micro-clusters, or spinning up Flox sandboxes.",
         ["kubernetes-patterns", "uncloud", "flox-environments", "terminal-opener", "terminal-ops"]),

        # Backend
        ("enterprise-java-dotnet", "Enterprise Java and .NET Backends", "build",
         "Architect enterprise transactional backends with Spring Boot, JPA, Quarkus, and .NET.",
         "Building robust microservices in Spring Boot, Quarkus, or .NET Core.",
         ["springboot-patterns", "jpa-patterns", "quarkus-patterns", "dotnet-patterns", "mybatis-patterns"]),
        ("modern-typed-backends", "Modern Typed and Async Backends", "build",
         "Build high-throughput APIs using NestJS, Kotlin Ktor, Bun runtime, and Tinystruct.",
         "Developing TypeScript or Kotlin APIs with fast runtimes and modular architecture.",
         ["nestjs-patterns", "kotlin-ktor-patterns", "kotlin-exposed-patterns", "bun-runtime", "tinystruct-patterns", "contract-first"]),
        ("python-ruby-frameworks", "Full-Stack Web Frameworks", "build",
         "Deliver database-backed web applications with Laravel, Ruby on Rails, and Django Celery.",
         "Writing full-stack apps with Rails conventions, Laravel plugins, or asynchronous Celery queues.",
         ["rails-patterns", "laravel-patterns", "laravel-plugin-discovery", "django-celery", "backend-patterns"]),
        ("high-performance-datastores", "High-Performance Analytical Datastores", "build",
         "Scale analytical and transactional storage with ClickHouse, MySQL, Redis, and Prisma ORM.",
         "Optimizing ClickHouse queries, tuning MySQL indexes, caching in Redis, or writing Prisma migrations.",
         ["clickhouse-io", "mysql-patterns", "redis-patterns", "prisma-patterns"]),

        # Security
        ("penetration-testing-strix", "Automated Penetration Testing and Strix", "secure",
         "Scan and remediate vulnerabilities automatically using Strix AI pentesting agents.",
         "Running automated dynamic application security testing or fixing web exploits with Strix.",
         ["web-app-penetration-testing", "api-security-testing", "managed-pentesting-with-strix", "ci-security-scanning-with-strix", "fix-security-vulnerabilities-with-strix", "security-bounty-hunter"]),
        ("cloud-container-hardening", "Cloud and Container Hardening", "secure",
         "Harden Docker containers, audit AWS S3 bucket permissions, and enforce CIS cloud benchmarks.",
         "Securing container images, auditing AWS IAM and S3 permissions, or detecting container breakout.",
         ["hardening-docker-containers-for-production", 'detecting-container-escape-attempts', 'auditing-aws-s3-bucket-permissions', 'auditing-cloud-with-cis-benchmarks', 'analyzing-cloud-storage-access-patterns', 'analyzing-api-gateway-access-logs']),
        ("app-and-agent-security", "Application and Agent Security Hardening", "secure",
         "Harden LLM agents, verify framework-specific defense, and enforce Zero Trust access.",
         "Securing autonomous agents, auditing Spring/Laravel endpoints, or implementing Zero Trust.",
         ["claude-security", "agent-security-hardening", "implementing-zero-trust-network-access", "achieving-cmmc-level-2-compliance", "security-audit", "reverse-engineer-anything", "defi-amm-security", "llm-trading-agent-security", "laravel-security", "springboot-security", "quarkus-security", "perl-security"]),

        # Engineering
        ("codebase-knowledge-graph", "Codebase Knowledge Graphs and AST", "research",
         "Trace symbol references, structural AST diffs, and codebase architecture graphs.",
         "Navigating large foreign repositories, tracing AST callgraphs, or structural diffing.",
         ["gitnexus", "trail-code", "difftastic", "floorplan", "build-your-own-x"]),
        ("system-performance-optimization", "System Performance and Reliability", "speed",
         "Optimize cache architectures, throughput bottlenecks, and latency-critical services.",
         "Benchmarking hot loops, eliminating cache stampedes, or profiling high-frequency services.",
         ["latency-critical-systems", "data-throughput-accelerator", "content-hash-cache-pattern", "benchmark-optimization-loop", "benchmark-methodology"]),
        ("software-craftsmanship", "Software Craftsmanship and Standards", "review",
         "Enforce architectural boundaries, error recovery, and Karpathy coding discipline.",
         "Applying hexagonal architecture, standardizing error handling, or performing production audits.",
         ["hexagonal-architecture", "error-handling", "coding-standards", "karpathy-guidelines", "production-audit", "change-impact", "ecc-conventions", "ponytail", "unlazy"]),
        ("investigation-tool-design", "Investigation Tool Design and Changelogs", "extend",
         "Design REA investigation tools, optimize provider evidence schemas, and automate changelog sync.",
         "Building REA evidence collectors or generating release changelogs.",
         ["rea-tool-design", "rea-analysis-optimization", "rea-changelog-update"]),

        # Testing & Quality
        ("polyglot-compiled-testing", "Compiled Languages TDD Suite", "test",
         "Test-driven assertions and verification fixtures across C++, C#, F#, Rust, and Kotlin.",
         "Developing compiled language assertions in GoogleTest, xUnit, FsUnit, or cargo test.",
         ["cpp-testing", "csharp-testing", "fsharp-testing", "rust-testing", "kotlin-testing", "perl-testing"]),
        ("framework-verification-tdd", "Framework Verification and TDD", "test",
         "Drive test-driven development for Laravel, Spring Boot, Quarkus, and Django apps.",
         "Writing HTTP integration tests, mock repositories, or automated framework test runs.",
         ["laravel-tdd", "laravel-verification", "springboot-tdd", "springboot-verification", "quarkus-tdd", "quarkus-verification", "django-verification"]),
        ("quality-gates-and-e2e", "Quality Gates and E2E Automation", "test",
         "Run end-to-end browser automation, desktop UI tests, mutation checks, and commit reviews.",
         "Automating Playwright test scripts, testing Windows desktop apps, or enforcing delivery gates.",
         ["playwright-cli", "windows-desktop-e2e", "delivery-gate", "eval-harness", "gateguard", "safety-guard", "ai-regression-testing", "module-regression", "conventional-commit-review", "plankton-code-quality", "test-collaboration", "gsd-code-review", "rea-ci-tests-audit"]),

        # Memory
        ("claude-mem-agent-engine", "Claude-Mem Agent Engine", "agents",
         "Instrument persistent cross-session memory with local workers and observation indexing.",
         "Installing and tuning claude-mem observers, session timelines, and memory injection.",
         ["claude-mem-install", "mem-how-it-works", "mem-host-observer", "mem-cloud-sync", "mem-design-is", "mem-knowledge-agent", "mem-pathfinder", "mem-openclaw"]),
        ("mem-workflow-orchestration", "Memory-Driven Workflow Orchestration", "agents",
         "Execute autonomous build-and-release plans driven by persistent memory observations.",
         "Automating multi-step plans with make-plan, mem-do, and PR babysitting.",
         ["mem-make-plan", "mem-do", "mem-build", "mem-build-and-release", "mem-babysit", "mem-standup", "mem-ccs-align", "mem-childhood", "mem-handoff", "mem-oh-my-issues", "mem-version-bump", "mem-agent-cost-report", "mem-timeline-report", "mem-weekly-digests", "mem-what-the", "mem-wowerpoint", "mem-mode-creator"]),
        ("multimodal-desktop-memory", "Desktop and Multimodal Agent Memory", "agents",
         "Record, recall, and search screen history, OCR text, and long-term agent memory stores.",
         "Recalling past screen activity via Screenpipe or querying OpenViking persistent stores.",
         ["mem-screenpipe", "openviking", "agentmemory"]),

        # Content & Media
        ("video-content-generation", "Programmatic Video Generation", "create",
         "Generate automated videos with Manim math animations, Remotion React canvas, and AI speech.",
         "Creating algorithmic video explanations, Remotion reels, or automated TikTok videos.",
         ["manim-video", "remotion-video-creation", "moneyprinterturbo-video", "tasteforge-video", "video-editing", "videodb", "openmontage", "lemo-opuscar"]),
        ("brand-identity-craft", "Brand Identity and Creative Design", "create",
         "Design brand guidelines, art direction, presentation slides, and marketing assets.",
         "Defining visual brand guidelines, designing marketing canvas assets, or generating GIFs.",
         ["brand-discovery", "brand-guidelines", "canvas-design", "frontend-slides", "project-artifact", "slack-gif-creator", "algorithmic-art", "huashu-art-motion", "gpt-image-prompting"]),
        ("persuasion-and-growth-copy", "Persuasion, Copywriting and Growth", "create",
         "Audit psychological conversion mechanics, write punchy prose, and automate social feeds.",
         "Polishing editorial prose with Hemingway clarity, auditing dark patterns, or scheduling crossposts.",
         ["persuasion-audit", "price-framing", "behavior-diagnosis", "dark-pattern-check", "evidence-check", "marketing-campaign", "social-publisher", "crosspost", "ui-demo", "humanizer", "asd-ste100", "sepia", "sepia-hemingway", "sepia-recreate", "sepia-refactor", "sepia-review", "sepia-write"]),

        # Research & Docs
        ("knowledge-management-obsidian", "Knowledge Graphs and Obsidian", "document",
         "Organize markdown vaults, interactive JSON canvases, and persistent personal knowledge bases.",
         "Connecting notes in Obsidian, building JSON knowledge graphs, or exporting research vaults.",
         ["obsidian-markdown", "obsidian-cli", "obsidian-bases", "json-canvas", "knap", "defuddle", "notebooklm"]),
        ("deep-codebase-understanding", "Codebase Diagnostics and Living Docs", "research",
         "Interactively explain unfamiliar architectures, Figma design mappings, and codebase diffs.",
         "Running interactive understand sessions, generating living documentation, or exploring domain logic.",
         ["understand", "understand-chat", "understand-dashboard", "understand-diff", "understand-domain", "understand-explain", "understand-figma", "understand-knowledge", "understand-onboard", "living-docs-governance", "knowledge-ops", "brownfield-retrospective", "codebase-memory-mcp"]),
        ("scientific-literature-deep-search", "Scientific Literature and Deep Search", "research",
         "Query PubMed, USPTO patents, scientific genomics packages, and private SearXNG nodes.",
         "Executing structured scholarly reviews, fetching genomic records, or parsing patent claims.",
         ["scientific-thinking-literature-review", "scientific-thinking-scholar-evaluation", "scientific-db-pubmed-database", "scientific-db-uspto-database", "scientific-pkg-gget", "research-ops", "searxng", "nutrient-document-processing", "story-lifecycle", "rederive", "graphify", "teach-me", "vibewise-learn", "vibewise-reset"]),

        # AI Gateway & OmniRoute
        ("omniroute-cli-suite-1", "OmniRoute CLI Operations: Core", "extend",
         "Manage OmniRoute AI proxy server, chat REPL, models, provider keys, and streaming.",
         "Configuring OmniRoute CLI sessions, switching models, or managing proxy endpoints.",
         ["cli-chat", "cli-models", "cli-keys", "cli-providers", "cli-setup", "cli-tunnel", "config-codex-cli"]),
        ("omniroute-cli-suite-2", "OmniRoute CLI Operations: Advanced", "extend",
         "Monitor server health, circuit breakers, backup syncs, batches, and token analytics.",
         "Inspecting provider circuit breakers, auditing token usage logs, or managing batch jobs.",
         ["cli-health", "cli-cost-usage", "cli-resilience", "cli-routing", "cli-compression", "cli-contexts", "cli-eval", "cli-policy-audit", "cli-mcp", "cli-plugins-skills", "cli-skill-collector", "cli-batches", "cli-backup-sync", "cli-a2a"]),
        ("omniroute-proxy-engine-1", "OmniRoute API Proxy Architecture: Gateway", "extend",
         "Configure unified OpenAI-compatible routing, provider proxies, auth, and secure tunnels.",
         "Directing LLM inference through OmniRoute, rotating upstream keys, or setting up ngrok tunnels.",
         ["omni-inference", "omni-providers", "omni-proxies", "omni-api-keys", "omni-auth", "omni-settings", "omni-tunnels", "omni-version-manager"]),
        ("omniroute-proxy-engine-2", "OmniRoute API Proxy Architecture: Intelligence", "extend",
         "Deploy semantic response caching, RTK context compression, webhooks, and A2A protocol.",
         "Lowering upstream API costs with semantic caching, compressing context, or registering webhooks.",
         ["omni-cache", "omni-compression", "omni-context-rtk", "omni-resilience", "omni-usage-logs", "omni-webhooks", "omni-db-backups", "omni-agents-a2a", "omni-mcp", "omni-models", "omni-sync-cloud", "omni-cli-tools", "omni-github-skills"]),

        # Caveman & N8N & Agent-Dev
        ("caveman-extreme-compression", "Caveman Ultra-Terse Compression", "speed",
         "Cut prompt and tool-call token spend with radical caveman brevity and workflow discovery.",
         "Running Claude Code in ultra-terse caveman mode, compressing memory, and tracking spend.",
         ["cavecrew", "caveman-commit", "caveman-compress", "caveman-discover", "caveman-evidence-review", "caveman-explore", "caveman-help", "caveman-learn", "caveman-manage", "caveman-optimize", "caveman-review", "caveman-setup", "caveman-stats", "megacave", "ultracave"]),
        ("n8n-workflow-automation", "n8n Workflow Engineering and MCP", "extend",
         "Design, validate, and host enterprise n8n workflow automations, custom nodes, and MCP tools.",
         "Building n8n agent workflows, scripting custom JavaScript/Python nodes, or self-hosting n8n.",
         ["n8n-agents", "n8n-workflow-patterns", "n8n-node-configuration", "n8n-code-javascript", "n8n-code-python", "n8n-code-tool", "n8n-error-handling", "n8n-expression-syntax", "n8n-subworkflows", "n8n-validation-expert", "n8n-multi-instance", "n8n-self-hosting", "n8n-mcp-tools-expert", "n8n-binary-and-data", "using-n8n-mcp-skills"]),
        ("agent-harness-engineering", "Agent Harness and Evaluation Engineering", "extend",
         "Architect agent action spaces, tool schemas, observation formats, and evaluation harnesses.",
         "Defining optimal tool sets for autonomous agents or benchmarking completion rates.",
         ["agent-harness-construction", "agent-architecture-audit", "agent-introspection-debugging", "agent-self-evaluation", "autonomous-agent-harness", "deepseek-harness-setup", "harness-engineering", "agent-sort", "agent-runtime-gateway-smoke-test", "automation-audit-ops", "loop-design-check", "token-card", "workspace-surface-audit", "agent-development", "command-development", "mcp-integration", "build-mcp-app", "build-mcp-server", "build-mcpb"]),
        ("skill-authoring-and-governance", "Skill Authoring and Ecosystem Governance", "extend",
         "Draft, lint, verify, and publish AI agent skills and plugins with Hookify rule engines.",
         "Creating new agent skills from repos, testing Hookify rules, or auditing marketplace plugins.",
         ["writing-hookify-rules", "hookify-rules", "skill-development", "skill-authoring", "skill-comply", "skill-host-compat", "skill-scout", "skill-stocktake", "skill-inspector", "find-skills", "plugin-settings", "plugin-structure", "cowork-plugin-customizer", "create-cowork-plugin", "claude-automation-recommender", "claude-md-improver", "codehealth-mcp", "config-gc", "configure-ecc", "ecc-guide", "ecc-recipes", "ecc-tools-cost-audit", "hermes-imports", "rules-distill", "headroom", "discord-access", "discord-configure", "task-observer", "cloudflare-codemode", "opencode", "lean-build", "migration", "ck", "context-and-decisions", "cost-tracking", "inherit-legacy-style", "iterative-retrieval", "nasiko-control-plane", "recursive-decision-ledger", "session-report"]),

        # Agents & Orchestration
        ("autonomous-agent-teams", "Autonomous Agent Teams and Council", "agents",
         "Coordinate multi-agent swarms, four-voice council deliberation, and parallel workflows.",
         "Running autonomous engineering teams, resolving architectural disputes, or managing swarms.",
         ["dev-team", "team-builder", "council", "council-multi-model", "ecc-council", "agentic-engineering", "agentic-os", "ai-first-engineering", "autonomous-loops", "claude-devfleet", "dmux-workflows", "dynamic-workflow-mode", "enterprise-agent-ops", "gan-style-harness", "intent-driven-development", "nanoclaw-repl", "openclaw-persona-forge", "opensource-pipeline", "operator-approval-loop", "parallel-execution-optimizer", "plan-canvas", "plan-orchestrate", "ralphinho-rfc-pipeline", "browser-use", "moli", "graft"]),
        ("orchestrated-feature-delivery", "Orchestrated Feature Delivery (ECC)", "agents",
         "Orchestrate end-to-end MVP building, new features, bug fixes, and refactoring with gates.",
         "Driving complete feature lifecycles from ideation to TDD implementation and gated commit.",
         ["orch-build-mvp", "orch-add-feature", "orch-change-feature", "orch-refine-code"]),

        # GSD (Get Stuff Done) workflow suite
        ("gsd-project-lifecycle", "GSD Project Lifecycle and Planning", "plan",
         "Structure full GSD project initiatives: milestones, requirements, and execution phases.",
         "Initializing a new GSD project workspace, breaking down milestones, or reviewing roadmaps.",
         ["gsd-new-project", "gsd-new-milestone", "gsd-complete-milestone", "gsd-audit-milestone", "gsd-milestone-summary", "gsd-plan-phase", "gsd-spec-phase", "gsd-ultraplan-phase", "gsd-plan-review-convergence", "gsd-discuss-phase", "gsd-settings", "gsd-config", "gsd-help", "gsd-stats", "gsd-inbox", "gsd-phase"]),
        ("gsd-execution-engine", "GSD Autonomous Execution and Verification", "build",
         "Execute phased GSD iterations autonomously with strict verification, cleanup, and rollback.",
         "Running autonomous GSD phases, extracting learnings, and verifying acceptance criteria.",
         ["gsd-execute-phase", "gsd-autonomous", "gsd-fast", "gsd-quick", "gsd-quick-batch", "gsd-verify-work", "gsd-validate-phase", "gsd-cleanup", "gsd-undo", "gsd-pause-work", "gsd-resume-work", "gsd-progress", "gsd-ship", "gsd-pr-branch", "gsd-review", "gsd-review-backlog", "gsd-spike", "gsd-surface", "gsd-thread", "gsd-update", "gsd-workspace", "gsd-workstreams"]),
        ("gsd-codebase-intelligence", "GSD Codebase Intelligence and Memory", "research",
         "Map unfamiliar repositories, capture memory palaces, and trace semantic graph links in GSD.",
         "Onboarding to codebases in GSD, capturing recall nodes, or indexing architectural docs.",
         ["gsd-map-codebase", "gsd-explore", "gsd-onboard", "gsd-capture", "gsd-extract-learnings", "gsd-mempalace-capture", "gsd-mempalace-recall", "gsd-ingest-docs", "gsd-docs-update", "gsd-graphify", "gsd-forensics", "gsd-debug", "gsd-add-tests", "gsd-audit-fix", "gsd-audit-uat", "gsd-eval-review", "gsd-health", "gsd-import", "gsd-manager", "gsd-mvp-phase", "gsd-next", "gsd-profile-user", "gsd-secure-phase", "gsd-sketch", "gsd-ui-phase", "gsd-ui-review", "gsd-ai-integration-phase", "gsd-ns-context", "gsd-ns-ideate", "gsd-ns-manage", "gsd-ns-project", "gsd-ns-review", "gsd-ns-workflow"]),

        # Frontend
        ("frontend-ui-frameworks", "Frontend Frameworks and Modern Bundlers", "build",
         "Build modern reactive web frontends with Vite, Next.js Turbopack, Nuxt 4, Vue 3, and Angular.",
         "Setting up Vite plugins, optimizing Turbopack builds, or developing Vue/Angular components.",
         ["vite-patterns", "nextjs-turbopack", "nuxt4-patterns", "vue-patterns", "ui-to-vue", "angular-developer", "frontend-patterns"]),
        ("advanced-web-motion", "Advanced Web Motion and Physics", "design",
         "Implement fluid UI animations using GSAP, Framer Motion, Locomotive Scroll, and Emil standards.",
         "Crafting spring physics animations, scroll-linked interactions, or GSAP timelines.",
         ["gsap", "framer-motion", "locomotive-scroll", "motion-advanced", "motion-foundations", "motion-patterns", "emil-design-eng", "improve-animations", "find-animation-opportunities", "animate-expo", "animation-vocabulary"]),
        ("design-systems-craft", "Design Systems and Component Engineering", "design",
         "Architect scalable token-based design systems, responsive layouts, and UI guidelines.",
         "Creating enterprise component libraries, token schemas, or Vercel-grade web interfaces.",
         ["design-system", "design-systems", "design-ops", "design-elevation", "headcount-design-system", "web-interface-guidelines", "theme-factory", "interaction-design", "journey-mapping", "ux-research", "ux-strategy", "laws-of-designing", "hallmark", "diagram-design", "hairline-adopt", "hairline-create", "interface-review"]),
        ("elite-taste-and-polish", "Elite Taste and Visual Polish", "design",
         "Override generic LLM design defaults with high-end typography, bento grids, and Apple polish.",
         "Applying editorial typography, brutalist aesthetics, or high-end visual polish to web apps.",
         ["gpt-taste", "taste", "taste-application", "taste-distillation", "stitch-design-taste", "high-end-visual-design", "industrial-brutalist-ui", "minimalist-ui", "apple-design", "redesign-existing-projects", "make-interfaces-feel-better", "full-output-enforcement", "frontend-design", "frontend-design-direction", "mobile-native", "pick-ui-library", "prototype", "playground", "accessibility", "dashboard-builder", "i18n-sync", "liquid-glass-design", "liquid-logo", "web-artifacts-builder", "huashu-design", "awwwards", "jury", "uimax-banner-design", "uimax-brand", "uimax-design", "uimax-design-system", "uimax-slides", "uimax-ui-styling", "ui-ux-pro-max", "react-bits", "react-colorful", "stageshow", "ask-sonner"]),

        # Design Styles (67 styles grouped by aesthetic family)
        ("design-styles-minimal-clean", "Design Styles: Minimalist and Editorial", "design",
         "Curated clean, editorial, paper, and minimalist visual languages.",
         "Building minimalist, monochrome, editorial, or print-inspired interfaces.",
         ["minimal", "clean", "editorial", "paper", "basic", "codex", "modern", "refined", "sleek", "spacious", "square", "terracotta", "claude", "premium", "professional"]),
        ("design-styles-brutalist-mono", "Design Styles: Brutalist, Dark and Hacker", "design",
         "Curated raw brutalist, neobrutalist, mono, hacker-chic, and matrix aesthetics.",
         "Building high-impact brutalist, dark cyber, or terminal-style web interfaces.",
         ["brutalism", "neobrutalism", "mono", "matrix", "power", "enterprise", "industrial-brutalist-ui" if False else "dithered", "corporate"]),
        ("design-styles-tactile-3d", "Design Styles: Tactile, Skeuomorphic and Glass", "design",
         "Curated glassmorphism, claymorphism, neumorphism, and tactile interfaces.",
         "Creating soft 3D, extruded clay, frosted glass, or real-world physical metaphors.",
         ["glassmorphism", "claymorphism", "neumorphism", "skeumorphism", "material", "perspective", "levels"]),
        ("design-styles-vibrant-retro", "Design Styles: Vibrant, Retro and Playful", "design",
         "Curated colorful, neon, retro arcade, 8-bit, and playful illustrative styles.",
         "Crafting vibrant neon interfaces, retro 8-bit games, or playful story-driven designs.",
         ["colorful", "neon", "gradient", "vibrant", "retro", "vintage", "pacman", "sega", "tetris", "riso", "pulse", "creative", "doodle", "sketch", "lingo", "fiction", "fantasy", "storytelling", "expressive", "friendly", "bold", "dramatic", "futuristic", "cosmic", "bento", "contemporary", "flat", "geometric", "artistic", "agentic", "ant", "cafe", "roku", "shadcn", "stitch", "immersive", "style-impeccable"]),

        # Science & Hardware (Blender 3D & Scientific)
        ("hardware-microcontrollers", "Hardware Hacking and Microcontrollers", "build",
         "Develop firmware, pin control, and math algorithms for M5Stack, Cardputer, and embedded hardware.",
         "Programming Cardputer apps, interfacing M5Stack hardware, or solving algorithmic hardware math.",
         ["cardputer-buddy", "m5-onboard", "math-olympiad", "siege", "solo"]),
        ("computational-biology-chemistry", "Computational Biology and Cheminformatics", "research",
         "Analyze single-cell RNA datasets, molecular structures, and deep learning drug models.",
         "Processing AnnData single-cell matrices, running RDKit/Datamol pipelines, or DeepChem models.",
         ["anndata", "astropy", "biopython", "datamol", "deepchem", "scikit-bio", "scientific-schematics"]),
        ("blender-cinematography-lighting", "Blender Cinematography and Studio Lighting", "create",
         "Set up cinematic camera moves, Polyhaven HDRIs, studio lighting, and turntable loops.",
         "Setting up Blender crane shots, dolly rotations, seamless loop renders, or studio lighting.",
         ["blender-toolkit", "blender-director", "blend-camera-cinematography", "blend-lighting", "polyhaven-hdri-showcase", "polyhaven-studio-setup", "crane-shot", "dolly-rotate", "slow-zoom", "turntable", "dynamic-full-loop", "perfect-loop", "blender-product-polish", "blender-motion-state-inspection", "blend-compositing", "blend-rendering", "blend-vfx-fx"]),
        ("blender-materials-and-shaders", "Blender Materials and Geometry Nodes", "create",
         "Author realistic procedural materials, Polyhaven PBR textures, and Geometry Node systems.",
         "Building procedural textures in Blender, applying Polyhaven materials, or node graph modeling.",
         ["blend-materials", "blend-texture-workflow", "blend-geometry-nodes", "blend-procedural-modeling", "blend-lookdev", "polyhaven-material-swap", "polyhaven-texture-apply", "blend-uv-workflow", "blend-hard-surface"]),
        ("blender-character-and-rigging", "Blender Character Modeling and Rigging", "create",
         "Sculpt, retopologize, rig, and simulate cloth/hair for production characters.",
         "Sculpting character models, creating armature rigs, retopologizing meshes, or simulating cloth.",
         ["blender-modeler", "blend-character-artist", "blend-creature-artist", "blend-character-archetypes", "blend-sculpting", "blend-retopology", "blend-rigging", "blend-animation", "blend-cloth-sim", "blend-hair-groom", "blend-physics-sim"]),
        ("blender-environment-and-export", "Blender Environment Art and Game Engine Export", "create",
         "Assemble 3D game scenes and export optimized assets to Godot, Unity, Three.js, and Unreal.",
         "Exporting 3D assets to Unreal, Unity, Godot, or Three.js with LODs and collision proxies.",
         ["blend-environment-artist", "blend-scene-assembly", "blend-set-dressing", "blend-prop-artist", "blend-vegetation-artist", "blend-vehicle-artist", "polyhaven-scene-builder", "blend-asset-optimization", "blend-lod-pipeline", "blend-collision-proxy", "blend-export-pipeline", "blend-unreal-export", "blend-unity-export", "blend-godot-export", "blender-threejs-export", "blend-qa-review", "image-to-3d", "multi-image-to-3d"]),
        ("blender-game-genres", "Blender 3D Game Genre Templates", "create",
         "Tailor 3D models and mechanics for RPGs, shooters, survival, platformers, and narrative games.",
         "Creating art and level geometry specifically tailored to game genre constraints.",
         ["blend-genre-action-combat", "blend-genre-card-party-idle", "blend-genre-metroidvania-roguelike", "blend-genre-narrative-vn", "blend-genre-open-world-sandbox", "blend-genre-puzzle-platformer", "blend-genre-racing-sports", "blend-genre-rpg", "blend-genre-shooter", "blend-genre-soulslike", "blend-genre-stealth", "blend-genre-strategy-sim", "blend-genre-survival", "blend-apocalypse-worlds", "blend-fantasy-worlds", "blend-historical-worlds", "blend-sci-fi-punk-worlds", "blend-biome-worlds"]),
        ("blender-stylized-and-horror", "Blender Stylized, Horror and Retro Aesthetics", "create",
         "Build specialized 3D aesthetics: PSX retro, analog horror, anime, voxel, and comic book.",
         "Crafting low-poly PSX horror, anime cel-shading, stop-motion look, or voxel models.",
         ["blend-horror-style", "blend-analog-found-footage-horror", "blend-psx-horror-style", "blend-body-horror-style", "blend-cosmic-eldritch-horror", "blend-folk-horror-style", "blend-indie-horror-aesthetics", "blend-mascot-puppet-horror", "blend-anime-style", "blend-cartoon-style", "blend-chibi-style", "blend-comic-book-style", "blend-manga-style", "blend-stylized-style", "blend-hand-painted-style", "blend-painterly-style", "blend-pixel-art-style", "blend-voxel-style", "blend-lowpoly-style", "blend-hd-2d-style", "blend-retro-8bit-style", "blend-retro-16bit-style", "blend-visual-console-eras", "blend-isometric-style", "blend-vector-style", "blend-stop-motion-craft-style", "blend-archviz", "blend-brutalist-mood", "blend-cozy-wholesome-mood", "blend-dark-gritty-mood", "blend-dream-surreal-mood", "blend-dream-weirdcore-style", "blend-frutiger-aero-style", "blend-liminal-space-style", "blend-minimalist-style", "blend-neon-retrofuturism", "blend-noir-style", "blend-realistic-style"]),

        # Business Ops Suite
        ("founder-suite-launch", "Founder Suite: Launch and Strategy", "business",
         "Define early-stage founder strategy, brand identity, competitor moat, and launch offer.",
         "Validating SaaS startup ideas, structuring founder offers, or planning initial market entry.",
         ["founder-plan", "founder-offer", "founder-brand", "founder-competitors", "founder-launch", "founder-consumer", "founder-board", "founder-cfo", "founder-marketing", "founder-ops", "founder-pricing", "saas-idea-validator", "chief-strategy-officer", "chief-executive", "ceo-advisor", "business-growth-consultant"]),
        ("executive-finance-cfo", "Executive Corporate Finance and CFO", "business",
         "Manage capital allocation, financial modeling, treasury liquidity, and audit controls.",
         "Building financial forecasts, modeling unit economics, or managing cash treasury.",
         ["chief-financial-officer", "financial-modeling", "financial-reporting-and-close", "financial-statement-analysis", "budgeting-and-forecasting", "capital-allocation", "capital-structure-and-covenants", "cost-accounting", "revenue-recognition", "treasury-and-liquidity", "unit-economics", "tax", "internal-controls-and-audit", "customer-billing-ops", "finance-billing-ops", "receipts", "fundraising-and-investor-relations"]),
        ("corporate-legal-governance", "Corporate Legal, Governance and Risk", "business",
         "Review master enterprise agreements, privacy compliance, and corporate risk posture.",
         "Reviewing customer contracts, managing intellectual property, or auditing regulatory compliance.",
         ["chief-legal-and-risk-officer", "contract-review", "master-agreement-generator", "corporate-governance", "disputes-and-legal-holds", "enterprise-risk", "intellectual-property", "privacy-and-data-protection", "regulatory-compliance", "counterparty-channel-discipline", "esign-field-placement", "visa-doc-translate"]),
        ("growth-marketing-and-seo", "Growth Marketing and Acquisition", "business",
         "Drive programmatic SEO, performance marketing, landing page CRO, and app store growth.",
         "Optimizing search rankings, running paid ad campaigns, or engineering viral referral loops.",
         ["growth-log", "seo-strategy", "programmatic-seo", "ai-search-optimization", "app-store-optimization", "landing-page-cro-expert", "lead-capture", "lead-intelligence", "experimentation", "marketing-analytics", "paid-advertising", "account-based-marketing", "lifecycle-messaging", "listing-distribution", "behavioral-marketing", "social-graph-ranker"]),
        ("content-and-brand-marketing", "Content Strategy and Brand Communications", "business",
         "Lead corporate editorial communications, newsletter publishing, and product launch PR.",
         "Planning quarterly marketing campaigns, writing product launch press releases, or newsletters.",
         ["chief-content-officer", "chief-marketing-officer", "content-strategy", "headcount-brand-voice", "marketing-campaign-planner", "marketing-copywriting", "marketing-planning", "newsletter-writer", "partnership-marketing", "positioning-and-messaging", "product-launch", "public-relations", "social-post-craft", "video-content", "visual-content", "youtube-producer", "internal-comms", "events-and-field-marketing"]),
        ("customer-success-and-support", "Customer Success and Implementation", "business",
         "Drive enterprise customer onboarding, retention, support desks, and voice-of-customer.",
         "Streamlining new customer onboarding, handling escalation tickets, or reducing churn.",
         ["chief-customer-officer", "customer-onboarding-and-implementation", "customer-success-management", "customer-research", "retention", "escalation-management", "self-service-and-knowledge", "support-operations", "voice-of-customer", "activation"]),
        ("sales-revenue-operations", "Enterprise Sales and Revenue Operations", "business",
         "Scale outbound sales pipelines, complex deal negotiation, packaging, and RevOps.",
         "Negotiating enterprise contracts, structuring sales comp plans, or optimizing RevOps pipelines.",
         ["chief-revenue-officer", "deal-negotiation", "outbound-prospecting", "pricing-and-packaging", "referral-programs", "revenue-operations", "sales-compensation-and-territory", "sales-enablement"]),
        ("people-hr-operations", "People, Talent and HR Operations", "business",
         "Scale hiring funnels, compensation leveling, org structure, and employment compliance.",
         "Designing engineering compensation bands, onboarding employees, or managing workforce plans.",
         ["chief-human-resources-officer", "benefits-and-leave", "compensation-and-leveling", "employee-relations", "employment-compliance", "hiring-and-interviewing", "learning-and-development", "onboarding-and-offboarding", "org-design", "payroll-operations", "performance-management", "workforce-planning"]),
        ("enterprise-operations-coo", "Enterprise Operations and PMO", "business",
         "Drive operational cadence, vendor procurement, facilities, and PMO program governance.",
         "Running executive operating reviews, auditing vendor procurement, or managing critical incidents.",
         ["chief-operating-officer", "operating-cadence", "process-design", "procurement-and-sourcing", "quality-management", "service-level-management", "vendor-management", "facilities-and-workplace", "business-continuity-and-resilience", "capacity-and-demand-planning", "incident-management", "head-of-pmo", "program-management", "portfolio-governance", "project-delivery", "schedule-development-and-analysis", "change-and-adoption", "benefits-realization", "dependency-and-risk-management", "estimating-and-contingency", "ops-check", "project-flow-ops", "email-ops", "messages-ops", "google-workspace-ops", "mailtrap-email-integration", "jira-integration", "connections-optimizer", "unified-notifications-ops"]),
        ("enterprise-it-administration", "Enterprise IT and Systems Administration", "business",
         "Administer cloud infrastructure, identity lifecycles, endpoint fleets, and IT service desks.",
         "Managing company IT helpdesks, onboarding SSO identities, or auditing IT assets.",
         ["chief-information-officer", "cloud-administration", "collaboration-platform-administration", "endpoint-management", "identity-lifecycle-administration", "it-asset-management", "network-administration", "service-desk", "systems-administration", "telephony-and-conferencing", "virtualization-operations", "backup-and-recovery"]),
        ("data-intelligence-bi", "Data Intelligence and Analytics Governance", "business",
         "Architect corporate data platforms, quantitative analytics, and AI/ML data governance.",
         "Modeling enterprise data warehouses, writing BI dashboards, or establishing data governance.",
         ["chief-data-officer", "business-intelligence", "data-engineering", "data-governance", "data-modeling", "quantitative-analysis", "ai-ml-governance", "ai-research-analyst"]),
        ("product-management-cpo", "Product Management and Discovery (CPO)", "business",
         "Shape product requirements, user discovery, interface craft, and visual design standards.",
         "Writing product requirement PRDs, designing UI mockups, or auditing product-market fit.",
         ["chief-product-officer", "product-requirements", "product-discovery", "product-capability", "product-lens", "interface-craft", "interface-redesign", "ux-product-auditor", "presentation-design", "visual-reference-generation", "brand-identity", "design-styles"]),
        ("strategic-alliances-mna", "Strategic Alliances and M&A", "business",
         "Execute mergers and acquisitions, joint ventures, scenario models, and portfolio strategy.",
         "Structuring corporate acquisitions, modeling joint venture terms, or planning market entry.",
         ["strategic-alliances", "mergers-and-acquisitions", "market-entry", "portfolio-strategy", "scenario-planning", "competitive-platform-analysis"]),
        ("enterprise-infosec-ciso", "Enterprise Information Security (CISO)", "business",
         "Govern enterprise threat modeling, incident response, zero trust identity, and encryption.",
         "Establishing corporate CISO policies, conducting threat models, or responding to breaches.",
         ["chief-information-security-officer", "threat-modeling", "incident-response", "detection-and-monitoring", "access-and-identity", "data-protection-and-encryption", "security-architecture-review", "vulnerability-management"]),
        ("executive-cto-engineering", "Executive Engineering and Architecture (CTO)", "business",
         "Lead organizational engineering architecture, tech debt roadmaps, and parallel AI delivery.",
         "Leading engineering org decisions, solution architecture reviews, or technical debt planning.",
         ["chief-technology-officer", "solution-architecture", "solution-exploration", "cloud-infrastructure", "observability-and-reliability", "ai-workflow-architect", "parallel-agent-delivery", "branch-and-worktree-workflow", "data-migration", "implementation-planning", "release-and-deployment", "completion-verification", "code-review", "technical-debt-management", "systematic-debugging", "test-driven-development", "headcount-api-design", "headcount-prompt-optimizer", "agent-hierarchy"]),
    ]

def verify_and_apply():
    cat = json.load(open(os.path.join(ROOT, 'catalog.json'), encoding='utf-8'))['skills']
    all_skills = {s['name']: s for s in cat}

    recipes = {r['name']: r for r in lib.v1.RECIPES}
    raw_path = os.path.join(ROOT, 'bundles.json')
    raw_data = json.load(open(raw_path, encoding='utf-8'))
    existing_bundles = raw_data['bundles']

    already_bundled = set()
    for b in existing_bundles:
        if 'recipe' in b:
            r = recipes.get(b['recipe'])
            if r:
                already_bundled.update(r['skills'])
        else:
            already_bundled.update(b.get('skills', []))

    new_bundles = get_bundle_definitions()
    newly_bundled = set()
    seen_ids = set()

    for bid, name, purpose, goal, when, skills in new_bundles:
        assert bid not in seen_ids, f"Duplicate bundle id: {bid}"
        seen_ids.add(bid)
        assert len(skills) >= 2, f"Bundle {bid} has fewer than 2 skills: {skills}"
        assert len(skills) == len(set(skills)), f"Bundle {bid} has duplicate skills"
        for s in skills:
            assert s in all_skills, f"Skill {s} in bundle {bid} not in catalog"
            newly_bundled.add(s)

    total_bundled = already_bundled | newly_bundled
    unbundled = set(all_skills.keys()) - total_bundled
    print(f"Catalog skills: {len(all_skills)}")
    print(f"Already bundled: {len(already_bundled)}")
    print(f"Newly bundled: {len(newly_bundled)}")
    print(f"Total bundled: {len(total_bundled)}")
    print(f"Still unbundled: {len(unbundled)}")
    if unbundled:
        print("Remaining unbundled:", sorted(list(unbundled)))
        return False

    # Format new bundle objects
    added_bundle_objs = []
    for bid, name, purpose, goal, when, skills in new_bundles:
        added_bundle_objs.append({
            "id": bid,
            "name": name,
            "purpose": purpose,
            "goal": goal,
            "when": when,
            "skills": skills
        })

    raw_data['bundles'].extend(added_bundle_objs)
    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump(raw_data, f, indent=2, ensure_ascii=False)
    print(f"Updated {raw_path} with {len(added_bundle_objs)} new bundles! Total bundles: {len(raw_data['bundles'])}")
    return True

if __name__ == '__main__':
    ok = verify_and_apply()
    if not ok:
        sys.exit(1)
