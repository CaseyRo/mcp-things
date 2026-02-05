# URL Scheme Capability: Delta Specification

## ADDED Requirements

### Requirement: GTD Inbox Processing

The system SHALL provide a `process-inbox` tool that guides agents through GTD's Clarify phase.

The tool SHALL:

- Fetch the oldest unprocessed item from Inbox
- Present GTD decision tree context in the response
- Support follow-up actions: trash, defer to someday, schedule, delegate, convert to project

#### Scenario: Process inbox item

- **WHEN** agent calls `process-inbox`
- **THEN** returns oldest inbox item with metadata
- **AND** includes GTD guidance: "Is this actionable? If yes, is it a single action or project? If single action, can it be done in <2 minutes?"

#### Scenario: Empty inbox

- **WHEN** inbox is empty
- **THEN** returns success message: "Inbox is clear. GTD: mind like water achieved."

#### Scenario: Item requires project conversion

- **WHEN** agent determines item needs multiple steps
- **THEN** agent can follow up with `convert-to-project` tool

---

### Requirement: Convert Task to Project

The system SHALL provide a `convert-to-project` tool for transforming single tasks into multi-step projects.

Required: `task_id`
Optional: `first_action` (title of the first next action)

#### Scenario: Convert with first action

- **WHEN** agent calls `convert-to-project` with `task_id` and `first_action="Research options"`
- **THEN** project is created with original task's title and notes
- **AND** first action is created within project
- **AND** original task is deleted

#### Scenario: Convert without first action

- **WHEN** agent calls `convert-to-project` with only `task_id`
- **THEN** project is created
- **AND** warning returned: "Project has no next action. GTD requires every project to have a clear next step."

---

### Requirement: Context-First Task Retrieval

The system SHALL provide a `get-tasks` tool with GTD context as the primary filter.

Parameters:

- `view`: Optional. inbox, today, tomorrow, upcoming, anytime, someday, logbook, trash, deadlines
- `context`: Optional. Tag name(s) for GTD contexts (e.g., "@computer", "@errands")
- `energy`: Optional. Energy level tag (e.g., "high-energy", "low-energy")
- `time_available`: Optional. Time estimate tag (e.g., "5min", "30min", "1hr+")
- `area`: Optional. Area name or ID
- `project`: Optional. Project name or ID

#### Scenario: Filter by context

- **WHEN** agent calls `get-tasks` with `context="@computer"`
- **THEN** returns only tasks tagged with "@computer"
- **AND** tasks are from any view (anytime, today, etc.)

#### Scenario: Combined GTD filters

- **WHEN** agent calls `get-tasks` with `view="anytime"`, `context="@office"`, `energy="low-energy"`
- **THEN** returns available next actions for low-energy office work

#### Scenario: Waiting for context

- **WHEN** agent calls `get-tasks` with `context="waiting-for"`
- **THEN** returns all delegated items awaiting follow-up

---

### Requirement: Task Delegation (Waiting For)

The system SHALL provide a `delegate-task` tool implementing GTD's "Waiting For" pattern.

Required: `task_id`, `delegated_to` (person name)
Optional: `follow_up_date`, `notes`

Implementation:

- Add "waiting-for" tag to task
- Prepend "Waiting: {person} - " to title
- Append "[Delegated {date}] {notes}" to task notes
- Set deadline to follow_up_date if provided

#### Scenario: Delegate with follow-up

- **WHEN** agent calls `delegate-task` with `delegated_to="Sarah"` and `follow_up_date="2025-02-01"`
- **THEN** task title becomes "Waiting: Sarah - {original title}"
- **AND** task has "waiting-for" tag
- **AND** task deadline is 2025-02-01

#### Scenario: Delegate without follow-up

- **WHEN** agent calls `delegate-task` with only `delegated_to="Bob"`
- **THEN** task is tagged and annotated
- **AND** response notes: "No follow-up date set. Item will appear in weekly review."

---

