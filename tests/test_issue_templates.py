from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
ISSUE_TEMPLATE_DIR = ROOT / ".github" / "ISSUE_TEMPLATE"
BUG_REPORT_FORM = ISSUE_TEMPLATE_DIR / "bug_report.yml"
BUG_REPORT_MARKDOWN = ISSUE_TEMPLATE_DIR / "bug_report.md"
ISSUE_TEMPLATE_CONFIG = ISSUE_TEMPLATE_DIR / "config.yml"


def _body_item(form, item_id):
    for item in form["body"]:
        if item.get("id") == item_id:
            return item
    raise AssertionError(f"Missing issue form item: {item_id}")


def test_bug_report_uses_single_required_issue_form():
    assert BUG_REPORT_FORM.exists()
    assert not BUG_REPORT_MARKDOWN.exists()
    assert ISSUE_TEMPLATE_CONFIG.exists()

    form = yaml.safe_load(BUG_REPORT_FORM.read_text(encoding="utf-8"))
    config = yaml.safe_load(ISSUE_TEMPLATE_CONFIG.read_text(encoding="utf-8"))

    assert config["blank_issues_enabled"] is False
    assert form["title"] == "[Bug] "
    assert "bug" in form["labels"]
    assert isinstance(form["body"], list)


def test_bug_report_requires_reproducible_bug_context():
    form = yaml.safe_load(BUG_REPORT_FORM.read_text(encoding="utf-8"))

    required_text_fields = {
        "local_commit",
        "actions_commit",
        "problem",
        "steps",
        "expected",
        "actual",
        "logs",
        "os",
        "python_version",
        "run_mode",
        "config",
    }

    for item_id in required_text_fields:
        item = _body_item(form, item_id)
        assert item.get("validations", {}).get("required") is True

    latest_code = _body_item(form, "latest_code")
    assert latest_code["type"] == "checkboxes"
    assert latest_code["attributes"]["options"][0]["required"] is True
