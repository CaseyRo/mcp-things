# Tasks: Redesign MCP Tools for GTD-Native Agent Experience

## 1. GTD Clarify Stage (NEW)

### 1.1 Process Inbox Tool

- [ ] 1.1.1 Create `process-inbox` tool that fetches oldest unprocessed inbox item
- [ ] 1.1.2 Return item with GTD decision tree prompts in description
- [ ] 1.1.3 Include "Is this actionable?" as first decision point
- [ ] 1.1.4 Include "Can it be done in <2 minutes?" for quick actions
- [ ] 1.1.5 Include "Is this a single action or multi-step project?" branching
- [ ] 1.1.6 Description: "Process one inbox item using GTD methodology. Returns the oldest item with decision guidance. Use this during daily/weekly review to work through the inbox systematically."
- [ ] 1.1.7 Write tests for processing logic

### 1.2 Convert to Project Tool

- [ ] 1.2.1 Create `convert-to-project` tool
- [ ] 1.2.2 Accept task_id and optional first_action title
- [ ] 1.2.3 Implement: Create project with task's title/notes, create first action, delete original task
- [ ] 1.2.4 Description: "Convert a task into a project when it requires multiple steps. GTD: any outcome requiring >1 action is a project. Provide first_action to define the immediate next step."
- [ ] 1.2.5 Write tests

## 2. GTD Context-First Design

### 2.1 Unified Get Tasks Tool (Context-Aware)

- [ ] 2.1.1 Create `get-tasks` tool with context as primary filter
- [ ] 2.1.2 Parameters: view, context (tag), energy, time_available, area, project
- [ ] 2.1.3 Support multiple contexts: `context=["@computer", "@office"]`
- [ ] 2.1.4 Add energy filter mapping to energy tags
- [ ] 2.1.5 Add time_available filter mapping to time tags
- [ ] 2.1.6 Description: "Get tasks filtered by context, energy, and time available. GTD: context is your first filter when choosing what to do. Use '@computer' when at your desk, '@errands' when going out, '@phone' for calls."
- [ ] 2.1.7 Deprecate individual `get-inbox`, `get-today`, etc. tools
- [ ] 2.1.8 Write tests for all filter combinations

### 2.2 Document Recommended Tag Structure

- [ ] 2.2.1 Create GTD tag structure documentation
- [ ] 2.2.2 Contexts: @computer, @phone, @office, @home, @errands, @anywhere
- [ ] 2.2.3 Energy: high-energy, low-energy
- [ ] 2.2.4 Time: 5min, 15min, 30min, 1hr+
- [ ] 2.2.5 Status: waiting-for
- [ ] 2.2.6 People: @person-name pattern for agendas
- [ ] 2.2.7 Add to CLAUDE.md and tool descriptions

## 3. GTD Waiting For (Delegation)

### 3.1 Delegate Task Tool

- [ ] 3.1.1 Create `delegate-task` tool
- [ ] 3.1.2 Required: task_id, delegated_to (person name)
- [ ] 3.1.3 Optional: follow_up_date, notes
- [ ] 3.1.4 Implementation: Add "waiting-for" tag
- [ ] 3.1.5 Implementation: Prepend "Waiting: {person} - " to title
- [ ] 3.1.6 Implementation: Append "[Delegated {date}] {notes}" to notes
- [ ] 3.1.7 Implementation: Set deadline to follow_up_date if provided
- [ ] 3.1.8 Description: "Delegate a task and track it as 'Waiting For'. GTD: items you're waiting on others to complete. The task stays visible for follow-up during weekly review."
- [ ] 3.1.9 Write tests

### 3.2 Get Waiting For Items

- [ ] 3.2.1 Ensure `get-tasks` can filter by `context="waiting-for"`
- [ ] 3.2.2 Add `get-tasks(context="waiting-for")` example to description
- [ ] 3.2.3 Weekly review should automatically surface waiting-for items

## 4. GTD Reflect Stage (Reviews)

### 4.1 Daily Review Tool

