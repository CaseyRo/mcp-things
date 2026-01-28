# Design: Client Integration Documentation

## Context

The Things MCP server is compatible with n8n, ChatGPT, and clawdbot. Users need clear documentation on:
1. How to set up integrations with each client
2. Official documentation references
3. How to get integrations approved/listed in client directories

Existing documentation includes technical compatibility guides but lacks user-facing integration guides.

## Goals

- Provide step-by-step integration guides for each client platform
- Include official documentation links for reference
- Guide users through approval processes for directory listings
- Maintain clear separation between setup guides and technical compatibility details

## Non-Goals

- Rewriting technical compatibility guides (keep existing docs)
- Creating new testing procedures (use existing test documentation)
- Modifying server code (documentation-only change)

## Decisions

### Decision: Documentation Structure

**What**: Create separate integration guides for each client (`docs/integration-{client}.md`) plus one approval guide (`docs/integration-approval.md`).

**Why**: 
- Each client has different setup requirements and processes
- Users typically integrate with one client at a time
- Approval processes differ significantly between platforms
- Keeps documentation focused and scannable

**Alternatives considered**:
- Single combined guide: Too long, harder to navigate
- Integration info in README only: README would become too long

### Decision: Separation of Concerns

**What**: Integration guides focus on setup steps; compatibility guides focus on technical implementation details.

**Why**:
- Users setting up integrations don't need technical details upfront
- Developers debugging compatibility issues need technical details
- Clear separation reduces cognitive load

**Cross-references**: Integration guides link to compatibility guides for troubleshooting.

### Decision: Approval Guide Scope

**What**: Create single `docs/integration-approval.md` covering all clients' approval processes, including ClawdHub skill publishing.

**Why**:
- Approval processes are less frequently accessed than setup guides
- Single guide allows comparison between platforms
- Users may want to get listed on multiple platforms
- ClawdHub (https://clawdhub.com/) is the primary skill registry for clawdbot

**Structure**: Organize by client platform with clear sections for each, including ClawdHub publishing process.

### Decision: Official Documentation Links

**What**: Include links to official client documentation in each integration guide.

**Why**:
- Official docs are authoritative and kept up-to-date by platform maintainers
- Users may need platform-specific details not covered in our guides
- Demonstrates integration follows official best practices

**Maintenance**: Links should be verified periodically as platforms evolve.

## Risks / Trade-offs

**Risk**: Official documentation links may break or change as platforms evolve.
- **Mitigation**: Include link verification in documentation review process

**Risk**: Approval processes may change faster than documentation can be updated.
- **Mitigation**: Include "last updated" dates and encourage users to check official sources

**Risk**: Integration guides may become outdated as server evolves.
- **Mitigation**: Link to compatibility guides for technical details, keep setup guides focused on configuration

## Open Questions

- Should we include screenshots in integration guides? (Decision: Include if helpful, but text-first approach)
- How detailed should troubleshooting sections be? (Decision: Link to compatibility guides, include common issues)
- Should approval guide include submission templates? (Decision: Include if official templates exist, otherwise provide guidance)
