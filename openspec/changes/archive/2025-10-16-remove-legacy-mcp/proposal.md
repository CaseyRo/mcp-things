# Remove Legacy MCP Implementation

## Why

The Things FastMCP server currently maintains two parallel MCP implementations:

1. **Legacy Implementation** (`things_server.py`, `simple_server.py`) - Original implementation using direct MCP protocol
2. **FastMCP Implementation** (`fast_server.py`, `things_fast_server.py`) - Modern implementation with reliability features

This dual-implementation maintenance creates several problems:

- **Code duplication**: Similar functionality exists in both implementations, making bug fixes and features require double work
- **Increased complexity**: New contributors must understand both implementations
- **Documentation burden**: README and docs must explain both approaches
- **Testing overhead**: Both implementations need testing, increasing CI time
- **Security surface**: More code means more potential vulnerabilities
- **Deprecation deadline approaching**: README already announces EOY 2025 removal

The FastMCP implementation is production-ready and includes significant reliability improvements that the legacy implementation lacks:

- Circuit breaker pattern for failure recovery
- Intelligent caching with TTL management
- Rate limiting and throttling
- Dead letter queue for debugging
- Structured logging with privacy redaction
- Exponential backoff retry logic

The deprecation was announced in documentation, giving users sufficient notice to migrate.

## What Changes

**BREAKING CHANGE**: Remove all legacy MCP server files and consolidate to FastMCP-only implementation.

### Files to Remove

1. `/things_server.py` - Legacy entry point
2. `/src/things_mcp/things_server.py` - Legacy MCP server implementation
3. `/src/things_mcp/simple_server.py` - Simple MCP server variant
4. `/src/things_mcp/simple_url_scheme.py` - Legacy URL scheme implementation
5. `/src/things_mcp/mcp_tools.py` - Legacy tool registration (if unused by FastMCP)

### Files to Keep/Update

1. `/things_fast_server.py` - Primary entry point (KEEP)
2. `/src/things_mcp/fast_server.py` - FastMCP implementation (KEEP)
3. `/src/things_mcp/url_scheme.py` - Modern URL scheme (KEEP)
4. `/src/things_mcp/handlers.py` - Tool handlers with reliability (KEEP)
5. All supporting modules: `cache.py`, `utils.py`, `formatters.py`, etc. (KEEP)

### Documentation Updates

- Remove deprecation notice from README (no longer needed)
- Remove "Why not Docker" duplicate section (consolidate)
- Update quick start to only reference FastMCP
- Remove all references to `things_server.py` from docs
- Update AGENTS.md with removal completion

### Configuration Updates

- Update `pyproject.toml` if it references legacy files
- Update `smithery.yaml` to remove legacy entry points (if any)
- Ensure `things_fast_server.py` is the only documented entry point

## Impact

### Breaking Changes

- **Users still referencing `things_server.py`** will need to update to `things_fast_server.py`
- **MCP client configs** pointing to old entry point must be updated
- **Automated scripts** using `mcp dev things_server.py` must migrate

### Migration Path

Clear migration documented in README:

1. Update MCP client config from `things_server.py` → `things_fast_server.py`
2. Test with `mcp dev things_fast_server.py`
3. No changes to tool names or signatures - full backward compatibility

### Benefits

- **Reduced codebase**: ~30% fewer files to maintain
- **Clearer architecture**: Single implementation path
- **Better reliability**: All users get circuit breaker, caching, retry logic
- **Faster development**: Changes only need to be made once
- **Reduced confusion**: No more "which one should I use?" questions

### Risks

- **Users ignoring deprecation**: Some users may not have seen the EOY 2025 notice
- **Automated deployments**: Scripts that haven't been updated may break
- **Documentation lag**: External blog posts/tutorials may reference old approach

**Mitigation**: Version bump to 2.0.0 to signal breaking change, clear CHANGELOG entry, update README migration guide prominently.

## Affected Specs

None - this is an implementation consolidation, not a capability change. All 19 MCP tools remain identical with the same signatures.

## Timeline

- **Target Removal**: Aligns with previously announced EOY 2025 deprecation
- **Current Date**: October 2025 - plenty of notice has been given
- **Version**: Bump to 2.0.0 to signal breaking change

