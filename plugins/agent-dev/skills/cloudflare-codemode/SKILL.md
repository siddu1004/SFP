---
name: cloudflare-codemode
description: "Build and run sandboxed agent tools using Cloudflare Code Mode (@cloudflare/codemode). Connects dynamic Worker sandboxes, Durable Objects, OpenAPI, and MCP servers safely. Use when creating agent sandboxes, building code tools, or integrating Cloudflare Workers with agents."
---

# Cloudflare Code Mode

Build, configure, and operate sandboxed tool execution for AI agents using Cloudflare Code Mode (`@cloudflare/codemode`). Code Mode enables agents to execute dynamic JavaScript/TypeScript inside isolated Worker or browser sandboxes, calling typed host connectors without leaking secrets or direct host authority.

## Use This Skill When

- Building or configuring sandboxed execution environments for AI agents using `@cloudflare/codemode`.
- Exposing OpenAPI endpoints or MCP servers to agents as safe, typed sandboxed globals (`McpConnector`, `OpenApiConnector`).
- Implementing stateful, durable agent runtimes backed by Cloudflare Durable Objects (`createCodemodeRuntime`).
- Integrating agent code execution with Vercel AI SDK (`@cloudflare/codemode/ai`), TanStack AI (`@cloudflare/codemode/tanstack-ai`), or MCP tools.

## Architecture & Core Concepts

1. **Host Control Plane (`createCodemodeRuntime`)**:
   Runs inside a Cloudflare Durable Object to manage execution states, audit logs, and runtime facets.
2. **Connectors (`CodemodeConnector`)**:
   Bridge host-side capabilities into sandbox globals. Built-in connectors include `McpConnector`, `OpenApiConnector`, and `ToolSetConnector`.
3. **Executors (`Executor`)**:
   Isolated execution engines:
   - `DynamicWorkerExecutor`: Ephemeral V8/Worker sandbox running generated code with strict CPU/memory limits.
   - `IframeSandboxExecutor`: Browser-side sandboxed iframe for client-side tool execution.

## Step-by-Step Implementation

### 1. Install Dependencies

```bash
npm install @cloudflare/codemode
# For AI SDK or framework adapters:
npm install @cloudflare/codemode/ai @ai-sdk/openai ai
```

### 2. Configure Runtime in a Durable Object

```typescript
import { DurableObject } from "cloudflare:workers";
import { createCodemodeRuntime, DynamicWorkerExecutor, McpConnector } from "@cloudflare/codemode";

export class AgentRuntimeDO extends DurableObject {
  private runtime;

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);

    this.runtime = createCodemodeRuntime({
      ctx,
      name: "agent-session",
      maxExecutions: 50,
      connectors: [
        new McpConnector({
          name: "tools",
          client: mcpClientInstance,
        }),
      ],
      executor: new DynamicWorkerExecutor({
        env,
        limits: { cpuMs: 5000, subrequests: 10 },
      }),
      transformResult: (result) => {
        // Redact internal pointers before returning to LLM
        return typeof result === "object" ? { ...result, _internal: undefined } : result;
      },
    });
  }

  async executeCode(code: string) {
    return await this.runtime.run({ code });
  }
}
```

### 3. Expose as an AI SDK Code Tool

```typescript
import { createCodeTool } from "@cloudflare/codemode/ai";

export const sandboxTool = createCodeTool({
  runtime: runtimeHandle,
  name: "run_sandboxed_code",
  description: "Execute sandboxed JavaScript code with access to configured connectors (e.g. tools.*).",
});
```

## Verification & Checks

- [ ] Ensure connector names are unique and do not collide with reserved name `codemode`.
- [ ] Verify `DynamicWorkerExecutor` limits (CPU milliseconds and subrequest quotas) match workload boundaries.
- [ ] Confirm sensitive environment secrets are passed via scoped connectors, never exposed as raw global environment variables in the sandbox.
- [ ] Audit execution logs via `runtime.getExecutions()` to verify non-leaking error traces.

## Common Pitfalls

- **State Leakage**: Sandboxes are ephemeral per execution; do not rely on in-memory global state across runs. Use Durable Object storage.
- **Reserved Identifier**: Never name a connector `codemode`.
- **Unhandled Async Promises**: Ensure all connector calls within sandbox code are awaited before the execution script completes.

## Sources

- [Cloudflare Code Mode API Reference](https://developers.cloudflare.com/agents/tools/codemode/api-reference/)
- [Cloudflare Agents Documentation](https://developers.cloudflare.com/agents/)