- [ ] 4.1.1 Create `daily-review` tool
- [ ] 4.1.2 Return: Today's scheduled tasks (hard landscape)
- [ ] 4.1.3 Return: Overdue tasks requiring attention
- [ ] 4.1.4 Return: Inbox count (items awaiting clarification)
- [ ] 4.1.5 Return: Available next actions by context (optional summary)
- [ ] 4.1.6 Include summary: "5 tasks today, 2 overdue, 8 in inbox to process"
- [ ] 4.1.7 Description: "Get a daily overview following GTD daily review. Shows your 'hard landscape' (scheduled items) plus overdue items. Start here each morning or when asking 'what do I need to do today?'"
- [ ] 4.1.8 Write tests

### 4.2 Weekly Review Tool (GTD-Compliant)

- [ ] 4.2.1 Create `weekly-review` tool with GTD weekly review structure
- [ ] 4.2.2 Return: Stalled projects (active projects with no next action)
- [ ] 4.2.3 Return: Waiting-for items (especially overdue follow-ups)
- [ ] 4.2.4 Return: Someday/Maybe items to reconsider
- [ ] 4.2.5 Return: Recently completed items (closure/celebration)
- [ ] 4.2.6 Return: Inbox items remaining (should be zero after review)
- [ ] 4.2.7 Stalled project detection logic (see design.md)
- [ ] 4.2.8 Description: "Comprehensive GTD weekly review. Identifies stalled projects (no next action), overdue waiting-for items, and someday items to reconsider. David Allen calls this the 'critical factor for success'."
- [ ] 4.2.9 Write tests for stalled project detection

## 5. GTD Engage Stage

### 5.1 Focus Mode Tool

- [ ] 5.1.1 Create `focus-mode` tool
- [ ] 5.1.2 Accept optional: context, energy, time_available
- [ ] 5.1.3 Priority: overdue with deadline > today with deadline > today > anytime
- [ ] 5.1.4 Filter by provided context/energy/time
- [ ] 5.1.5 Return single task with full context (project, notes, deadline)
- [ ] 5.1.6 Explain selection: "This task is overdue and matches your @computer context"
- [ ] 5.1.7 Description: "Get the single most important task to work on now. Filters by your current context, energy level, and available time. Use when feeling overwhelmed or asking 'what should I do next?'"
- [ ] 5.1.8 Write tests

### 5.2 Complete Task Tool

- [ ] 5.2.1 Create `complete-task` tool with fuzzy matching
- [ ] 5.2.2 Accept task_id OR task_title (fuzzy match)
- [ ] 5.2.3 Optional: completion_notes (append before completing)
- [ ] 5.2.4 Multiple matches: return list for clarification, don't auto-complete
- [ ] 5.2.5 Description: "Mark a task complete. Provide task_id if known, or task_title to search. GTD: completing tasks regularly provides positive feedback loop."
- [ ] 5.2.6 Write tests

## 6. GTD Organize Stage

### 6.1 Capture Task Tool

- [ ] 6.1.1 Refine existing `capture-task` for quick inbox capture
- [ ] 6.1.2 Minimal params: title required, notes and tags optional
- [ ] 6.1.3 Always creates in Inbox (no scheduling)
- [ ] 6.1.4 Description: "Quick capture to Inbox. GTD: get it out of your head into a trusted system. Don't organize now—use process-inbox later to clarify and organize."
- [ ] 6.1.5 Write tests

### 6.2 Schedule Task Tool

- [ ] 6.2.1 Create `schedule-task` for organized task creation
- [ ] 6.2.2 Required: title, when (or project)
- [ ] 6.2.3 Optional: deadline, project, area, context (tags), checklist, notes
- [ ] 6.2.4 Support time formats: today, tomorrow, evening, dates, datetimes
- [ ] 6.2.5 Description: "Create a task with scheduling and organization. Use when you know the context and timing. For quick capture without organizing, use capture-task instead."
- [ ] 6.2.6 Write tests

### 6.3 Defer Task Tool

