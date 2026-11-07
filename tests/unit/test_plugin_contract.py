"""Plugin structure tests (PLAN.md §15.5).

The plugin is TypeScript executed by OpenCode's runtime; these tests pin its
contract (default export, supported hooks, failure handling). Behaviour is
verified live in OpenCode (see CHANGELOG M11 verification notes).
"""

from pathlib import Path

PLUGIN_PATH = (
    Path(__file__).resolve().parents[2]
    / "integrations" / "opencode" / "plugin" / "cii.ts"
)


class TestPluginContract:
    def test_exists_and_uses_v2_api(self) -> None:
        text = PLUGIN_PATH.read_text()
        assert 'Plugin.define({' in text
        assert 'id: "cii"' in text
        assert "export default" in text

    def test_uses_only_supported_lifecycle_hooks(self) -> None:
        text = PLUGIN_PATH.read_text()
        for hook in [
            'ctx.tool.hook("execute.before"',
            'ctx.tool.hook("execute.after"',
            'ctx.session.hook("context"',
            "ctx.tool.transform(",
            "ctx.command.transform(",
        ]:
            assert hook in text, f"plugin is missing required registration: {hook}"

    def test_is_not_a_second_indexing_engine(self) -> None:
        text = PLUGIN_PATH.read_text()
        # it must go through the CLI, never duplicate indexing logic
        assert 'runCii(command' in text
        for forbidden in ["tree_sitter", "tree-sitter", "sqlite3.connect", "CREATE TABLE"]:
            assert forbidden not in text

    def test_failure_handling_present(self) -> None:
        text = PLUGIN_PATH.read_text()
        assert "timeout: 30_000" in text
        assert "CII status unavailable" in text
        assert "structural verification could NOT be performed" in text
        assert "tool hooks unavailable" in text

    def test_contextual_reminder_content(self) -> None:
        text = PLUGIN_PATH.read_text()
        assert "CII integrity reminder" in text
        assert "index_scan" in text
        assert "index_validate" in text

    def test_readonly_status_tool(self) -> None:
        text = PLUGIN_PATH.read_text()
        assert 'name: "cii_status"' in text
        assert "Read-only" in text
