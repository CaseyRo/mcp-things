"""Pytest plugin to capture and store test results in Markdown format."""
import json
import pytest
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import subprocess


class TestResultsPlugin:
    """Plugin to capture test results and store them in Markdown."""

    def __init__(self, config):
        self.config = config
        self.results_dir = Path("test-results")
        self.results_dir.mkdir(exist_ok=True)
        self.results_file = self.results_dir / "test-results.md"
        self.current_run: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "tests": [],
            "summary": {},
        }

    def pytest_runtest_logreport(self, report):
        """Capture test report data."""
        if report.when == "call":  # Only capture final test results
            # Extract markers properly - report.keywords is a dict where keys are strings
            markers = []
            if hasattr(report, "keywords"):
                # Get marker names from keywords dict
                for key in report.keywords.keys():
                    if key not in ["parametrize"] and not key.startswith("_"):
                        # Check if it's a marker by looking at the item
                        if hasattr(report, "nodeid"):
                            markers.append(key)

            test_info = {
                "name": report.nodeid,
                "outcome": report.outcome,
                "duration": getattr(report, "duration", 0),
                "markers": markers,
            }

            if report.outcome == "failed":
                test_info["error"] = str(report.longrepr) if hasattr(report, "longrepr") else None
                test_info["error_message"] = report.longreprtext if hasattr(report, "longreprtext") else None

            if report.outcome == "skipped":
                test_info["skip_reason"] = report.longreprtext if hasattr(report, "longreprtext") else None

            self.current_run["tests"].append(test_info)

    def pytest_sessionfinish(self, session, exitstatus):
        """Store test results when session finishes."""
        # Get summary from session
        self.current_run["summary"] = {
            "total": session.testscollected if hasattr(session, "testscollected") else 0,
            "passed": len([t for t in self.current_run["tests"] if t["outcome"] == "passed"]),
            "failed": len([t for t in self.current_run["tests"] if t["outcome"] == "failed"]),
            "skipped": len([t for t in self.current_run["tests"] if t["outcome"] == "skipped"]),
            "errors": len([t for t in self.current_run["tests"] if t["outcome"] == "error"]),
            "duration": sum(t["duration"] for t in self.current_run["tests"]),
            "exit_status": exitstatus,
        }

        # Store this run
        self._store_test_results()

    def _store_test_results(self):
        """Store test results, keeping only the last 3 runs."""
        # Read existing results
        runs = self._load_existing_runs()

        # Add current run
        runs.insert(0, self.current_run)

        # Keep only last 3 runs
        runs = runs[:3]

        # Write to Markdown
        self._write_markdown(runs)

        # Also store JSON for programmatic access
        json_file = self.results_dir / "test-results.json"
        with open(json_file, "w") as f:
            json.dump(runs, f, indent=2)

    def _load_existing_runs(self) -> List[Dict[str, Any]]:
        """Load existing test runs from JSON if available."""
        json_file = self.results_dir / "test-results.json"
        if json_file.exists():
            try:
                with open(json_file, "r") as f:
                    runs = json.load(f)
                    # Remove current run if it exists (in case of re-run)
                    runs = [r for r in runs if r.get("timestamp") != self.current_run["timestamp"]]
                    return runs
            except Exception:
                pass
        return []

    def _write_markdown(self, runs: List[Dict[str, Any]]):
        """Write test results to Markdown file."""
        md_lines = [
            "# Test Results History",
            "",
            "This file contains the last 3 test runs. Results are automatically updated after each test run.",
            "",
            "---",
            "",
        ]

        for idx, run in enumerate(runs, 1):
            timestamp = datetime.fromisoformat(run["timestamp"])
            formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")

            summary = run["summary"]
            total = summary.get("total", 0)
            passed = summary.get("passed", 0)
            failed = summary.get("failed", 0)
            skipped = summary.get("skipped", 0)
            errors = summary.get("errors", 0)
            duration = summary.get("duration", 0)
            exit_status = summary.get("exit_status", 0)

            # Status emoji
            if exit_status == 0:
                status_emoji = "✅"
            elif failed > 0 or errors > 0:
                status_emoji = "❌"
            else:
                status_emoji = "⚠️"

            md_lines.extend([
                f"## Run #{idx} - {formatted_time} {status_emoji}",
                "",
                f"**Status:** {'PASSED' if exit_status == 0 else 'FAILED'}",
                f"**Duration:** {duration:.2f}s",
                "",
                "### Summary",
                "",
                "| Metric | Count |",
                "|--------|-------|",
                f"| Total Tests | {total} |",
                f"| ✅ Passed | {passed} |",
                f"| ❌ Failed | {failed} |",
                f"| ⏭️ Skipped | {skipped} |",
                f"| ⚠️ Errors | {errors} |",
                "",
            ])

            # Failed tests
            failed_tests = [t for t in run["tests"] if t["outcome"] == "failed"]
            if failed_tests:
                md_lines.extend([
                    "### Failed Tests",
                    "",
                ])
                for test in failed_tests:
                    test_name = test["name"].split("::")[-1]
                    md_lines.append(f"- **{test_name}** (`{test['name']}`)")
                    if test.get("error_message"):
                        # Truncate long error messages
                        error_msg = test["error_message"]
                        if len(error_msg) > 500:
                            error_msg = error_msg[:500] + "... (truncated)"
                        md_lines.append(f"  ```\n  {error_msg}\n  ```")
                    md_lines.append("")

            # Skipped tests
            skipped_tests = [t for t in run["tests"] if t["outcome"] == "skipped"]
            if skipped_tests:
                md_lines.extend([
                    "### Skipped Tests",
                    "",
                ])
                for test in skipped_tests:
                    test_name = test["name"].split("::")[-1]
                    skip_reason = test.get("skip_reason", "No reason provided")
                    if len(skip_reason) > 200:
                        skip_reason = skip_reason[:200] + "..."
                    md_lines.append(f"- **{test_name}** - {skip_reason}")
                md_lines.append("")

            # Test breakdown by marker
            markers = {}
            for test in run["tests"]:
                for marker in test.get("markers", []):
                    if marker not in ["parametrize"]:
                        if marker not in markers:
                            markers[marker] = {"passed": 0, "failed": 0, "skipped": 0}
                        markers[marker][test["outcome"]] = markers[marker].get(test["outcome"], 0) + 1

            if markers:
                md_lines.extend([
                    "### Test Breakdown by Marker",
                    "",
                    "| Marker | Passed | Failed | Skipped |",
                    "|--------|--------|--------|---------|",
                ])
                for marker, counts in sorted(markers.items()):
                    md_lines.append(
                        f"| `{marker}` | {counts.get('passed', 0)} | {counts.get('failed', 0)} | {counts.get('skipped', 0)} |"
                    )
                md_lines.append("")

            md_lines.extend([
                "---",
                "",
            ])

        # Write to file
        with open(self.results_file, "w") as f:
            f.write("\n".join(md_lines))

        print(f"\n📊 Test results saved to: {self.results_file}")


def pytest_configure(config):
    """Register the plugin."""
    # Only register if not already registered (prevents duplicate registration)
    if not hasattr(config, "_test_results_plugin_registered"):
        config.pluginmanager.register(TestResultsPlugin(config), "test_results_plugin")
        config._test_results_plugin_registered = True

