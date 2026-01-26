# Design: GTD-Native MCP Tools for Things 3

## Context

MCP servers designed for LLM agents should not mirror REST APIs. The fundamental difference:
- **REST API**: Developer knows exactly what endpoint to call
- **MCP Tools**: LLM is trying to figure out *how* to solve a problem

More importantly, Things 3 is designed around GTD (Getting Things Done) methodology. Tools should align with GTD's five stages:

1. **Capture**: Collect what has your attention
2. **Clarify**: Process what each item means
3. **Organize**: Put items where they belong
4. **Reflect**: Review frequently (daily/weekly)
5. **Engage**: Simply do

Current implementation exposes 20 CRUD-style tools that don't map to these stages, causing poor LLM routing and missing critical workflows like "Clarify" and "Reflect".

**Key Insight from GTD:**
> "Your head's a crappy office." — David Allen

The tools should help the agent externalize thinking into Things, then guide proper GTD processing.

## Goals / Non-Goals

### Goals
- Map every tool to a GTD stage for clear LLM routing
- Support the complete GTD workflow including Clarify phase
- Make GTD contexts (tags) a first-class filter
- Detect GTD anti-patterns (stalled projects, unprocessed inbox)
- Reduce tool count while increasing GTD coverage

### Non-Goals
- Full backward compatibility (will provide migration period)
- Exposing every URL scheme parameter
- Implementing Things features that don't exist (native delegation, repeating task editing)
- Replacing a human GTD practice (tools support, not replace)

## Decisions

### Decision 1: Tools Map to GTD Stages

**What:** Every tool explicitly belongs to a GTD stage.

| GTD Stage | Tools |
|-----------|-------|
| Capture | `capture-task` |
| Clarify | `process-inbox`, `convert-to-project` |
| Organize | `schedule-task`, `delegate-task`, `defer-task`, `plan-project` |
| Reflect | `daily-review`, `weekly-review` |
| Engage | `get-tasks`, `focus-mode`, `complete-task` |

**Why:**
- LLMs can route based on user intent → GTD stage → appropriate tool
- Tool descriptions include "GTD Stage: X" for clarity
- Covers workflows current implementation ignores entirely (Clarify, Reflect)

### Decision 2: Implement GTD Clarify with `process-inbox`

**What:** A tool that fetches one inbox item and provides GTD decision guidance.

```python
async def process_inbox() -> str:
    """Process the oldest inbox item using GTD methodology.

    GTD Stage: Clarify
    Use when: Processing inbox during daily/weekly review
    Returns: Oldest inbox item with decision guidance

    The GTD clarify questions:
    1. Is this actionable?
       - No → Trash, Someday/Maybe, or Reference
       - Yes → Continue...
    2. Is it a single action or multi-step project?
       - Project → Use convert-to-project
       - Single action → Continue...
    3. Can it be done in <2 minutes?
       - Yes → Do it now
       - No → Delegate (delegate-task) or Defer (schedule-task)
    """
    inbox_items = things.inbox()
    if not inbox_items:
        return "Inbox is clear. GTD: mind like water achieved."

    item = inbox_items[0]  # Oldest first
    return format_with_gtd_guidance(item)
```

**Why:**
- GTD Clarify is completely missing from current implementation
- The 2-minute rule is core GTD but impossible without tool support
- Guides agent through proper processing rather than ad-hoc organizing

### Decision 3: Context-First Task Retrieval

**What:** `get-tasks` uses GTD context (tags) as the primary filter, not time views.

```python
async def get_tasks(
    view: Optional[str] = None,  # inbox, today, anytime, etc.
    context: Optional[Union[str, List[str]]] = None,  # "@computer", "@phone"
    energy: Optional[str] = None,  # "high-energy", "low-energy"
    time_available: Optional[str] = None,  # "5min", "30min", "1hr+"
    area: Optional[str] = None,
    project: Optional[str] = None
) -> str:
    """Get tasks filtered by context, energy, and time available.

    GTD Stage: Engage
    GTD guidance: Context is your FIRST filter when choosing what to do.

    Examples:
    - get_tasks(context="@computer") - What can I do at my desk?
    - get_tasks(context="@errands") - What can I do while out?
    - get_tasks(view="anytime", energy="low-energy") - Easy wins when tired
    """
```

**Why:**
- GTD: "Context is always your first limitation when choosing what to do"
- Current time-first design (`get-today`, `get-anytime`) ignores this
- Supports GTD questions like "I have 15 minutes at my computer, what should I do?"

### Decision 4: Waiting For via Convention

**What:** `delegate-task` implements GTD's "Waiting For" pattern using Things tags and title conventions.

Things 3 lacks native delegation tracking. We implement via convention:

```python
async def delegate_task(
    task_id: str,
    delegated_to: str,
    follow_up_date: Optional[str] = None,
    notes: Optional[str] = None
) -> str:
    # Implementation:
    # 1. Add "waiting-for" tag
    # 2. Prepend "Waiting: {person} - " to title
    # 3. Append "[Delegated {date}] {notes}" to notes
    # 4. Set deadline to follow_up_date if provided
```

**Why:**
- Delegation tracking is core GTD but missing from current tools
- Convention matches common Things 3 GTD user practices
- `waiting-for` tag enables filtering: `get-tasks(context="waiting-for")`
- Weekly review can surface overdue follow-ups

