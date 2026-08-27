---
name: graphori-dashboard
description: Open a local read-only dashboard for a Graphori run. Use when the user asks to view the Graphori dashboard, current run progress, or the result of a specific run. Do not use it to implement or redesign the dashboard itself.
---

# Graphori Dashboard

Start the local dashboard for an existing Graphori journal and open its page. Read run
records only; never start, resume, approve, or modify a Graphori run.

Match user-facing messages to the user's language. Honor an explicit language request
first, then use the request language, active conversation language, system locale, and
English in that order.

## 1. Select the target

Use the workspace or run ID supplied by the user. Otherwise, use the current Git
repository root as the workspace, or the current directory when it is not a Git
repository. Without a run ID, the CLI selects the journal with the newest modification
time.

This step is complete when the absolute workspace path and optional run ID are known.

## 2. Start the dashboard

Check that the `graphori` command is installed. If it is missing, report that the
Runtime is required; do not guess an internal source path.

Start this command in a host-provided long-running terminal or background process:

```bash
graphori dashboard --root "<workspace>" --port 0
```

Add `--run-id "<run-id>"` only for a specific run. The CLI binds to a loopback address
and prints the actual URL. A live process is expected and must not be treated as a
timeout merely because it keeps running.

This step is complete when the CLI prints a loopback dashboard URL and the server
process remains alive.

## 3. Check the page

If the CLI cannot open a browser, open the printed URL with an available browser tool.
Confirm that the page responds and, when specified, displays the requested run ID. Do
not change the journal, run state, or approval gates.

Report the URL, workspace, and selected run ID—or that the latest run was selected.
Keep the server alive for the user and stop it only when asked.
