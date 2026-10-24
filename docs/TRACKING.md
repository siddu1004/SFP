# Following the agent: phase tracking, Kalman filter and Markov chain

The hive chooses skills from a task's words. While an agent works, its activity says more: the files it edits, the commands it runs, the errors it hits. `mcp/sfp_track.py` turns that activity into the phase of work, so the skills can change when the work changes, and predicts the next phase so its skills can be ready.

```bash
# events as a JSON list, or one JSON object per line
echo '[{"t": 1700000000, "kind": "run", "command": "go test ./...", "exit": 1}]' | python3 mcp/sfp_hive.py track --json
```

The answer has the current phase and its layer, a confidence, each phase's share of the work, the phase changes seen, the next phases the Markov chain expects, the skills for now, and the skills for the most likely next phase. The state carries over between calls in the hive's data folder (`track_state.json`), and the learned transitions are in `phases.json`.

## The three layers

| Layer | What it does | In the code |
|---|---|---|
| Evidence | Each event gives evidence for some of the eleven phases. Editing `parse_test.go` or running `go test` is testing; a Dockerfile or `git push` is shipping; a failing command is debugging, and while a failure is open, editing source code counts as debugging, not building, until something passes | `evidence()` |
| Kalman filter | One scalar filter per phase tracks how much of the work is that phase. Between events the estimate relaxes towards a weak prior and its uncertainty grows; each event is a noisy measurement, with less noise for strong evidence (a prompt, a test run) than weak (opening a file). The phase changes only when the new one leads by a margin and the filter is confident | `PhaseFilter`, `run()` |
| Markov chain | Counts changes of phase, starting from a prior that encodes the usual order of work, and fades them with a 30-day half-life. Predicts the next phase | `PhaseChain` |

The tracked phase is passed to the hive as `phase_hint`. It is blended half and half with what the task's words say, and it adds the phase's own words to the search, so skills for that job can join even when the task did not name it. Without a hint, selection is unchanged.

## How well it works

Two sets of hand-written agent sessions, each event labelled with the true phase. The filter's two responsiveness settings were tuned on the first (dev) set. The second (held-out) set was written before that tuning and checked once.

| Method | Dev: accuracy | Dev: switches (17 true) | Held-out: accuracy | Held-out: switches (17 true) |
|---|---|---|---|---|
| Last event only | 73.5% | 45 | 73.8% | 29 |
| Majority of the last three | 75.5% | 25 | 54.1% | 23 |
| Kalman filter | 80.4% | 22 | 67.2% | 26 |

| Next phase (Markov) | Dev | Held-out |
|---|---|---|
| Prior only | 76.5% | 41.2% |
| Learned from the other sessions | 70.6% | 52.9% |

What this says, plainly:

- The filter is steadier than following the last event: fewer phase switches on both sets, so the suggested skills do not churn. On the held-out set it is also about 7 points less accurate than the last event, because it waits for evidence before switching. The tuning partly fit the dev set.
- The learned chain beat the hand-written prior on the held-out set and lost to it on the dev set. With 17 phase changes per set, neither difference is reliable.
- The sessions are small and written by hand. Real use will say more: the extension shows the phase and its confidence, and a wrong phase is visible at once.
- Opening a file says little, and an agent working in one file for a long time gives little to go on. Prompts and test runs are the strongest evidence.

Run `python3 -c "import sys,json; sys.path.insert(0,'mcp'); import sfp_track as t; print(t.evaluate(json.load(open('tests/track_heldout.json'))['sessions']))"` to repeat the held-out numbers. `tests/test_track.py` holds the floors.

## Clusters

819 skills are hard to browse, so `clusters.json` groups them into about 40 named clusters, such as "UI components and design systems", "Animation and motion", "Testing and QA" and "GSD project workflow". A skill goes to the first cluster that matches its name and category, and lists up to two more it also fits. `python3 mcp/sfp_hive.py clusters` lists them with how often their skills were used; `cluster-add "My UI kit" --skills impeccable,frontend-a11y` adds one of your own (kept in your data folder), and `cluster-remove` takes it out.
