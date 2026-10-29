# Tools

mcp-things exposes 32 tools, grouped by the GTD stage they serve. Tool names
are kebab-case. Write tools change Things through its URL scheme; read tools
query the Things database directly.

- [Response shape](#response-shape)
- [Status filtering](#status-filtering)
- [Dates, reminders and repeats](#dates-reminders-and-repeats)
- [Deleting things](#deleting-things)
- [Resources and prompts](#resources-and-prompts)
- [GTD context tags](#gtd-context-tags)
- [Tool reference](#capture) (generated from the live schemas)
- [Removed tools](#removed-tools)

## Response shape

Every tool returns a human-readable text block and a JSON `structuredContent`
envelope, so clients can read fields without parsing prose:

```json
{
  "data": <typed payload | list | null>,
  "summary": "one-sentence headline",
  "meta": {"total_count": 12, "truncated": false, "...": "..."}
}
```

Payload types live in `src/things_mcp/models.py` (`Todo`, `Project`, `Area`,
`Tag`, `WriteResult`, `BulkResult`, `FocusResult`, `ReviewReport`,
`TriageInsights`, ...). Each tool publishes its `outputSchema` in `tools/list`.

Failures are MCP errors (`isError: true`); the envelope has no `ok` field.

Create tools read the new to-do back from the database to return its real
`thing_id`. A `null` `thing_id` means "created, not yet confirmed": Things
commits the row a moment after the URL opens, and the read-back window is
about 3.5 seconds.

If you used to regex the markdown body, read `structuredContent` instead. The
text block stays for text-only clients, but the envelope is the contract.

## Status filtering

`get-tasks`, `search-tasks`, `get-projects` and `get-areas` share one `status`
parameter: a list of `incomplete`, `completed`, `canceled` (a single value also
works), default `["incomplete"]`.

- `get-projects(status=["completed", "canceled"])` finds finished or abandoned projects.
- On `get-areas` it filters the projects and tasks that `include_items` embeds; areas have no status.
- On `get-tasks` the `view` picks the list and `status` filters within it. Without `status`,
  `view="logbook"` returns completed and canceled, `view="trash"` every status.
- `include_completed` is a deprecated alias for `status=["incomplete", "completed"]` and is
  ignored when `status` is set.

## Dates, reminders and repeats

Every `when` parameter takes `today`, `tomorrow`, `evening`, `anytime`,
`someday` or a `YYYY-MM-DD` date. Add `@HH:MM` for a reminder
(`2026-11-14@09:00`, `tomorrow@08:30`). A plain date keeps an existing
reminder; `anytime` and `someday` remove it.

`schedule-task` and `modify-task` accept a server-side `repeat` rule. The
server writes it to the to-do's notes as a visible `🔁 repeat:` line, because
Things offers no way to create a repeat rule from outside the app. A periodic
sweep creates the next occurrence once one is completed, including completions
you make in the Things app. Canceling an occurrence, or deleting the line, ends
the series.

## Deleting things

The Things URL scheme cannot delete a to-do. "Delete" means cancel:
`modify-task(canceled=true)` or `bulk-cancel`. Canceled items stay in the
Logbook, which matches GTD. Areas can be deleted with `delete-area`, which
refuses while the area still holds loose to-dos.

## Resources and prompts

- Resources: `things://inbox/count`, `things://today`, `things://stalled-projects`,
  `things://triage/stats`, `things://contexts`, `things://config`
- Prompts: `weekly-review`, `process-inbox-to-zero`, `plan-project`

## GTD context tags

The context-aware tools (`get-tasks`, `focus-mode`) work best with consistent tags:

```
Contexts: @computer, @phone, @office, @home, @errands, @anywhere
Energy:   high-energy, low-energy
Time:     5min, 15min, 30min, 1hr+
Status:   waiting-for
People:   @person-name (for agenda items)
```

Missing tags are created automatically when a write tool uses them.

<!-- GENERATED:tools -->

## Capture

### `capture-task`

Quick capture a task to Inbox for later processing.

*Use when:* Getting something out of your head quickly. Don't organize now.

| Parameter | Required | Description |
|---|---|---|
| `title` | yes | What needs to be done (required) |
| `notes` |  | Additional details (optional) |
| `tags` |  | Context tags like @computer, @phone (optional) |
| `when` |  | Optional schedule (today, tomorrow, evening, anytime, someday, or YYYY-MM-DD). If omitted, goes to inbox. Add @HH:MM for a reminder at that time (2026-11-14@09:00, tomorrow@08:30); a plain date keeps an existing reminder, anytime/someday removes it. |
| `checklist` |  | Checklist items (native, tickable sub-rows), in order (optional) |

## Clarify

### `process-inbox`

Process inbox items using GTD methodology.

*Use when:* Processing inbox during daily/weekly review.

| Parameter | Required | Description |
|---|---|---|
| `all` |  | If True, return all inbox items in compact format for bulk-triage. Default: False (one item at a time). |
| `limit` |  | Maximum items to return when all=True (default 50, max 200). |

### `convert-to-project`

Convert a task into a project when it requires multiple steps.

*Use when:* Realizing a task is actually a multi-step outcome.

| Parameter | Required | Description |
|---|---|---|
| `task_id` | yes | UUID of the task to convert |
| `first_action` |  | Title of the first next action (added before checklist items) |

## Organize

### `schedule-task`

Create a task with specific scheduling and organization.

*Use when:* You know when/where this task belongs.

| Parameter | Required | Description |
|---|---|---|
| `title` | yes | What needs to be done |
| `when` | yes | Schedule - today, tomorrow, evening, anytime, someday, or YYYY-MM-DD. Add @HH:MM for a reminder at that time (2026-11-14@09:00, tomorrow@08:30); a plain date keeps an existing reminder, anytime/someday removes it. |
| `deadline` |  | Hard deadline (YYYY-MM-DD) |
| `project` |  | Project name or UUID to add to |
| `area` |  | Area name or UUID |
| `context` |  | GTD context tags (e.g., ["@computer", "high-energy"]) |
| `checklist` |  | Subtasks/checklist items |
| `notes` |  | Additional notes |
| `repeat` |  | Make it a repeating to-do. This is a SERVER-SIDE repeat: Things has no API for repeat rules, so the rule is stored as a "🔁 repeat:" line in the notes and mcp-things creates the next occurrence (same title, notes, tags, checklist, project/area; the deadline keeps its offset from `when`) within ~10 minutes of this one being completed. Canceling or deleting an occurrence ends the series. Grammar: daily, weekly:mon[,thu], monthly:15, monthly:last, monthly:2nd-saturday, monthly:last-friday, every:14d, every:2w, every:3m, every:1y; append " after-completion" to count from the completion day instead of the schedule (default "fixed"). |

### `delegate-task`

Delegate a task and track it as 'Waiting For'.

*Use when:* You've handed off a task to someone else.

| Parameter | Required | Description |
|---|---|---|
| `task_id` |  | UUID of the task to delegate (preferred if known) |
| `task_title` |  | Title to search for (fuzzy match). If multiple match, returns list. |
| `delegated_to` |  | Person's name you're waiting on (required) |
| `follow_up_date` |  | When to follow up (YYYY-MM-DD) |
| `notes` |  | Notes about the delegation (e.g., "Emailed on Jan 20") |

### `defer-task`

Defer a task to a later time.

| Parameter | Required | Description |
|---|---|---|
| `task_id` |  | UUID of the task to defer (preferred if known) |
| `task_title` |  | Title to search for (fuzzy match). If multiple match, returns list. |
| `defer_to` |  | When - "someday", "tomorrow", "next_week", or YYYY-MM-DD (required). Add @HH:MM for a reminder at that time (2026-11-14@09:00, tomorrow@08:30); a plain date keeps an existing reminder, anytime/someday removes it. |
| `reason` |  | Why you're deferring (appended to notes) |

### `plan-project`

Create a project with initial tasks atomically.

*Use when:* Planning a multi-step outcome.

| Parameter | Required | Description |
|---|---|---|
| `title` | yes | Project title |
| `tasks` | yes | List of task objects - each with 'title' and optional 'when', 'notes', 'tags', 'deadline', 'checklist' (list of checklist item titles) |
| `notes` |  | Project notes |
| `when` |  | Project schedule |
| `deadline` |  | Project deadline |
| `area` |  | Area name to add to |

### `modify-task`

General task modification for updates not covered by specific tools.

| Parameter | Required | Description |
|---|---|---|
| `task_id` |  | UUID of the task to update (preferred if known) |
| `task_title` |  | Title to search for (fuzzy match). If multiple match, returns list. |
| `title` |  | New title (replaces existing) |
| `notes` |  | New notes (replaces existing) |
| `add_notes` |  | Notes to append (preserves existing) |
| `when` |  | New schedule (today, tomorrow, evening, anytime, someday, YYYY-MM-DD). Pass "none"/"clear"/"remove"/"null" to clear it. Add @HH:MM for a reminder at that time (2026-11-14@09:00, tomorrow@08:30); a plain date keeps an existing reminder, anytime/someday removes it. |
| `deadline` |  | New deadline (YYYY-MM-DD). Pass "none"/"clear"/"remove"/ "null" to clear an existing deadline. |
| `tags` |  | New tags (replaces existing) |
| `add_tags` |  | Tags to add (preserves existing) |
| `checklist` |  | New checklist items (replaces existing) |
| `add_checklist` |  | Checklist items to append (preserves existing) |
| `project` |  | Project name or UUID to move task to |
| `area` |  | Area name or UUID to move task to |
| `canceled` |  | Set to true to trash/cancel the task |
| `repeat` |  | Set a SERVER-SIDE repeat rule (same grammar as schedule-task, e.g. "monthly:2nd-saturday"); the rule goes into a "🔁 repeat:" notes line and mcp-things creates the next occurrence after this one is completed. Pass "none" to stop. Rejected for to-dos that Things already repeats natively. |

### `create-area`

Create a new area in Things, optionally with initial projects.

*Use when:* Setting up a new area of responsibility (e.g., Health, Finance, Work).

| Parameter | Required | Description |
|---|---|---|
| `name` | yes | Area name (e.g., "Health", "Side Projects") |
| `tags` |  | Optional tags to assign to the area |
| `projects` |  | Optional list of project names to create within the area |

## Reflect

### `daily-review`

Get a daily overview following GTD daily review.

*Use when:* Start of day, or asking "what do I need to do today?"

### `weekly-review`

Comprehensive GTD weekly review.

### `triage-insights`

Get insights into your inbox triage patterns.

*Use when:* Understanding capture and processing habits.

| Parameter | Required | Description |
|---|---|---|
| `days` |  | Number of days to analyze (default 7, 0 for all time) |
| `category` |  | Filter by category (repo-research, vague-capture, client-person, etc.) |
| `action` |  | Filter by action (completed, canceled, deferred-someday, delegated, etc.) |
| `show_trends` |  | Show week-over-week trends (4 weeks) |

## Engage

### `get-tasks`

Get tasks filtered by view, status, context, energy, and time available.

*Use when:* Choosing what to work on based on current context and constraints.

| Parameter | Required | Description |
|---|---|---|
| `view` |  | Task view - inbox, today, tomorrow, upcoming, anytime, someday, logbook, trash, deadlines |
| `context` |  | GTD context tag(s) to filter by (e.g., "@computer", "@phone") |
| `energy` |  | Energy level tag (e.g., "high-energy", "low-energy") |
| `time_available` |  | Time estimate tag (e.g., "5min", "15min", "30min", "1hr+") |
| `area` |  | Filter by area name or UUID |
| `project` |  | Filter by project name or UUID |
| `status` |  | Statuses to return: any of "incomplete", "completed", "canceled", as a list (a single value also works). ["completed", "canceled"] is "finished either way". Default ["incomplete"]. |
| `include_completed` |  | Deprecated, use status. True means status=["incomplete", "completed"]; ignored when status is set. |
| `limit` |  | Maximum number of tasks to return (default 50, max 200) |

### `focus-mode`

Get the single most important task to work on right now.

*Use when:* Feeling overwhelmed or asking "what should I do next?"

| Parameter | Required | Description |
|---|---|---|
| `context` |  | Current GTD context (e.g., "@computer", "@phone") |
| `energy` |  | Current energy level (e.g., "high-energy", "low-energy") |
| `time_available` |  | Available time (e.g., "5min", "15min", "30min") |

### `complete-task`

Mark a task as complete.

*Use when:* Finishing a task. Provide task_id if known, or task_title to search.

| Parameter | Required | Description |
|---|---|---|
| `task_id` |  | UUID of the task to complete (preferred if known) |
| `task_title` |  | Title to search for (fuzzy match). If multiple match, returns list. |
| `completion_notes` |  | Optional notes to append before completing |

## Utility

### `modify-project`

Update a project's properties.

*Use when:* Renaming, rescheduling, reassigning to an area, adding notes,

| Parameter | Required | Description |
|---|---|---|
| `name_or_uuid` | yes | Project name (case-insensitive) or UUID |
| `title` |  | New title |
| `notes` |  | New notes (replaces existing) |
| `prepend_notes` |  | Text to add before existing notes |
| `append_notes` |  | Text to add after existing notes |
| `when` |  | Schedule date (today, tomorrow, evening, anytime, someday, YYYY-MM-DD). Pass "none"/"clear"/"remove"/"null" to clear it. Add @HH:MM for a reminder at that time (2026-11-14@09:00, tomorrow@08:30); a plain date keeps an existing reminder, anytime/someday removes it. |
| `deadline` |  | Deadline date (YYYY-MM-DD). Pass "none"/"clear"/"remove"/ "null" to clear an existing deadline. |
| `tags` |  | Tags to set (replaces existing) |
| `add_tags` |  | Tags to add without replacing |
| `area` |  | Area name or UUID to move project to |
| `completed` |  | Mark as completed (Things 3 feature) |
| `canceled` |  | Mark as canceled (Things 3 feature) |

### `modify-area`

Rename an area or update its tags.

*Use when:* Renaming an area of focus/responsibility or changing its tags.

| Parameter | Required | Description |
|---|---|---|
| `name_or_uuid` | yes | Current area name (case-insensitive) or UUID |
| `new_name` |  | New name for the area |
| `tags` |  | Tags to set on the area |

### `delete-area`

Delete an area. Refuses if loose to-dos exist (Things trashes them).

*Use when:* Removing an area of responsibility that is no longer relevant.

| Parameter | Required | Description |
|---|---|---|
| `name_or_uuid` | yes | Area name (case-insensitive) or UUID |

### `merge-areas`

Move all contents from source area to target area, then delete source.

*Use when:* Two areas of responsibility are converging (e.g., merging

| Parameter | Required | Description |
|---|---|---|
| `source` | yes | Source area name or UUID (will be deleted) |
| `target` | yes | Target area name or UUID (will receive all items) |

### `search-tasks`

Search for tasks by keyword or filters.

*Use when:* Looking for a specific task or filtering by criteria.

| Parameter | Required | Description |
|---|---|---|
| `query` |  | Search text (matches title and notes) |
| `status` |  | Statuses to return: any of "incomplete", "completed", "canceled", as a list (a single value also works). ["completed", "canceled"] is "finished either way". Default ["incomplete"]. |
| `tag` |  | Filter by tag (context) |
| `area` |  | Filter by area of responsibility (name or UUID), NOT a built-in list. For Inbox/Today/Anytime/etc. use get-tasks(view=...). |
| `project` |  | Filter by project name or UUID (same as get-tasks) |
| `deadline` |  | Filter by deadline date |
| `limit` |  | Maximum results to return (default 20, max 200) |

### `get-projects`

Get projects from Things (open ones unless `status` says otherwise).

| Parameter | Required | Description |
|---|---|---|
| `include_items` |  | Include tasks within projects |
| `status` |  | Statuses to return: any of "incomplete", "completed", "canceled", as a list (a single value also works). ["completed", "canceled"] is "finished either way". Default ["incomplete"]. |

### `get-areas`

Get all areas from Things.

| Parameter | Required | Description |
|---|---|---|
| `include_items` |  | Include projects and tasks within areas |
| `status` |  | Statuses to return: any of "incomplete", "completed", "canceled", as a list (a single value also works). ["completed", "canceled"] is "finished either way". Default ["incomplete"]. |

### `get-project`

Get a single project with full detail by name or UUID.

*Use when:* You need full detail on a specific project — its tasks, notes,

| Parameter | Required | Description |
|---|---|---|
| `name_or_uuid` | yes | Project name (case-insensitive) or UUID |

### `get-area`

Get a single area with full detail by name or UUID.

*Use when:* Inspecting a specific area before modifying or deleting it,

| Parameter | Required | Description |
|---|---|---|
| `name_or_uuid` | yes | Area name (case-insensitive) or UUID |
| `include_items` |  | Include full project and to-do listings |

### `get-tags`

Get all tags.

| Parameter | Required | Description |
|---|---|---|
| `include_items` |  | Include items tagged with each tag |

### `show-in-app`

Open a specific item or list in the Things app.

| Parameter | Required | Description |
|---|---|---|
| `id` | yes | Item UUID, or list name: inbox, today, upcoming, anytime, someday, logbook, tomorrow, deadlines, repeating, all-projects, logged-projects |

### `get-cache-stats`

Get cache performance statistics.

## Batch

### `bulk-capture`

Create multiple inbox items in one call. Batch version of capture-task.

*Use when:* Capturing multiple items at once (meeting notes, braindump, etc.)

| Parameter | Required | Description |
|---|---|---|
| `items` | yes | List of items to capture (1-50). Each has title (required), notes, when, tags, deadline, checklist. |
| `default_when` |  | Default schedule for items without an explicit 'when' value. |

### `bulk-complete`

Mark multiple tasks complete in one call. Batch version of complete-task.

*Use when:* Completing several tasks at once (end-of-day cleanup, batch processing).

| Parameter | Required | Description |
|---|---|---|
| `task_ids` | yes | List of task UUIDs to complete (1-50). |

### `bulk-cancel`

Cancel multiple tasks in one call. Batch version of modify-task(canceled=True).

*Use when:* Canceling several tasks at once (cleanup, scope change).

| Parameter | Required | Description |
|---|---|---|
| `task_ids` | yes | List of task UUIDs to cancel (1-50). |

### `bulk-modify`

Apply the same modification to multiple tasks. Batch version of modify-task.

*Use when:* Moving, tagging, or rescheduling many tasks at once.

| Parameter | Required | Description |
|---|---|---|
| `task_ids` | yes | List of task UUIDs to modify (1-50). |
| `when` |  | Reschedule all tasks (today, tomorrow, evening, anytime, someday, or YYYY-MM-DD). Add @HH:MM for a reminder at that time (2026-11-14@09:00, tomorrow@08:30); a plain date keeps an existing reminder, anytime/someday removes it. |
| `add_tags` |  | Tags to add to all tasks (e.g. ["@computer"]). |
| `project` |  | Move all tasks to this project (name or UUID). Mutually exclusive with area. |
| `area` |  | Move all tasks to this area (name or UUID). Mutually exclusive with project. |

### `bulk-triage`

Process multiple inbox decisions in one call. Use after process-inbox(all=True).

*Use when:* You have reviewed all inbox items and want to submit all decisions at once.

| Parameter | Required | Description |
|---|---|---|
| `decisions` | yes | List of triage decisions (1-100). Each has task_id, action, and action-specific fields. |

<!-- /GENERATED:tools -->

## Removed tools

The CRUD-style tools of the original fork were replaced by GTD-native tools.
See [MIGRATION.md](MIGRATION.md) for details.

| Removed tool | Replacement |
|---|---|
| `get-inbox`, `get-today`, `get-upcoming`, `get-anytime`, `get-someday`, `get-logbook`, `get-trash` | `get-tasks(view=...)` |
| `get-todos` | `get-tasks()` |
| `get-tagged-items` | `get-tasks(context="tag-name")` |
| `get-recent` | `get-tasks(view="logbook")` |
| `search-todos`, `search-advanced`, `search-items` | `search-tasks` |
| `add-todo` | `capture-task` or `schedule-task` |
| `add-project` | `plan-project` |
| `update-todo` | `modify-task` |
| `update-project` | `modify-project` |
| `show-item` | `show-in-app` |
