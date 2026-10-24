# Test in a real VS Code

`drive.js` operates a real VS Code workbench in a headless browser with the extension installed, and checks the whole path: it activates at startup, the command is in the palette, choosing skills lists them, the status bar counts them, the prompt is copied and feedback is sent. Then check `feedback.jsonl` in your `SFP_DATA_DIR`.

It ran against code-server 4.117.0 (VS Code 1.117.0). It is not run by `npm test`.

1. Get code-server (the real VS Code in a browser): `npm install --prefix <dir> code-server`. Its post-install builds native modules; if that fails on `kerberos` (no Kerberos headers) or on `@vscode/ripgrep` (no access to GitHub), install with `--ignore-scripts` and run `npm install --omit=dev --ignore-scripts` inside `node_modules/code-server/lib/vscode`. Neither is needed for this test.
2. Install the extension and start the server, with a home folder whose `.sfp/root` names your SFP checkout:

```bash
export HOME=<home> SFP_DATA_DIR=<data>   # <home>/.sfp/root contains the SFP checkout path
E=<dir>/node_modules/code-server/out/node/entry.js
node $E --user-data-dir <ud> --extensions-dir <ext> --install-extension sfp-hive-0.1.0.vsix
node $E --auth none --bind-addr 127.0.0.1:8099 --user-data-dir <ud> --extensions-dir <ext> <workspace>   # leave running
```

3. In another shell: `npm install --no-save playwright-core`, then `node test/e2e/drive.js 8099 <workspace>`. Set `CHROMIUM` to a Chromium binary if it is not at `/opt/pw-browsers/chromium`.
