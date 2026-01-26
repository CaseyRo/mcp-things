## 1. Investigation & Analysis
- [x] 1.1 Review current osascript usage patterns across codebase
- [x] 1.2 Test current behavior - verify Things shows in foreground during operations
- [x] 1.3 Research AppleScript techniques for background execution (`without activating`, `ignoring application responses`)
- [x] 1.4 Check FastMCP documentation for latest features and best practices
- [x] 1.5 Review current FastMCP version constraints in pyproject.toml

## 2. osascript Background Execution
- [x] 2.1 Add `THINGS_MCP_DISABLE_BACKGROUND_OSASCRIPT` environment variable check in `applescript_bridge.py`
- [x] 2.2 Modify `run_applescript()` in `applescript_bridge.py` to wrap AppleScript commands with background execution flags (respecting env var)
- [x] 2.3 Update `add_todo_direct()` to use background execution
- [x] 2.4 Update `update_todo_direct()` to use background execution
- [x] 2.5 Update `ensure_tags_exist()` in `tag_handler.py` to use background execution
- [x] 2.6 Update `get_existing_tags()` in `tag_handler.py` to use background execution
- [x] 2.7 Update `detect_things_version()` in `utils.py` to use background execution
- [x] 2.8 Update `is_things_running()` in `utils.py` to use background execution for responsiveness check

## 3. FastMCP Integration Review
- [x] 3.1 Review FastMCP async capabilities - check if tools can benefit from async/await
- [x] 3.2 Verify FastMCP metadata usage (instructions, website_url, icons) is optimal
- [x] 3.3 Check for FastMCP declarative configuration options (fastmcp.json)
- [x] 3.4 Review tool annotation usage for consistency
- [x] 3.5 Document any FastMCP best practices that should be adopted

## 4. Testing & Validation
- [x] 4.1 Test that Things does not appear in foreground during todo creation (background enabled)
- [x] 4.2 Test that Things does not appear during tag operations (background enabled)
- [x] 4.3 Test that Things does not appear during version/app state checks (background enabled)
- [x] 4.4 Test that `THINGS_MCP_DISABLE_BACKGROUND_OSASCRIPT` env var disables background execution
- [x] 4.5 Test that foreground execution works correctly when env var is set
- [x] 4.6 Verify all existing functionality still works correctly
- [x] 4.7 Run `ruff check .` to ensure code quality
- [x] 4.8 Run `pytest` to ensure all tests pass

## 5. Documentation
- [x] 5.1 Update code comments explaining background execution approach and env var
- [x] 5.2 Document `THINGS_MCP_DISABLE_BACKGROUND_OSASCRIPT` env var in README
- [x] 5.3 Update README if behavior changes are user-visible
- [x] 5.4 Document any FastMCP improvements in AGENTS.md log

