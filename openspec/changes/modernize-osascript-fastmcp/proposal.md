# Change: Modernize osascript and FastMCP Integration

## Why

The current implementation has two areas for improvement:

1. **osascript Execution**: Currently uses synchronous `subprocess.run()` which can cause Things 3 to appear in the foreground and interrupt user workflow. AppleScript operations should run silently in the background.

2. **FastMCP Integration**: While the current FastMCP setup is functional, there may be modern features (async handlers, improved metadata, declarative configuration) that could enhance the integration.

## What Changes

- **osascript Background Execution**: Modify `run_applescript()` and all osascript invocations to prevent Things from appearing in the foreground using AppleScript techniques (`without activating`, `ignoring application responses`) and subprocess improvements. Add `THINGS_MCP_DISABLE_BACKGROUND_OSASCRIPT` environment variable to allow disabling background execution for debugging.

- **FastMCP Modernization Review**: Review FastMCP integration for:
  - Async/await patterns where beneficial
  - Latest metadata features (if available in current version)
  - Best practices for tool registration and error handling

- **Consistent Background Behavior**: Ensure all AppleScript operations (tag creation, version detection, app state checks) run without showing Things UI.

## Impact

- **Affected specs**: `applescript-execution`, `fastmcp-integration`
- **Affected code**:
  - `src/things_mcp/applescript_bridge.py` - Core AppleScript execution
  - `src/things_mcp/tag_handler.py` - Tag creation via AppleScript
  - `src/things_mcp/utils.py` - App state checks and version detection
  - `src/things_mcp/fast_server.py` - FastMCP server configuration (if improvements found)

- **User Experience**: Things 3 will remain in the background during MCP operations, providing a more seamless, non-intrusive experience.
