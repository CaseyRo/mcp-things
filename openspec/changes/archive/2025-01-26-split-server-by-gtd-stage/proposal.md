# Change: Split Server by GTD Stage

## Status

**APPROVED** - Ready for implementation

## Why

`fast_server.py` has grown to 2,404 lines (50.8% of the entire codebase), mixing:

- 34 tool definitions across 5 GTD stages
- Server configuration and middleware
- n8n compatibility patches
- 19 deprecated backward-compatibility tools

This creates:

- **Poor maintainability** - Single file too large to navigate efficiently
- **High cognitive load** - Hard to reason about one GTD stage in isolation
- **Testing friction** - Can't easily test one stage without loading everything
- **Token overhead** - AI assistants loading the full file when working on one area

## What Changes

Split `fast_server.py` into focused modules organized by GTD methodology:

```
src/things_mcp/
├── fast_server.py           # 140 lines - Entry point, imports & registers all tools
├── server_core.py           # 340 lines - Middleware, n8n patches, server factory
├── tools_gtd_core.py        # 460 lines - Engage/Capture/Clarify tools
├── tools_gtd_organize.py    # 450 lines - Organize stage tools
├── tools_gtd_reflect.py     # 190 lines - Reflect stage tools
├── tools_utility.py         # 120 lines - Utility tools (search, cache stats, etc.)
├── tools_deprecated.py      # 730 lines - Backward-compat aliases
└── tool_annotations.py      # 80 lines - Shared TOOL_ANNOTATIONS dict
```

**Tool Distribution:**

| Module | GTD Stage | Tools |
|--------|-----------|-------|
| tools_gtd_core.py | Engage | get-tasks, focus-mode, complete-task |
| tools_gtd_core.py | Capture | capture-task |
| tools_gtd_core.py | Clarify | process-inbox, convert-to-project |
| tools_gtd_organize.py | Organize | schedule-task, delegate-task, defer-task, plan-project, modify-task |
| tools_gtd_reflect.py | Reflect | daily-review, weekly-review |
| tools_utility.py | Utility | search-tasks, get-projects, get-areas, get-tags, show-in-app, get-cache-stats |
| tools_deprecated.py | Deprecated | 19 backward-compat tools |

## Impact

- **Affected code:**
  - `src/things_mcp/fast_server.py` - Reduced to entry point
  - New files: `server_core.py`, `tools_gtd_core.py`, `tools_gtd_organize.py`, `tools_gtd_reflect.py`, `tools_utility.py`, `tools_deprecated.py`, `tool_annotations.py`
  - Test imports may need updates

- **No breaking changes:**
  - All tool names remain identical
  - MCP protocol interface unchanged
  - Entry point (`things_fast_server.py`) unchanged

## Design Decisions

1. **Combine Engage/Capture/Clarify** - These form the "input" side of GTD and share similar patterns (reading + light writes)

2. **Keep Organize separate** - Heavy write operations with distinct patterns

3. **Keep Reflect separate** - Review tools have unique aggregation logic

4. **Isolate deprecated tools** - Easy to remove entirely in future version

5. **Extract annotations** - Shared across all modules, prevents circular imports

6. **Server factory in server_core.py** - Middleware, patches, and server creation logic
