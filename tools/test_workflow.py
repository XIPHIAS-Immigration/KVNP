"""Static regressions for the four-stage browser workflow."""

from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PASS = "  ok"


class WorkflowParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.workflow_steps = []
        self.wizard_panels = []

    def handle_starttag(self, _tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"])
        if values.get("data-workflow-step"):
            self.workflow_steps.append(values["data-workflow-step"])
        if values.get("data-wizard-panel"):
            self.wizard_panels.append(values["data-wizard-panel"])


def load_sources():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "src" / "app.js").read_text(encoding="utf-8")
    return html, app


def test_four_stage_structure():
    html, _ = load_sources()
    parser = WorkflowParser()
    parser.feed(html)
    assert parser.workflow_steps == ["1", "2", "3", "4"], parser.workflow_steps
    assert sorted(parser.wizard_panels) == ["1", "2", "3", "4"], parser.wizard_panels
    assert len(parser.ids) == len(set(parser.ids)), "duplicate HTML ids"
    print("test_four_stage_structure", PASS)


def test_review_outputs_are_present():
    html, _ = load_sources()
    required_ids = (
        "download-original",
        "download-photo",
        "download-report",
        "background-variant",
        "review-source-quality-list",
        "review-photo-image",
        "document-preview-photo",
        "download-warning-dialog",
    )
    for element_id in required_ids:
        assert f'id="{element_id}"' in html, element_id
    assert "PREVIEW ONLY / NOT AN OFFICIAL DOCUMENT" in html
    assert 'id="background-variant-dialog"' in html
    print("test_review_outputs_are_present", PASS)


def test_warnings_do_not_gate_file_availability():
    _, app = load_sources()
    assert "const preparedAvailable = Boolean(state.exportBlob && state.processedImage);" in app
    assert "elements.downloadPhoto.disabled = !preparedAvailable;" in app
    assert "elements.printSheet.disabled = !preparedAvailable;" in app
    assert "const photoReady = failCount === 0" not in app
    assert "showDownloadWarningDialog(issues);" in app
    print("test_warnings_do_not_gate_file_availability", PASS)


def test_original_download_survives_processing_failure():
    _, app = load_sources()
    assert "function downloadOriginal()" in app
    assert "downloadBlob(state.originalFile" in app
    assert "elements.downloadOriginal.disabled = !state.originalFile;" in app
    print("test_original_download_survives_processing_failure", PASS)


def test_background_variant_respects_programme_policy():
    _, app = load_sources()
    assert "function backgroundVariantIsSubmissionEligible()" in app
    assert "previewMode: !eligible" in app
    assert "background-preview-not-for-submission" in app
    assert "The current prepared file will not be replaced." in app
    print("test_background_variant_respects_programme_policy", PASS)


def main():
    tests = [
        test_four_stage_structure,
        test_review_outputs_are_present,
        test_warnings_do_not_gate_file_availability,
        test_original_download_survives_processing_failure,
        test_background_variant_respects_programme_policy,
    ]
    for test in tests:
        test()
    print(f"\nAll {len(tests)} workflow tests passed.")


if __name__ == "__main__":
    main()
