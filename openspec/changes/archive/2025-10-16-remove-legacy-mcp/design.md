# Design Document: Remove Legacy MCP Implementation

## Context

The Things FastMCP server evolved from a simple MCP implementation to a production-ready server with enterprise reliability features. During this evolution, both implementations were maintained in parallel to allow gradual migration. The deprecation was announced with an EOY 2025 timeline, and we're now ready to complete the transition.

**Stakeholders:**
- End users running the MCP server locally
- AI assistant platforms (Claude Desktop, etc.)
- Contributors maintaining the codebase
- Smithery registry users discovering the server

**Constraints:**
- Must maintain tool API compatibility (no changes to tool names or signatures)
- Must provide clear migration path for users still on legacy implementation
- Should minimize user disruption while maintaining security and maintainability

## Goals / Non-Goals

### Goals

1. **Simplify codebase** - Remove ~500+ lines of duplicate/deprecated code
2. **Improve maintainability** - Single implementation to update and test
3. **Enhance user experience** - All users get reliability features automatically
4. **Clear documentation** - Remove confusion about which implementation to use
5. **Security posture** - Reduce attack surface by removing unused code

### Non-Goals

1. **Tool API changes** - Not changing tool signatures or adding/removing tools
2. **Configuration overhaul** - Not changing env vars or config file structure
3. **Dependency updates** - Not updating Python or package versions (separate concern)
4. **UI/UX changes** - Not changing terminal output or logging format

## Decisions

### Decision 1: Complete Removal vs. Deprecation Stub

**Options:**
- A) Complete removal of all legacy files
- B) Keep stub files that print deprecation error and exit
- C) Redirect legacy imports to FastMCP

**Choice:** A - Complete removal

**Rationale:**
- Deprecation notice has been active for months
- README already states "will be removed by EOY 2025"
- Stub files still require maintenance and testing
- Major version bump (2.0.0) clearly signals breaking change
- Clean break is simpler than half-measures

### Decision 2: Version Bump Strategy

**Options:**
- A) Major version bump (2.0.0)
- B) Minor version bump (1.1.0) with deprecation
- C) Stay at 1.0.0

**Choice:** A - Major version bump to 2.0.0

**Rationale:**
- Semantic versioning: breaking changes require major bump
- Signals to users that manual intervention may be needed
- Package managers will prompt users about major version updates
- Clear demarcation between legacy and modern eras

### Decision 3: Migration Documentation

**Options:**
- A) Separate MIGRATION.md file
- B) Prominent section in README
- C) CHANGELOG.md entry only
- D) All of the above

**Choice:** B + C - README section + CHANGELOG entry (remove separate file after transition)

**Rationale:**
- Users check README first
- CHANGELOG provides version history
- Separate file adds clutter after migration complete
- Can remove migration section in future (2.1.0) once transition settles

### Decision 4: File Removal Order

**Choice:** Remove all at once in single commit

**Rationale:**
- Atomic change prevents partial state
- Easier to revert if issues discovered
- All related changes in one PR for review
- Testing validates entire change at once

## Technical Details

### Files Identified for Removal

```
/things_server.py                    # 134 lines - Legacy entry point
/src/things_mcp/things_server.py     # ~200 lines - Legacy MCP implementation
/src/things_mcp/simple_server.py     # ~180 lines - Simplified variant
/src/things_mcp/simple_url_scheme.py # ~150 lines - Legacy URL builder
/src/things_mcp/mcp_tools.py         # ~50 lines - Legacy tool registration
```

**Total removal:** ~714 lines of code

### Import Dependencies

Need to verify these files aren't imported elsewhere:

```bash
# Search for imports
rg "from.*simple_server" --type py
rg "from.*things_server" --type py
rg "import.*mcp_tools" --type py
```

### Entry Points

Current:
```python
# things_server.py (OLD)
# things_fast_server.py (NEW)
```

After change:
```python
# things_fast_server.py (ONLY)
```

## Risks / Trade-offs

### Risk 1: Users Miss Migration Notice

**Likelihood:** Medium
**Impact:** High (broken workflows)

**Mitigation:**
- Major version bump forces attention
- CHANGELOG entry prominently describes change
- README has clear migration guide
- GitHub release notes include migration steps
- Error messages point to documentation

### Risk 2: External Documentation References Legacy

**Likelihood:** High (blog posts, tutorials)
**Impact:** Medium (confusion for new users)

**Mitigation:**
- Can't control external docs
- Our official docs are authoritative
- Search engine results will eventually catch up
- FastMCP is clearly labeled as recommended approach

### Risk 3: Automated CI/CD Breaks

**Likelihood:** Low
**Impact:** High (deployment failures)

**Mitigation:**
- Pre-flight check: search GitHub for public references
- Version pinning in CI prevents automatic breakage
- Clear migration path in docs
- Can create issue template for migration help

### Risk 4: Ruff/Pytest Breakage

**Likelihood:** Low
**Impact:** Medium (development workflow)

**Mitigation:**
- Run full test suite before commit
- Run `ruff check .` before commit
- Fix any import errors immediately
- Update pytest paths if needed

## Migration Plan

### Phase 1: Preparation (Pre-Implementation)

1. Audit all files for imports of legacy modules
2. Search GitHub for external projects using legacy server
3. Prepare detailed CHANGELOG entry
4. Update README with migration guide

### Phase 2: Implementation

1. Create feature branch: `remove-legacy-mcp`
2. Delete legacy files atomically
3. Clean up imports and references
4. Update documentation
5. Bump versions to 2.0.0
6. Run full test suite
7. Commit with detailed message

### Phase 3: Validation

1. Test `./run_things_fastmcp.sh`
2. Test `mcp dev things_fast_server.py`
3. Verify all 19 tools work
4. Check reliability features (circuit breaker, cache)
5. Validate `ruff check .` passes
6. Validate `pytest` passes (if exists)

### Phase 4: Release

1. Merge to main branch
2. Tag release: `v2.0.0`
3. Publish to PyPI as 2.0.0
4. Update Smithery registry
5. Create GitHub release with migration notes
6. Monitor issues for migration problems

### Rollback Plan

If critical issues discovered:

1. Revert commit (atomic change makes this safe)
2. Tag as 2.0.1 with revert
3. Investigate issues
4. Re-attempt removal later

## Open Questions

1. **Q:** Should we keep legacy files in git history with a "tombstone" marker?
   **A:** No - git history preserves them, no need for extra markers

2. **Q:** What if users report needing specific legacy features?
   **A:** Investigate and potentially add to FastMCP if genuinely needed

3. **Q:** Should we create a migration helper script?
   **A:** No - migration is simple (change filename in config), script is overkill

4. **Q:** How long should migration docs stay in README?
   **A:** Remove in 2.1.0 (after ~3 months) since it's just filename change

## Success Metrics

- [ ] Codebase reduced by ~700+ lines
- [ ] Zero increase in reported issues
- [ ] All 19 tools remain functional
- [ ] Test suite passes completely
- [ ] No broken imports in codebase
- [ ] Documentation is consistent and clear
- [ ] Smithery registry validates