- [ ] 6.3.1 Create `defer-task` with GTD-aware semantics
- [ ] 6.3.2 Required: task_id, defer_to
- [ ] 6.3.3 defer_to values: tomorrow, next_week, someday, specific date
- [ ] 6.3.4 Optional: reason (appends to notes)
- [ ] 6.3.5 Description distinguishes: "Use defer_to='someday' to incubate (Someday/Maybe list). Use a specific date for tickler items that should reappear. These are different GTD concepts."
- [ ] 6.3.6 Write tests

### 6.4 Plan Project Tool

- [ ] 6.4.1 Create `plan-project` for atomic project creation
- [ ] 6.4.2 Required: title, tasks (array of task objects)
- [ ] 6.4.3 Optional: area, deadline, notes, when
- [ ] 6.4.4 Support headings in tasks array for organization
- [ ] 6.4.5 Uses JSON API internally for atomic creation
- [ ] 6.4.6 Description: "Create a project with initial tasks atomically. GTD: any outcome requiring >1 action is a project. Always include at least one next action."
- [ ] 6.4.7 Warn if no tasks have `when=anytime` (no clear next action)
- [ ] 6.4.8 Write tests

## 7. Tool Descriptions (GTD-Native)

### 7.1 Rewrite All Descriptions with GTD Context

- [ ] 7.1.1 Include GTD stage reference where applicable
- [ ] 7.1.2 Include "Use when..." with GTD triggers
- [ ] 7.1.3 Include "Instead use X if..." for GTD alternatives
- [ ] 7.1.4 Reference GTD concepts: next action, context, waiting for, weekly review
- [ ] 7.1.5 Keep descriptions under 200 tokens

## 8. Error Handling (GTD-Aware)

### 8.1 Actionable Error Messages

- [ ] 8.1.1 "Task not found" → "Task not found. Use search-tasks to locate it, or check get-tasks(view='logbook') if completed."
- [ ] 8.1.2 "Multiple matches" → "Found 3 tasks matching 'meeting'. Specify which one: [list with IDs]"
- [ ] 8.1.3 "No next action" → "Project has no active next action. Add one with schedule-task or use process-inbox to define it."
- [ ] 8.1.4 "Inbox not empty" → "Weekly review incomplete: 5 items remain in inbox. Use process-inbox to clarify them."

## 9. URL Scheme Infrastructure

### 9.1 Note Manipulation (Required for Delegation)

- [ ] 9.1.1 Add `append_notes` to url_scheme.update_todo()
- [ ] 9.1.2 Add `prepend_notes` to url_scheme.update_todo()
- [ ] 9.1.3 Write tests

### 9.2 Tag Operations (Required for Contexts)

- [ ] 9.2.1 Add `add_tags` parameter (append without replacing)
- [ ] 9.2.2 Ensure proper tag encoding for @-prefixed contexts
- [ ] 9.2.3 Write tests

### 9.3 JSON Bulk API (Required for Projects)

- [ ] 9.3.1 Investigate why JSON API was disabled
- [ ] 9.3.2 Implement `build_json_payload()` for structured objects
- [ ] 9.3.3 Add `execute_json_url()` function
- [ ] 9.3.4 Write tests for project with tasks creation

### 9.4 Time Scheduling

- [ ] 9.4.1 Add `evening` support
- [ ] 9.4.2 Add time string parsing
- [ ] 9.4.3 Add datetime format support
- [ ] 9.4.4 Write tests

## 10. Migration & Deprecation

### 10.1 Backward Compatibility

- [ ] 10.1.1 Keep old tool names as deprecated aliases
- [ ] 10.1.2 Log deprecation warnings when old tools used
- [ ] 10.1.3 Document migration path in CHANGELOG
- [ ] 10.1.4 Create migration guide mapping old → new tools
- [ ] 10.1.5 Plan removal timeline (suggest: 2 minor versions)

### 10.2 Documentation Updates

- [ ] 10.2.1 Update CLAUDE.md with GTD workflow guidance
- [ ] 10.2.2 Add recommended tag structure to documentation
- [ ] 10.2.3 Document "Waiting For" convention
- [ ] 10.2.4 Add GTD resources/references
