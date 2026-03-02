## 1. Pre-flight Checks

- [x] 1.1 Verify UV is available and working in the project
- [x] 1.2 Test current bash script functionality to understand all features
- [x] 1.3 Document current argument parsing and environment variable handling
- [x] 1.4 Add python-dotenv dependency to pyproject.toml

## 2. UV Script Configuration

- [x] 2.1 Add UV scripts section to `pyproject.toml`
- [x] 2.2 Configure `server` script to run `things_fast_server.py`
- [x] 2.3 Configure `dev` script for development mode
- [x] 2.4 Test UV script execution locally

## 3. Environment Variable Handling

- [x] 3.1 Add dotenv loading to FastMCP server startup
- [x] 3.2 Create `.env.example` file with default configuration values
- [x] 3.3 Verify `THINGS_MCP_HOST` and `THINGS_MCP_PORT` work with UV scripts and .env files
- [x] 3.4 Test environment variable overrides with UV scripts
- [x] 3.5 Verify default values (127.0.0.1:8009) are maintained

## 4. Documentation Updates

- [x] 4.1 Update README.md Quick Start section to use UV commands
- [x] 4.2 Update any other documentation references to bash script
- [x] 4.3 Add migration guide for existing users

## 5. Testing and Validation

- [x] 5.1 Test UV script execution on clean environment
- [x] 5.2 Verify all server functionality works with UV scripts
- [x] 5.3 Test environment variable configuration scenarios
- [x] 5.4 Run existing test suite to ensure no regressions

## 6. Cleanup

- [x] 6.1 Remove `run_things_fastmcp.sh` file
- [x] 6.2 Update any references in project files
- [x] 6.3 Clean up any bash-specific documentation

## 7. Final Validation

- [x] 7.1 Test complete user workflow with UV scripts
- [x] 7.2 Verify OpenSpec proposal validation passes
- [x] 7.3 Confirm all tasks are completed and documented
