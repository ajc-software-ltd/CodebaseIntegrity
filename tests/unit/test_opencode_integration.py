"""OpenCode integration artifact tests (PLAN.md §15)."""

import json
import re
from pathlib import Path

from typer.testing import CliRunner

from cii.cli.commands import app

REPO_ROOT = Path(__file__).resolve().parents[2]
INTEGRATIONS = REPO_ROOT / "integrations" / "opencode"
SKILL_PATH = INTEGRATIONS / "skills" / "codebase-integrity" / "SKILL.md"
AGENT_PATH = INTEGRATIONS / "agents" / "codebase-auditor.md"
AGENTS_MD_PATH = INTEGRATIONS / "AGENTS.md"
DOC_PATH = REPO_ROOT / "docs" / "OPENCode_INTEGRATION.md"

runner = CliRunner()


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "frontmatter block missing"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


class TestSkill:
    def test_frontmatter(self) -> None:
        fields = _frontmatter(SKILL_PATH.read_text())
        assert fields["name"] == "Codebase Integrity"
        assert "CII" in fields["description"]

    def test_covers_required_workflow(self) -> None:
        body = SKILL_PATH.read_text()
        for phrase in [
            "index_status", "index_search", "index_file", "index_scan",
            "index_validate", "Retrieve the actual source", "Do not duplicate",
            "Respect established structure", "Run the project's tests",
            "Report integrity honestly",
        ]:
            assert phrase in body, f"skill is missing required guidance: {phrase}"


class TestAuditorAgent:
    def test_frontmatter_is_read_only_subagent(self) -> None:
        text = AGENT_PATH.read_text()
        fields = _frontmatter(text)
        assert fields["mode"] == "subagent"
        assert fields["description"]
        assert "- action: edit" in text and "effect: deny" in text
        assert "- action: shell" in text

    def test_covers_required_responsibilities(self) -> None:
        body = AGENT_PATH.read_text()
        for phrase in [
            "index health", "missing or unindexed files", "duplicate symbols",
            "stale entries", "namespace consistency", "Compare index records",
            "Report every discrepancy", "Recommend corrective action",
            "never modify source code",
        ]:
            assert phrase in body, f"auditor is missing responsibility: {phrase}"


class TestAgentsMd:
    def test_six_rules_present(self) -> None:
        text = AGENTS_MD_PATH.read_text()
        for rule in [
            "Structural Discovery Rule", "Source Verification Rule",
            "Duplicate Prevention Rule", "Index Integrity Rule",
            "Post-Development Rule", "Failure Rule",
        ]:
            assert rule in text, f"AGENTS.md is missing rule: {rule}"


class TestIntegrationDoc:
    def test_embedded_snippet_is_valid_config(self) -> None:
        text = DOC_PATH.read_text()
        blocks = re.findall(r"```jsonc\n(.*?)```", text, re.DOTALL)
        assert blocks, "no jsonc snippet found"
        # strip line comments and parse the primary registration snippet
        cleaned = "\n".join(
            line for line in blocks[0].splitlines() if not line.strip().startswith("//")
        )
        payload = json.loads(cleaned)
        command = payload["mcp"]["servers"]["cii"]["command"]
        assert command[-3:] == ["mcp", "--root", "/path/to/project"] or command[-2] == "mcp"
        assert payload["mcp"]["servers"]["cii"]["type"] == "local"

    def test_explains_placement_and_no_global_assumption(self) -> None:
        text = DOC_PATH.read_text()
        flat = " ".join(text.split())
        assert "project-level configuration" in flat
        assert "do not assume a global" in flat.lower()


class TestOpenCodeConfigCommand:
    def test_generates_snippet_with_resolved_paths(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["opencode-config", "--root", str(tmp_path), "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        command = payload["snippet"]["mcp"]["servers"]["cii"]["command"]
        assert command[1:4] == ["-m", "cii", "mcp"]
        assert command[-1] == str(tmp_path.resolve())
        assert "project-level configuration" in payload["placement"]

    def test_human_output_mentions_alternative_launcher(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["opencode-config", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "never edits OpenCode configuration" in result.stdout
        assert '"mcp"' in result.stdout