### Requirement: GTD Daily Review

The system SHALL provide a `daily-review` tool returning a GTD-compliant daily overview.

Returns:

- Today's scheduled tasks (GTD "hard landscape")
- Overdue tasks requiring attention
- Inbox count (items awaiting clarification)
- Summary statistics

#### Scenario: Morning review

- **WHEN** agent calls `daily-review`
- **THEN** response includes categorized sections
- **AND** summary: "5 tasks today, 2 overdue, 8 in inbox to process"

#### Scenario: Clear day

- **WHEN** no overdue tasks and empty inbox
- **THEN** response indicates readiness: "Hard landscape clear. 3 tasks scheduled for today. Inbox is empty."

---

### Requirement: GTD Weekly Review

The system SHALL provide a `weekly-review` tool implementing GTD's weekly review checklist.

Returns:

- **Stalled projects**: Active projects with no available next action
- **Waiting for items**: Delegated tasks, especially those past follow-up date
- **Someday/Maybe review**: Items to reconsider activating
- **Completed this week**: Recent accomplishments for closure
- **Inbox status**: Count of items awaiting processing

#### Scenario: Detect stalled project

- **WHEN** project "Kitchen Renovation" has no tasks with status "anytime" or "today"
- **THEN** weekly review lists it under "Stalled Projects"
- **AND** suggests: "Project 'Kitchen Renovation' has no next action. Add one to make progress."

#### Scenario: Overdue waiting-for

- **WHEN** delegated task has follow_up_date in the past
- **THEN** weekly review highlights: "Waiting: Sarah - Review proposal (follow-up was Jan 15)"

#### Scenario: Someday reconsideration

- **WHEN** task has been in Someday for >30 days
- **THEN** weekly review suggests: "Consider: 'Learn Spanish' has been in Someday for 45 days. Activate or remove?"

---

### Requirement: GTD Focus Mode

The system SHALL provide a `focus-mode` tool that selects the single most important task.

Optional parameters:

- `context`: Current GTD context (e.g., "@computer")
- `energy`: Current energy level
- `time_available`: Available time window

Priority order:

1. Overdue tasks with deadline (oldest first)
2. Today's tasks with deadline (earliest deadline first)
3. Today's tasks without deadline
4. Anytime tasks (next actions)

#### Scenario: Context-aware focus

- **WHEN** agent calls `focus-mode` with `context="@computer"` and `time_available="15min"`
- **THEN** returns single task matching criteria
- **AND** explains: "Selected: 'Reply to email' - matches @computer context, estimated 10min, due today"

#### Scenario: No matching tasks

- **WHEN** no tasks match the provided filters
- **THEN** response suggests: "No tasks match @errands with 5min available. Try a different context or check if tasks need context tags."

---

### Requirement: Quick Capture

The system SHALL provide a `capture-task` tool for frictionless GTD capture.

Required: `title`
Optional: `notes`, `tags`

Always creates in Inbox (never scheduled).

#### Scenario: Minimal capture

- **WHEN** agent calls `capture-task` with only `title="Call dentist"`
- **THEN** task created in Inbox
- **AND** response: "Captured to Inbox. Use process-inbox or schedule-task to clarify and organize."

---

### Requirement: Scheduled Task Creation

The system SHALL provide a `schedule-task` tool for creating organized tasks.

Required: `title`, `when` (or `project`)
Optional: `deadline`, `project`, `area`, `context` (tags), `checklist`, `notes`

When parameter supports: today, tomorrow, evening, anytime, someday, dates, datetimes

#### Scenario: Schedule with context

- **WHEN** agent calls `schedule-task` with `title="Review PR"`, `when="today"`, `context="@computer"`
- **THEN** task created for today with "@computer" tag

#### Scenario: Add to project

- **WHEN** agent calls `schedule-task` with `project="Website Launch"`
- **THEN** task created within project as next action

---

### Requirement: GTD-Aware Deferral

