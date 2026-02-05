# Tasks: Remove Deprecated Tool Aliases

## 1. Documentation

- [x] 1.1 Add migration guide to CHANGELOG.md with tool mapping table
- [x] 1.2 Update README.md tool list (remove deprecated section)
- [x] 1.3 Update CLAUDE.md tool organization section
- [x] 1.4 Add "Removed Tools" section at end of README.md with migration table

## 2. Code Removal

- [x] 2.1 Remove `tools_deprecated.py` file entirely
- [x] 2.2 Remove deprecated tool annotations from `tool_annotations.py`
- [x] 2.3 Remove `register_deprecated_tools` import and call from `fast_server.py`
- [x] 2.4 Remove any imports of deprecated tools in test files

## 3. Verification

- [x] 3.1 Run full test suite to ensure no regressions
- [x] 3.2 Verify GTD tools cover all use cases (inbox, today, upcoming, etc.)
- [x] 3.3 Test that removed tool names return proper "tool not found" errors

## 4. Cleanup

- [x] 4.1 Remove unused imports in affected files
- [x] 4.2 Run ruff check and format
- [ ] 4.3 Update test coverage report
