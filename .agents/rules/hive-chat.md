# SFP Live Hive Chat Protocol

Whenever chatting with the user in this Antigravity IDE agentic chat window:
1. **Dynamic Skill Analysis**:
   Evaluate every user prompt with the SFP Hive engine (`mcp/sfp_hive.py select "<prompt>"` or `select_skills` tool).
2. **Real-Time Header in Response**:
   Render the live SFP Hive monitor banner at the start of your reply:
   - **Active Skills**: names and relevance scores.
   - **Prompt Skill Delta**: `+ Added` and `- Removed` skill names compared to the last turn.
   - **Three-Tier Layers**:
     - `⚡ Base Layer (Grounding)`: core architecture & implementation skills.
     - `🛡️ Check Layer (Safety & Standards)`: testing, security, edge-case guards.
     - `✨ Finish Layer (Review & Polish)`: reviews, polish, docs.
   - **Context Budget**: token consumption against the 12,000 token ceiling.
3. **Skill Execution**:
   Apply the rules and patterns from the selected skills during the implementation.
