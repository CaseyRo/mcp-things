## ADDED Requirements

### Requirement: Direct SQLite reads for all read operations

The system SHALL provide a `sqlite_reader.py` module that queries the Things SQLite database directly for read operations, bypassing things-py and AppleScript.

#### Scenario: get-tasks reads from SQLite

- **WHEN** `get-tasks` is called
- **THEN** it reads from the Things SQLite database at `~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/Things Database.thingssqlite`
- **THEN** the response is equivalent to the current things-py based response

#### Scenario: Read-only access

- **WHEN** the SQLite reader opens the database
- **THEN** it uses `?mode=ro` (read-only) with WAL-compatible settings
- **THEN** no write operations are attempted via SQLite

### Requirement: Schema version validation on startup

The system SHALL check the Things database schema version on server startup and warn if unrecognized.

#### Scenario: Known schema version

- **WHEN** the server starts and the schema version matches a known version
- **THEN** the SQLite reader initializes normally

#### Scenario: Unknown schema version

- **WHEN** the server starts and the schema version is unrecognized
- **THEN** a warning is logged
- **THEN** the system falls back to things-py for reads

### Requirement: Graceful fallback to things-py

The system SHALL fall back to things-py when the SQLite database is unavailable.

#### Scenario: Database file locked

- **WHEN** the SQLite database file is locked by another process
- **THEN** the read operation falls back to things-py transparently
- **THEN** a warning is logged

#### Scenario: Database file missing

- **WHEN** the SQLite database file does not exist at the expected path
- **THEN** the system falls back to things-py for all reads
- **THEN** a warning is logged on startup

### Requirement: Read performance target

Read operations via the SQLite layer SHALL meet the following latency targets.

#### Scenario: Large task list

- **WHEN** `get-tasks` is called with 200+ incomplete tasks
- **THEN** the response is returned in under 100ms (excluding network)

#### Scenario: Search operation

- **WHEN** `search-tasks` is called with a keyword query
- **THEN** the response is returned in under 50ms (excluding network)
