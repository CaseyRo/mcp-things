# Change: Redesign MCP Tools for GTD-Native Agent Experience

## Why

The current Things MCP server exposes tools that mirror REST/CRUD patterns rather than GTD workflows. This causes several problems:

1. **Missing "Clarify" Stage**: GTD's critical second phase (processing inbox items into actionable next actions) has no tool support. Users can capture and schedule, but the decision tree for processing is absent.

2. **Contexts are Invisible**: GTD relies heavily on contexts (@Computer, @Office, @Errands) to filter tasks during the Engage phase. Our tools treat tags as an afterthought rather than a primary filter.

3. **No "Waiting For" Support**: Delegation tracking is a core GTD pattern with no semantic tool. Things uses tags for this, but the agent has no way to understand the workflow.

4. **Stalled Projects Undetected**: GTD requires every project to have a clear "next action." Our `weekly-review` doesn't identify projects with no active tasks.

5. **Tool Sprawl**: 7 nearly-identical `get-*` tools flood the LLM's context window instead of one intelligent tool.

Additionally, the URL scheme implementation is missing features documented in the [official Things documentation](https://culturedcode.com/things/support/articles/2803573/).

## GTD Stage Mapping

| GTD Stage | Current Support | Proposed Tools |
|-----------|----------------|----------------|
| **Capture** | `add-todo` ✓ | `capture-task` (refined) |
| **Clarify** | ❌ Missing | `process-inbox` (NEW) |
| **Organize** | Partial (`update-todo`) | `schedule-task`, `delegate-task`, `convert-to-project` |
| **Reflect** | Partial (`get-*` views) | `daily-review`, `weekly-review` (GTD-aware) |
| **Engage** | ❌ Missing | `get-tasks` (context-first), `focus-mode` |

## What Changes

### Part 1: GTD Workflow Tools

**Capture Stage**
- `capture-task`: Quick inbox capture, minimal friction (exists, refine description)

**Clarify Stage (NEW)**
- `process-inbox`: Fetch oldest inbox item, present GTD decision tree to agent:
  1. Is it actionable?
  2. If no → Trash, Someday/Maybe, or Reference (notes)
  3. If yes → Single action or Project?
  4. If single action → <2 min? Do now. >2 min? Delegate or Defer
  5. Guides agent through proper GTD processing

**Organize Stage**
- `schedule-task`: Create with date/project/context (enhanced with context awareness)
- `delegate-task`: Set "Waiting For" state (tag + annotation + follow-up date)
- `convert-to-project`: Transform inbox item into project with initial next action
- `defer-task`: Distinct handling for "Tickler" (future date) vs "Someday/Maybe" (incubate)

**Reflect Stage**
- `daily-review`: Today's calendar + available Next Actions by context
- `weekly-review`: GTD-compliant review including:
  - Stalled projects (no next action)
  - Overdue waiting-for items
  - Someday/Maybe items to reconsider
  - Completed items for closure

**Engage Stage**
- `get-tasks`: Primary filter by **context (tags)**, then view
- `focus-mode`: Single most important task considering context, energy, time

### Part 2: Context-First Design

GTD contexts map to Things tags. Tools should make context filtering primary:

```python
# Current: Time-centric
get_tasks(view="today")

# Proposed: Context-first (GTD pattern)
get_tasks(context="@computer", energy="high", time_available="30m")
get_tasks(view="anytime", context="@errands")  # "What can I do while out?"
```

**Recommended Tag Structure** (documented for users):
- Contexts: `@computer`, `@phone`, `@office`, `@home`, `@errands`, `@anywhere`
- Energy: `high-energy`, `low-energy`
- Time: `5min`, `15min`, `30min`, `1hr+`
- Status: `waiting-for`
- People: `@person-name` (for agendas/delegation)

### Part 3: Waiting For Workflow

Things lacks native delegation, but GTD requires it. Implement via convention:

```python
delegate_task(
    task_id="abc123",
    delegated_to="Sarah",
    follow_up_date="2025-02-01",  # Optional
    notes="Emailed on Jan 20"
)
# Results in:
# - Tag: "waiting-for" added
# - Title prepended: "Waiting: Sarah - "
# - Notes appended: "[Delegated Jan 25] Emailed on Jan 20"
# - Deadline set to follow_up_date if provided
```

### Part 4: Stalled Project Detection

GTD principle: Every project needs a clear next action. `weekly-review` must detect:

```python
# Pseudocode for weekly_review()
projects = things.projects(status="active")
for project in projects:
    tasks = things.todos(project=project.uuid, status="incomplete")
    anytime_tasks = [t for t in tasks if t.when == "anytime"]
    if len(anytime_tasks) == 0:
        stalled_projects.append(project)
        # "Project 'Kitchen Renovation' has no next action. Consider adding one."
```

### Part 5: Tool Consolidation

| Current (CRUD) | Proposed (GTD Intent) |
|----------------|----------------------|
| 7 `get-*` tools | 1 `get-tasks(view, context, energy, time)` |
| `add-todo` | `capture-task` (inbox) / `schedule-task` (organized) |
| `update-todo(completed=true)` | `complete-task` |
| `update-todo(when=someday)` | `defer-task(to="someday")` (incubate) |
| `update-todo(when=date)` | `defer-task(to="2025-02-01")` (tickler) |
| — | `delegate-task` (waiting for) |
| — | `process-inbox` (clarify) |
| — | `convert-to-project` (multi-step outcome) |
| `add-project` | `plan-project` (atomic with tasks) |

### Part 6: URL Scheme Feature Gaps

Required for GTD tools:
- `append-notes`: For delegation annotations
- `prepend-notes`: For "Waiting: Person -" title patterns (or title modification)
- JSON bulk API: For atomic `plan-project` creation
- Extended tag operations: `add-tags` without replacing

## Impact

- **Affected code**: `src/things_mcp/fast_server.py`, `src/things_mcp/url_scheme.py`
- **Breaking changes**: Yes - tool names change. Deprecation period with aliases.
- **New conventions**: Documented tag structure for GTD contexts
- **Dependencies**: None

## Tool Count Evolution

| Category | Current | Proposed |
|----------|---------|----------|
| Capture | 2 | 1 (`capture-task`) |
| Clarify | 0 | 1 (`process-inbox`) |
| Organize | 2 | 4 (`schedule-task`, `delegate-task`, `defer-task`, `convert-to-project`) |
| Reflect | 0 | 2 (`daily-review`, `weekly-review`) |
| Engage | 9 | 3 (`get-tasks`, `focus-mode`, `complete-task`) |
| Projects | 2 | 2 (`plan-project`, `modify-project`) |
| Utility | 5 | 2 (`get-tags`, `search-tasks`) |
| **Total** | **20** | **15** |

Fewer tools with GTD-aligned intent = better agent routing for productivity workflows.

## References

- [GTD Methodology - David Allen](https://gettingthingsdone.com/)
- [GTD with Things 3 - Johnny Chadda](https://johnny.chadda.se/getting-things-done-with-things-3/)
- [Things URL Scheme Documentation](https://culturedcode.com/things/support/articles/2803573/)
- [GTD Forums - Waiting For in Things 3](https://forum.gettingthingsdone.com/threads/gtd-how-do-you-do-waiting-for-with-things-3.17049/)
