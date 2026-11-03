---
name: mirofish
description: "Run MiroFish swarm-intelligence simulations to explore scenarios in a digital sandbox. Use when exploring how a scenario might unfold with a multi-agent swarm simulation."
---

> Written for SFP in its own words from the project at https://github.com/666ghj/MiroFish (upstream license: AGPL-3.0).

# Running MiroFish Swarm-Intelligence Simulations

## Use this skill when
- You need to predict outcomes of complex scenarios.
- Want to test policies or public relations strategies safely.
- Explore imaginative or novel story endings.

## What it is
MiroFish is an AI prediction engine using multi-agent technology. It creates a high-fidelity digital world where intelligent agents interact, allowing you to dynamically inject variables and deduce future trajectories through simulations.

## Steps
1. **Graph Building**: Upload seed materials (e.g., data reports, stories) and describe your prediction requirements in natural language.
2. **Environment Setup**: Configure environment variables with required API keys for LLM and Zep Cloud services.
3. **Install Dependencies**:
   - Install Node.js dependencies: `npm run setup`
   - Install Python dependencies: `npm run setup:all` or follow step-by-step instructions.
4. **Run Simulation**: Execute the simulation command to start the swarm-intelligence process.
5. **Generate Report**: Review the detailed prediction report and interact with the simulated environment.

## Checks
- Ensure all required environment variables are correctly set in `.env`.
- Verify that dependencies are installed without errors.
- Confirm that the simulation runs smoothly and generates a report.

## Pitfalls
- High API consumption may occur; start with fewer than 40 rounds for initial simulations.
- Incorrect configuration of environment variables can lead to failed simulations.
