## ADDED Requirements

### Requirement: Benchmark CLI produces latency report

The system SHALL provide a `scripts/benchmark.py` CLI that measures end-to-end tool call latency against a running Things MCP server and outputs results as Markdown and JSON.

#### Scenario: Run benchmark with default settings

- **WHEN** user runs `python scripts/benchmark.py --output markdown`
- **THEN** the CLI connects to the MCP server and runs the standard suite (inbox read, single task get, search, modify, capture)
- **THEN** each operation runs 5 iterations
- **THEN** output includes min/avg/p95/max latency per operation

#### Scenario: JSON output for downstream consumption

- **WHEN** user runs `python scripts/benchmark.py --output json`
- **THEN** the CLI outputs structured JSON with per-operation latency arrays, percentiles, and metadata (server URL, timestamp, task counts)

#### Scenario: Cold vs warm measurement

- **WHEN** the benchmark suite runs
- **THEN** the first invocation of each operation is labeled "cold" and subsequent invocations are labeled "warm"
- **THEN** the report separates cold and warm latency statistics

### Requirement: Benchmark measures task count scaling

The system SHALL measure read operation latency across different task counts to identify scaling bottlenecks.

#### Scenario: Scaling measurement

- **WHEN** benchmark runs the scaling suite
- **THEN** it measures `get-tasks` latency at the current task count
- **THEN** results include task count alongside latency for correlation analysis

### Requirement: Benchmark measures osascript subprocess duration

The system SHALL instrument osascript subprocess calls independently from end-to-end latency.

#### Scenario: Subprocess timing

- **WHEN** a write operation is benchmarked
- **THEN** the report includes both end-to-end latency and osascript subprocess duration separately
- **THEN** the difference reveals framework/network overhead vs. AppleScript execution time
