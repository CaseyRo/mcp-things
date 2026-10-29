# Beyond the Things app

mcp-things lets an assistant read and change your Things. That is useful in a
chat. It gets more interesting when Things becomes the place where work is
handed to agents, and where they report back.

## Clients and automations

Anything that speaks MCP can use the same 32 tools:

- **Claude Desktop and Claude Code** in conversation: capture, reviews, "what should I do now".
- **n8n and Node-RED** on a schedule: a morning digest, an inbox count on a dashboard, a nudge
  when a project stalls. See [clients/n8n.md](clients/n8n.md).
- **Other agents**: a coding session that files its own follow-up to-dos when it finds work
  it shouldn't do now.

## A to-do that does itself

The pattern the author runs every day:

1. You write a to-do anywhere, usually on the phone: "Update the README badges", tagged
   `claude` and `mcp-things`.
2. Things Cloud syncs it to the Mac.
3. A small trigger, run by launchd every minute, finds open to-dos tagged `claude` whose When
   date has arrived and that carry a second tag naming a repository.
4. It tags the to-do `started` and opens a Claude Code session in that repository, with the
   to-do's title and notes as the brief.
5. The session does the work. If it finds more, it files follow-up to-dos through mcp-things.
6. When the session ends, the trigger completes the to-do. A repeating to-do then produces its
   next occurrence, which is how scheduled routines run.
7. Your phone shows it done.

![A to-do captured on the phone syncs to Things on the Mac; a trigger starts a Claude Code session in the tagged repo; the session files follow-ups through mcp-things; the trigger completes the to-do when the session ends](media/agentic-loop.gif)

*Static, theme-aware version: [SVG](media/agentic-loop.svg) · [WebM](media/agentic-loop.webm). Drawn with Archify; source: [agentic-loop.archify.json](media/agentic-loop.archify.json).*

The trigger is not part of the server. A runnable version, with plan mode as the
default and a test for its decision logic, is in
[examples/agent-sessions](../examples/agent-sessions/).

### The guardrails that make it usable

- **Explicit opt-in.** Only to-dos you tagged start anything; one tag picks the repository.
- **Time.** The When date holds a to-do back, so you can queue work for tomorrow morning.
- **Plan first.** Sessions start in plan mode unless the to-do says otherwise.
- **Once.** The `started` tag keeps a to-do from starting twice; closing the session closes
  the to-do, so open sessions and open to-dos stay in step.
- **Notes are data.** The brief tells the agent to treat pasted notes as context, not as
  instructions that widen the task.

## Things as a personal operating system

Things is where commitments get written down: on the phone when you think of
them, on the watch when you're out, on the Mac where agents can reach them.
Because the apps are native and fast, they actually get used, and because they
get used, they are the most accurate picture of your work you have. mcp-things
turns that picture into something agents can read and act on.

<!-- BLOG: link the "Things as an operating system" post on casey.berlin/writings once it is live -->
