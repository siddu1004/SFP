---
name: agency-agents
description: "Selects and loads a specialist persona from the agency-agents collection based on task requirements. Use when a task needs a specialist persona (engineering, marketing, game development, security, design, sales, testing and more)."
---

> Written for SFP in its own words from the project at https://github.com/msitarzewski/agency-agents (upstream license: MIT).

# Skill: Specialist Persona Selector

## Use this skill when
- You need expertise in a specific domain like engineering, marketing, or game development.
- The task requires unique communication styles and proven deliverables.

## What it is
This skill helps an AI coding agent pick the right specialist persona from the agency-agents collection. Each persona has deep expertise, a distinct personality, and focuses on delivering real code and measurable outcomes.

## Steps
1. Identify the domain or type of task (e.g., engineering, marketing).
2. Browse the appropriate folder in the agency-agents repository.
3. Select an agent that best matches the task requirements.
4. Load the selected agent's persona into the coding environment using the provided installation script.
5. Activate the agent for the current session.

## Checks
- Ensure the correct folder is browsed based on the task domain.
- Verify that the selected agent has the necessary skills and personality traits for the task.
- Confirm successful loading of the agent's persona in the coding environment.

## Pitfalls
- Avoid selecting a generic prompt template instead of a specialized agent.
- Be cautious about mismatching the agent's expertise with the task requirements.

## Persona folders
The collection has about 330 personas in folders: engineering (66), specialized (59), marketing (37), game-development (21), integrations (19), strategy (16), gis (13), security (12), design (10), sales (9), testing (9), paid-media (7), project-management (7), academic (6), examples (6).

To load one, open https://github.com/msitarzewski/agency-agents/tree/main/<folder>, pick the persona whose file name fits the task, and read its markdown as the role to take on. Prefer one persona per task; say which one you chose and why.

