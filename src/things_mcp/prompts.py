"""MCP prompts: guided, selectable GTD workflows.

These wrap the server's signature multi-step rituals — the weekly review, inbox
processing to zero, and project planning — into first-class, discoverable
``@mcp.prompt`` entries. The narrative guidance previously lived only in tool
docstrings and server instructions; exposing it as prompts lets a client surface
the GTD ritual as a single click and have the model walk it step by step using
the existing tools.

Each prompt returns a plain string, which FastMCP delivers as the initial user
message of the workflow.
"""

from __future__ import annotations

from fastmcp import FastMCP


def register_prompts(mcp: FastMCP) -> None:
    """Register guided GTD-workflow prompts with the server."""

    @mcp.prompt(
        name="weekly-review",
        title="Run a GTD Weekly Review",
        description=(
            "Guide me through David Allen's weekly review: get current, get "
            "clear, get creative. Uses weekly-review, process-inbox, and the "
            "bulk-* tools."
        ),
        tags={"reflect", "workflow"},
    )
    def weekly_review_prompt() -> str:
        return (
            "Walk me through a complete GTD weekly review for my Things 3 setup. "
            "Follow these steps and use the matching tools:\n\n"
            "1. **Get current** — Call `weekly-review` to surface stalled "
            "projects, waiting-for items, someday/maybe, and what I completed.\n"
            "2. **Get clear** — If the inbox is not empty, call "
            "`process-inbox(all=True)`, then propose a single `bulk-triage` call "
            "with a GTD decision (do / defer / delegate / delete / assign) for "
            "each item. Show me the plan before executing.\n"
            "3. **Get projects moving** — For every stalled project, suggest a "
            "concrete next action and offer to add it.\n"
            "4. **Review the horizons** — Walk the someday/maybe list and ask "
            "which items should become active now.\n"
            "5. **Wrap up** — Summarise what changed and what still needs my "
            "attention.\n\n"
            "Pause for my confirmation before any write that completes, cancels, "
            "or reschedules tasks."
        )

    @mcp.prompt(
        name="process-inbox-to-zero",
        title="Process the Inbox to Zero",
        description=(
            "Clarify every inbox item with the GTD decision tree and clear the "
            "inbox in one batch. Uses process-inbox and bulk-triage."
        ),
        tags={"clarify", "workflow"},
    )
    def process_inbox_prompt() -> str:
        return (
            "Help me process my Things inbox to zero using the GTD clarify "
            "workflow:\n\n"
            "1. Call `process-inbox(all=True)` to load every inbox item with its "
            "suggested category.\n"
            "2. For each item, apply the GTD decision tree:\n"
            "   - Not actionable → **delete** (cancel) or **defer** to "
            "someday/maybe.\n"
            "   - Actionable, < 2 minutes → flag it so I can **do it now**.\n"
            "   - Actionable, mine, later → **schedule** or **defer** with a "
            "`when`.\n"
            "   - Actionable, someone else's → **delegate** (capture who).\n"
            "   - Multi-step outcome → **assign** to a project.\n"
            "3. Assemble one `bulk-triage` call with a decision per item and show "
            "it to me for approval before executing.\n"
            "4. After triage, confirm the inbox is empty and report the action "
            "breakdown.\n\n"
            "Ask me whenever an item's correct decision is genuinely ambiguous."
        )

    @mcp.prompt(
        name="plan-project",
        title="Plan a New Project",
        description=(
            "Turn a desired outcome into a Things project with a clean next "
            "action and supporting tasks. Uses plan-project."
        ),
        tags={"organize", "workflow"},
    )
    def plan_project_prompt(outcome: str) -> str:
        return (
            f"I want to plan a project for this outcome: {outcome}\n\n"
            "Apply GTD natural planning:\n"
            "1. Restate the **successful outcome** in one sentence (what 'done' "
            "looks like).\n"
            "2. Brainstorm the concrete tasks needed to get there.\n"
            "3. Identify the single **next action** — the very next physical, "
            "visible step — and put it first.\n"
            "4. Suggest a GTD context tag (@computer, @phone, …) for each task "
            "and an area of focus for the project.\n"
            "5. Show me the proposed project and task list, then call "
            "`plan-project` to create it atomically once I approve."
        )
