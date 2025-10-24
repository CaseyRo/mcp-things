## Context

The current FastMCP server uses a bash script (`run_things_fastmcp.sh`) to handle argument parsing, environment variable management, and virtual environment setup. This script adds complexity and maintenance overhead, especially when UV is already the preferred package manager for the project.

## Goals / Non-Goals

### Goals
- Simplify server execution by leveraging UV's native script capabilities
- Reduce maintenance overhead by removing bash script complexity
- Maintain all current functionality (host/port configuration, environment variables)
- Provide clear migration path for existing users

### Non-Goals
- Changing the core server functionality
- Modifying the FastMCP protocol implementation
- Breaking existing API compatibility

## Decisions

### Decision: Use UV Scripts for Server Execution
**What**: Replace bash script with UV script configuration in `pyproject.toml`
**Why**: UV provides native script execution with proper dependency management, eliminating the need for custom bash logic
**Alternatives considered**:
- Keep bash script (rejected - adds maintenance overhead)
- Use Python entry points (rejected - UV scripts are more flexible for this use case)

### Decision: Maintain Environment Variable Interface
**What**: Keep `THINGS_FASTMCP_HOST` and `THINGS_FASTMCP_PORT` environment variables (already implemented in FastMCP server)
**Why**: The FastMCP server already reads these environment variables directly, so no changes needed to preserve existing user workflows
**Alternatives considered**: Command-line arguments only (rejected - environment variables are more convenient for configuration)

## Risks / Trade-offs

### Risk: Breaking existing user workflows
**Mitigation**: Provide clear migration documentation and maintain environment variable compatibility

### Risk: UV dependency requirement
**Mitigation**: UV is already the preferred package manager for this project, so this aligns with existing practices

### Trade-off: Less flexibility than bash script
**Mitigation**: UV scripts provide sufficient flexibility for the use cases, and the simplification benefits outweigh the minor flexibility loss

## Migration Plan

1. **Phase 1**: Add UV scripts to `pyproject.toml` alongside existing bash script
2. **Phase 2**: Update documentation to show both methods
3. **Phase 3**: Test UV scripts thoroughly
4. **Phase 4**: Remove bash script and update all references
5. **Phase 5**: Update version and changelog

## Open Questions

- Should we provide both `uv run server` and `uv run dev` scripts?
- Do we need to handle any edge cases that the bash script currently handles?
