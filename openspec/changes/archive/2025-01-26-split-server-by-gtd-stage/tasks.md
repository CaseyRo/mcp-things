# Tasks: Split Server by GTD Stage

## 1. Create Shared Infrastructure
- [x] 1.1 Create `tool_annotations.py` with TOOL_ANNOTATIONS dict, READ_ONLY/ADD/UPDATE_ANNOTATIONS
- [x] 1.2 Create `server_core.py` with:
  - N8NCompatibilityMiddleware class
  - `_flatten_anyof_for_n8n()` helper
  - `_patch_tool_serialization_for_n8n()` helper
  - `_error_result()` helper
  - `_build_icon()` helper
  - INSTRUCTIONS_TEXT, WEBSITE_URL constants
  - `create_mcp_server()` factory function

## 2. Extract GTD Core Tools (Engage/Capture/Clarify)
- [x] 2.1 Create `tools_gtd_core.py`
- [x] 2.2 Move `get-tasks` tool
- [x] 2.3 Move `focus-mode` tool
- [x] 2.4 Move `complete-task` tool
- [x] 2.5 Move `capture-task` tool
- [x] 2.6 Move `process-inbox` tool
- [x] 2.7 Move `convert-to-project` tool
- [x] 2.8 Create `register_gtd_core_tools(mcp)` function

## 3. Extract GTD Organize Tools
- [x] 3.1 Create `tools_gtd_organize.py`
- [x] 3.2 Move `schedule-task` tool
- [x] 3.3 Move `delegate-task` tool
- [x] 3.4 Move `defer-task` tool
- [x] 3.5 Move `plan-project` tool
- [x] 3.6 Move `modify-task` tool
- [x] 3.7 Create `register_gtd_organize_tools(mcp)` function

## 4. Extract GTD Reflect Tools
- [x] 4.1 Create `tools_gtd_reflect.py`
- [x] 4.2 Move `daily-review` tool
- [x] 4.3 Move `weekly-review` tool
- [x] 4.4 Create `register_gtd_reflect_tools(mcp)` function

## 5. Extract Utility Tools
- [x] 5.1 Create `tools_utility.py`
- [x] 5.2 Move `search-tasks` tool
- [x] 5.3 Move `get-projects` tool
- [x] 5.4 Move `get-areas` tool
- [x] 5.5 Move `get-tags` tool
- [x] 5.6 Move `show-in-app` tool
- [x] 5.7 Move `get-cache-stats` tool
- [x] 5.8 Create `register_utility_tools(mcp)` function

## 6. Extract Deprecated Tools
- [x] 6.1 Create `tools_deprecated.py`
- [x] 6.2 Move all deprecated list tools (get-inbox, get-today, etc.)
- [x] 6.3 Move deprecated CRUD tools (add-todo, add-project, update-todo, update-project)
- [x] 6.4 Move deprecated search tools (search-todos, search-advanced, etc.)
- [x] 6.5 Create `register_deprecated_tools(mcp)` function

## 7. Refactor fast_server.py
- [x] 7.1 Remove all tool definitions (now in separate modules)
- [x] 7.2 Remove middleware and helper functions (now in server_core.py)
- [x] 7.3 Import and call `create_mcp_server()` from server_core
- [x] 7.4 Import and call all `register_*_tools(mcp)` functions
- [x] 7.5 Verify fast_server.py is ~110 lines (was ~140 target, achieved 111)

## 8. Testing & Validation
- [x] 8.1 Run `ruff check .` - fix any import errors
- [x] 8.2 Run `ruff format .` - ensure consistent formatting
- [x] 8.3 Run `uv run python -m pytest tests -m "not real"` - passes (30 deselected, all real tests)
- [x] 8.4 Verify server starts: `uv run server` - loads successfully
- [x] 8.5 Verify all 37 tools register correctly (was 34 in proposal, actual is 37)
- [x] 8.6 Update test imports to use new module structure

## 9. Documentation
- [x] 9.1 Update CLAUDE.md architecture section
- [x] 9.2 Create docs/n8n-fastmcp-compatibility.md
- [x] 9.3 Add entry to CHANGELOG.md
