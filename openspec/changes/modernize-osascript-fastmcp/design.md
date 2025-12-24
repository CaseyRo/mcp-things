# Design: Modernize osascript and FastMCP Integration

## Context

The Things FastMCP server interacts with Things 3 via AppleScript and URL schemes. Currently, AppleScript operations can cause Things to appear in the foreground, interrupting user workflow. Additionally, we should review the FastMCP integration to ensure we're using modern best practices.

## Goals

1. **Non-Intrusive Operations**: All AppleScript operations should execute without bringing Things to the foreground
2. **Maintain Reliability**: Background execution must not compromise operation success rates
3. **Modern FastMCP Patterns**: Ensure we're leveraging FastMCP best practices

## Non-Goals

- Rewriting the entire AppleScript execution layer
- Changing tool APIs or MCP protocol behavior
- Adding new dependencies beyond what's necessary

## Decisions

### Decision: AppleScript Background Execution Technique

**Approach**: Wrap AppleScript commands with `without activating` clause and use `ignoring application responses` where appropriate.

**Rationale**:

- `without activating` prevents the target application from being brought to the foreground
- `ignoring application responses` allows commands to execute without waiting for UI responses (when return values aren't needed)
- These are standard AppleScript techniques that maintain operation reliability

**Implementation Pattern**:

```applescript
tell application "Things3" without activating
  -- operations here
end tell
```

**Alternatives Considered**:

- Using `subprocess.Popen` with background flags: Doesn't prevent app activation at the AppleScript level
- Running osascript in separate process with `&`: Adds complexity, doesn't solve activation issue
- Using AppleScript's `run script` in background: More complex, same result as `without activating`

### Decision: Subprocess Execution Method

**Approach**: Continue using `subprocess.run()` but with appropriate timeouts and error handling.

**Rationale**:

- `subprocess.run()` provides good error handling and output capture
- Already has timeout support where needed
- Synchronous execution is appropriate for AppleScript operations that return values

**Alternatives Considered**:

- `subprocess.Popen`: More complex, doesn't add value for our use case
- `asyncio.subprocess`: Would require async tool handlers, adds complexity without clear benefit

### Decision: FastMCP Review Scope

**Approach**: Review current integration and make targeted improvements if clear benefits exist.

**Rationale**:

- Current FastMCP integration is functional and well-structured
- Don't change for change's sake
- Focus on improvements that add clear value (better error handling, async if needed, metadata improvements)

**Areas to Review**:

- Tool handlers: Can they benefit from async/await?
- Metadata: Are we using all useful metadata features?
- Configuration: Should we adopt declarative config (fastmcp.json)?

### Decision: Environment Variable for Background Execution Control

**Approach**: Add `THINGS_MCP_DISABLE_BACKGROUND_OSASCRIPT` environment variable to allow disabling background execution for debugging purposes.

**Rationale**:

- Provides a way to debug issues by allowing Things to activate (useful for troubleshooting)
- Follows existing pattern of using environment variables for configuration (e.g., `THINGS_FASTMCP_HOST`, `THINGS_FASTMCP_PORT`)
- Defaults to background execution enabled (False), maintaining the improved UX as default
- Simple boolean flag - set to any non-empty value to disable background execution

**Implementation Pattern**:

```python
# In applescript_bridge.py
DISABLE_BACKGROUND_ENV_VAR = "THINGS_MCP_DISABLE_BACKGROUND_OSASCRIPT"
background_enabled = not os.getenv(DISABLE_BACKGROUND_ENV_VAR, "").strip()
```

**Alternatives Considered**:

- Config file setting: Less convenient for quick debugging, requires file modification
- Command-line flag: Would require changes to server startup, environment variable is more flexible
- Default to foreground execution: Rejects the UX improvement as default, making it opt-in rather than opt-out

## Risks / Trade-offs

### Risk: Background Execution May Cause Timing Issues

**Mitigation**:

- Test thoroughly with various operation types
- Monitor error rates after deployment
- Keep existing retry logic and circuit breaker

### Risk: FastMCP Changes Could Break Compatibility

**Mitigation**:

- Only adopt FastMCP features available in our minimum version (1.2.0)
- Test with current MCP client versions
- Maintain backward compatibility

### Trade-off: Complexity vs. UX Improvement

**Decision**: Favor UX improvement (background execution) as it directly addresses user pain point with minimal code complexity.

## Migration Plan

1. **Phase 1**: Modify `run_applescript()` to accept optional background flag (backward compatible)
2. **Phase 2**: Update all AppleScript calls to use background execution
3. **Phase 3**: Test thoroughly
4. **Phase 4**: Review FastMCP integration and make targeted improvements
5. **Phase 5**: Deploy and monitor

## Open Questions

- Are there any AppleScript operations that require foreground execution (if so, document them)?
