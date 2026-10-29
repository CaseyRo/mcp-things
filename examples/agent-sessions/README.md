# Agent sessions from Things

A to-do tagged `claude` plus the name of a repo opens a Claude Code session in
that repo. When you quit the session, the to-do is completed.
[docs/beyond-things.md](../../docs/beyond-things.md) explains the idea; this is
the smallest version you can run.

## Try it

```bash
REPOS_DIR=~/code uv run --script things_sessions.py --dry-run
```

In Things, tag a to-do `claude` and `my-repo` (a folder under `REPOS_DIR`) and
run the dry run again: it prints the session it would start. Without
`--dry-run` it opens a Terminal window, starts `claude` in plan mode with the
to-do as its brief, and tags the to-do `started`.

Tags:

| Tag | Effect |
|---|---|
| `claude` | Marks the to-do for an agent |
| a repo folder name | Where the session runs; required |
| `go` | Normal permission mode instead of plan mode |
| `started` | Set by the script; the to-do won't start again |

A When date holds the to-do back until that day.

## Run it every minute

`~/Library/LaunchAgents/com.example.things-sessions.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.example.things-sessions</string>
  <key>ProgramArguments</key>
  <array>
    <string>/opt/homebrew/bin/uv</string><string>run</string><string>--script</string>
    <string>/path/to/mcp-things/examples/agent-sessions/things_sessions.py</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict><key>REPOS_DIR</key><string>/Users/you/code</string></dict>
  <key>StartInterval</key><integer>60</integer>
  <key>StandardErrorPath</key><string>/tmp/things-sessions.log</string>
</dict>
</plist>
```

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.things-sessions.plist
```

macOS asks once for Automation access to Things and to Terminal.

## Before you rely on it

- A session works in your repo with your permissions. Plan mode is the default for a reason;
  use `go` only for tasks you would hand over without looking.
- The to-do's notes go into the session as context. Notes pasted from mail or the web are read
  as data, but anything that reaches an agent can try to steer it.
- The script reads and writes Things through AppleScript, not through mcp-things. The session
  itself can use mcp-things to file follow-up to-dos, if you connect it in Claude Code.