### Decision 5: Stalled Project Detection in Weekly Review

**What:** `weekly-review` identifies projects with no available next action.

```python
async def weekly_review() -> str:
    # Check for stalled projects
    projects = things.projects()
    for project in projects:
        if project['status'] != 'active':
            continue
        tasks = things.todos(project=project['uuid'])
        # A project is stalled if it has no "anytime" or "today" tasks
        available_tasks = [t for t in tasks
                          if t['status'] == 'incomplete'
                          and t.get('start') in (None, 'anytime', 'today')]
        if len(available_tasks) == 0:
            stalled_projects.append(project)
```

**Why:**
- GTD: "Every project needs a clear next action"
- Stalled projects are a top GTD failure mode
- Human GTD practitioners check this weekly; agent should surface it

### Decision 6: Distinguish Someday vs Tickler in Deferral

**What:** `defer-task` description clearly distinguishes GTD concepts.

```python
async def defer_task(
    task_id: str,
    defer_to: str,  # "someday" | "tomorrow" | "next_week" | date
    reason: Optional[str] = None
) -> str:
    """Defer a task to a later time.

    GTD Stage: Organize

    IMPORTANT - GTD distinguishes two types of deferral:
    - defer_to="someday" → Someday/Maybe list (indefinite incubation)
    - defer_to=date → Tickler file (will reappear on that date)

    Use "someday" for: "I might want to do this someday"
    Use a date for: "I can't/won't do this until that date"
    """
```

**Why:**
- Current `defer-task` doesn't explain the semantic difference
- Users/agents confuse "someday" (incubation) with scheduling
- GTD treats these as fundamentally different workflows

### Decision 7: Recommended Tag Structure

**What:** Document a recommended GTD tag structure for Things users.

```
Contexts (location/tool):
- @computer, @phone, @office, @home, @errands, @anywhere

Energy levels:
- high-energy, low-energy

Time estimates:
- 5min, 15min, 30min, 1hr+

Status:
- waiting-for

People (for agendas):
- @person-name
```

**Why:**
- Tools filter by these tags; users need consistent naming
- GTD contexts are useless without user adoption
- Document in CLAUDE.md and tool descriptions

## Risks / Trade-offs

### Risk: Users Don't Use GTD Tag Conventions
- **Risk:** `get-tasks(context="@computer")` returns nothing if user doesn't tag
- **Mitigation:** Document conventions, surface untagged tasks in review tools
- **Trade-off:** Can't force GTD compliance, but can encourage it

### Risk: Stalled Project Detection Is Opinionated
- **Risk:** Some projects legitimately have all future-dated tasks
- **Mitigation:** Report as "stalled" with explanation, don't auto-fix
- **Trade-off:** May produce false positives for legitimate cases

### Risk: Breaking Existing Integrations
- **Risk:** Claude Desktop configs reference `get-inbox` not `get-tasks(view="inbox")`
- **Mitigation:** Deprecation aliases for 2 versions
- **Trade-off:** Churn for better long-term design

### Risk: process-inbox Is Too Prescriptive
- **Risk:** GTD decision tree may not fit all users
- **Mitigation:** Guidance is in response text, not enforced in code
- **Trade-off:** GTD-aligned users benefit; others can ignore guidance

## Things 3 Specific Considerations

### What Things 3 Does Well for GTD
- Inbox → Capture
- Today/Anytime/Someday → Next Actions / Someday-Maybe
- Areas → Areas of Focus (GTD Horizons)
- Projects → Multi-step outcomes
- Upcoming → Tickler/Scheduled
- Logbook → Completed items for review

### What Things 3 Lacks
- Native delegation/Waiting For tracking (→ we use tags)
- Convert task to project (→ we simulate: create project, move notes, delete task)
- Energy/time estimate fields (→ we use tags)
- Agenda views by person (→ we use `@person` tags)
- Built-in review scheduling (→ we provide review tools)

### URL Scheme Requirements for GTD Tools

The following URL scheme features are required:
- `append-notes`: For delegation annotations
- `add-tags`: For adding waiting-for without replacing existing tags
- JSON bulk API: For atomic `plan-project` creation
- Title modification: For "Waiting: Person - " prefix

## Open Questions

1. **Should `process-inbox` auto-delete trash items?**
   - Safer to return guidance and let agent/user decide
   - Decision: No auto-actions, only guidance

2. **How strict should stalled project detection be?**
   - Projects with only future-dated tasks: stalled or legitimate?
   - Decision: Report all, let user judge

3. **Should we create tags automatically?**
   - Current `ensure_tags_exist()` does this
   - Decision: Yes, maintain for GTD context tags

4. **MCP Resources for read-only GTD data?**
   - Could expose `inbox://count` as a Resource
   - Decision: Defer to future iteration, start with tools

## References

- [GTD Methodology - David Allen](https://gettingthingsdone.com/)
- [GTD with Things 3 - Johnny Chadda](https://johnny.chadda.se/getting-things-done-with-things-3/)
- [GTD Forums - Waiting For in Things 3](https://forum.gettingthingsdone.com/threads/gtd-how-do-you-do-waiting-for-with-things-3.17049/)
- [Things URL Scheme](https://culturedcode.com/things/support/articles/2803573/)
- [Todoist GTD Guide](https://www.todoist.com/productivity-methods/getting-things-done)
