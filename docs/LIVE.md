# Live attaching: skills follow what you type

`python3 mcp/sfp_hive.py live "<draft so far>" [--state JSON] [--pin a,b] [--remove c] [--commit] --json` returns the skills to attach to a message that is still being typed. `mcp/sfp_live.py` holds the logic, `src/live.ts` the debounced session, `tests/test_live.py` and `test/live.test.js` the tests.

## The rules

1. Fewer than 2 content words: nothing changes (`waiting`).
2. Skills you **pinned** are always attached; skills you **removed** never come back for this message.
3. If the draft still means what it meant when the skills were chosen (word overlap of at least 0.6) the list stays (`kept`). Typing more words does not make it flicker.
4. Otherwise the hive chooses again (`updated`). A skill attached before keeps its place while it is within 3 places of the cut, so a small change of topic moves one skill, not four.
5. Typing logs nothing. `--commit` (the message was sent) records one decision, so feedback and learning work as usual. Pins and removals made by the user are the feedback signal: send them with `give_feedback` (`missing` for pins, `unhelpful` for removals), as the Choose tab already does.

State is plain JSON (`anchor`, `auto`, `pinned`, `removed`): pass back what the last call returned, drop it when the message is sent.

## What the editor can and cannot see

The public VS Code API does not let an extension read another panel's input box. So the live layer has three sources, in the order to build them:

1. **The hive's own input** (a text box at the top of the Choose tab, and the `@hive` chat participant): fires on every keystroke. This is the reliable one.
2. **`@hive` on send**: the participant receives the whole message, calls `send()`, and answers with the skills and a prompt that carries them.
3. **The agent's own input**: only if Antigravity exposes a public command or event for its input text. Antigravity's agent should check whether one exists (look in `vscode.commands.getCommands()` and its documented extension API). If it does, feed `LiveSession.type()` from it. If not, say so in the report; do not scrape, read or patch Antigravity's files.

## Brief for Antigravity (enhancements)

Build on `LiveSession` and `liveArgs`/`parseLive`; do not change the Python contract without changing both and the tests.

- Wire source 1 and 2 above. The Choose tab shows the attached skills as chips marked **auto** or **pinned**, with a remove (x) and a restore control; each change calls `steer()`.
- Show a quiet "waiting for more words" state, and never flash an empty list while a call is running (keep the last result until the new one arrives).
- On send, call `send()`, then send the interventions as feedback with `interventionFeedback`.
- Setting `sfpHive.autoAttach` (default on) and `sfpHive.autoAttachDelayMs` (default 350).
- Ideas to enhance, in order: use the open file and selection as extra words; show why a skill was attached (the explain list); let a pinned skill carry over to the next message when the user turns on "keep my pins".
- Tests: a message-handler test per new message, and a case in `test/e2e/drive.js` that types in the Choose input and sees chips appear.

Acceptance: A1 type "fix" and see nothing; A2 type "make the login form accessible and animate the button" and see skills within 1 s of stopping; A3 keep typing the same idea and see the list stay still; A4 remove one skill, keep typing, it does not return; A5 pin one, change topic, the pin stays; A6 send, and `decisions.jsonl` gains exactly one line.
