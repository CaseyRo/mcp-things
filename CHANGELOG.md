# Changelog

All notable changes to Things 3 Enhanced MCP will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.0] - 2025-10-16

### BREAKING CHANGES

- **Removed legacy MCP implementation** - Consolidated to FastMCP-only implementation
  - Deleted `/things_server.py` - Legacy entry point
  - Deleted `/src/things_mcp/things_server.py` - Legacy MCP server
  - Deleted `/src/things_mcp/simple_server.py` - Simple server variant
  - Deleted `/src/things_mcp/simple_url_scheme.py` - Legacy URL scheme
  - Deleted `/src/things_mcp/mcp_tools.py` - Legacy tool registration

### Migration Guide

If upgrading from 1.x:

1. **Update MCP client configuration:**
   - Old: `"command": "things_server.py"`
   - New: `"command": "things_fast_server.py"`

2. **Update any scripts or automation:**
   - Old: `mcp dev things_server.py`
   - New: `mcp dev things_fast_server.py`

3. **No tool changes required** - All 19 MCP tools remain with identical signatures

### Benefits of 2.0

- ✅ **Simpler codebase** - Removed ~714 lines of duplicate code
- ✅ **Better reliability** - All users now get circuit breaker, caching, and retry logic automatically
- ✅ **Easier maintenance** - Single implementation to test and update
- ✅ **Clearer documentation** - No more confusion about which implementation to use

### Changed

- Updated project description to emphasize production-ready nature
- Bumped version to 2.0.0 across all configuration files
- Streamlined documentation with consolidated migration guide

## [1.0.0] - 2025-05-30

### Added
- 🚀 **FastMCP Implementation**: Complete rewrite using FastMCP pattern for better maintainability
- 🔄 **Reliability Features**:
  - Circuit breaker pattern to prevent cascading failures
  - Exponential backoff retry logic for transient failures
  - Dead letter queue for failed operations
- ⚡ **Performance Optimizations**:
  - Intelligent caching system with TTL management
  - Rate limiting to prevent overwhelming Things app
  - Automatic cache invalidation on data modifications
- 🍎 **AppleScript Bridge**: Fallback mechanism when URL schemes fail
- 📊 **Enhanced Monitoring**:
  - Structured JSON logging
  - Performance metrics and statistics
  - Comprehensive error tracking
  - Debug-friendly output
- 🛡️ **Error Handling**: Comprehensive exception management and recovery
- 🧪 **Test Suite**: Extensive tests for reliability
- 📦 **Smithery Support**: Full configuration for Smithery registry deployment
- 📝 **Documentation**: Enhanced README with detailed setup and troubleshooting guides

### Changed
- Rebranded to "Things 3 Enhanced MCP" for clear differentiation
- Updated package name to `things3-enhanced-mcp`
- Improved configuration token handling
- Enhanced URL scheme operations with better error recovery

### Fixed
- Token configuration import issues
- URL scheme reliability problems
- Various edge cases in task/project operations

### Attribution
Based on the original [things-mcp](https://github.com/hald/things-mcp) by Harald Lindstrøm

[1.0.0]: https://github.com/CaseyRo/things-fastmcp/releases/tag/v1.0.0