The system SHALL provide a `defer-task` tool distinguishing GTD deferral types.

Required: `task_id`, `defer_to`
Optional: `reason`

`defer_to` values:

- `someday`: Move to Someday/Maybe for incubation (indefinite)
- `tomorrow`, `next_week`, date: Tickler/scheduled (specific date)

#### Scenario: Incubate to someday

- **WHEN** agent calls `defer-task` with `defer_to="someday"`
- **THEN** task moved to Someday list
- **AND** response notes: "Moved to Someday/Maybe for incubation. Will appear in weekly review."

#### Scenario: Tickler to future date

- **WHEN** agent calls `defer-task` with `defer_to="2025-03-01"` and `reason="Conference prep"`
- **THEN** task scheduled for March 1
- **AND** reason appended to notes

---

### Requirement: Atomic Project Planning

The system SHALL provide a `plan-project` tool for creating projects with initial tasks.

Required: `title`, `tasks` (array)
Optional: `area`, `deadline`, `notes`, `when`

Task objects: `{title, notes?, when?, deadline?, tags?, heading?}`

#### Scenario: Project with next action

- **WHEN** agent creates project with tasks including one with `when="anytime"`
- **THEN** project created with clear next action available

#### Scenario: Project without next action

- **WHEN** all tasks have future dates or no dates
- **THEN** project created
- **AND** warning: "Project has no immediate next action. GTD: ensure at least one task is available to work on now."

---

### Requirement: Task Completion with Notes

The system SHALL provide a `complete-task` tool with fuzzy matching.

Required: `task_id` OR `task_title`
Optional: `completion_notes`

#### Scenario: Complete by title

- **WHEN** agent calls `complete-task` with `task_title="groceries"`
- **AND** one task matches
- **THEN** task marked complete

#### Scenario: Ambiguous title

- **WHEN** multiple tasks match title
- **THEN** returns list: "Found 3 tasks matching 'meeting'. Specify: [list with IDs]"
- **AND** no task completed

---

### Requirement: Actionable Error Messages

Error messages SHALL include GTD-aware recovery guidance.

#### Scenario: Stalled project warning

- **WHEN** operation reveals project with no next action
- **THEN** message includes: "Project has no next action. Use schedule-task to add one, or convert-to-project if this task should become a project."

#### Scenario: Inbox not cleared

- **WHEN** weekly review called with non-empty inbox
- **THEN** includes: "Inbox has 5 items. GTD weekly review recommends processing to zero. Use process-inbox to clarify each item."

---

### Requirement: Agent-Native Tool Descriptions

Each tool description SHALL include GTD context and routing guidance.

Pattern:

```
[Primary function in one sentence.]

GTD Stage: [Capture | Clarify | Organize | Reflect | Engage]
Use when: [specific user intents]
Instead use: [alternative tool] if [different situation]
```

#### Scenario: Clear GTD stage indication

- **WHEN** agent reads tool descriptions
- **THEN** can map user request to appropriate GTD stage and tool

---

## MODIFIED Requirements

### Requirement: Search Consolidation

The system SHALL provide a unified `search-tasks` tool.

Required: `query` OR at least one filter
Optional: `status`, `start_date`, `deadline`, `tag`, `area`, `type`

#### Scenario: Search by context tag

- **WHEN** agent calls `search-tasks` with `tag="@phone"`
- **THEN** returns all tasks with "@phone" context

---

## REMOVED Requirements

### Requirement: Individual View Tools

**Reason:** Consolidated into `get-tasks` with view and context parameters.
**Migration:** `get-inbox` → `get-tasks(view="inbox")`

Removed tools:

- `get-inbox`, `get-today`, `get-upcoming`, `get-anytime`, `get-someday`, `get-logbook`, `get-trash`

### Requirement: Separate Search Tools

**Reason:** Consolidated into `search-tasks`.
**Migration:** `search-todos` → `search-tasks(query="...")`

Removed tools:

- `search-todos`, `search-advanced`
