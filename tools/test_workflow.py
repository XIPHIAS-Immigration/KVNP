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
    assert "const checkerOnly = state.profile?.checkerOnly === true;" in app
    assert "elements.downloadPhoto.disabled = !preparedAvailable || checkerOnly;" in app
    assert "elements.printSheet.disabled = !preparedAvailable || checkerOnly;" in app
    assert "const photoReady = failCount === 0" not in app
    assert "showDownloadWarningDialog(issues);" in app
    print("test_warnings_do_not_gate_file_availability", PASS)


def test_guided_catalogue_and_studio_mode_are_present():
    html, app = load_sources()
    for element_id in (
        "programme-search",
        "category-filters",
        "programme-grid",
        "programme-mode",
        "programme-status",
        "programme-reviewed",
        "programme-notice",
        "coach-banner",
        "capture-readiness",
        "capture-readiness-grid",
        "preparation-receipt",
        "review-verdict",
        "verdict-recommendation",
        "verdict-file",
        "verdict-action",
        "selected-country-code",
        "selected-programme-name",
        "studio-crop-spec",
        "studio-crop-controls",
        "studio-tone-controls",
        "studio-background-controls",
        "studio-output-canvas",
        "studio-output-policy",
        "studio-mode-slot",
        "edit-mode-title",
        "tone-histogram",
    ):
        assert f'id="{element_id}"' in html, element_id
    assert 'data-workspace-mode="guided"' in html
    assert 'data-workspace-mode="studio"' in html
    assert "function renderProgrammeCatalogue()" in app
    assert "function getCatalogueMeta(" in app
    assert "function renderProgrammeNotice(" in app
    assert "function renderCoachBanner(" in app
    assert "function renderCaptureReadiness(" in app
    assert "function renderPreparationReceipt(" in app
    assert "function renderReviewVerdict(" in app
    assert "function mountStudioControls(" in app
    assert "function setStudioTool(" in app
    assert "function renderEditIntent(" in app
    assert "function loadSamplePortrait(" in app
    assert "function renderToneHistogram(" in app
    assert "const CATEGORY_ICONS =" in app
    assert 'document.body.dataset.workspaceMode = next;' in app
    print("test_guided_catalogue_and_studio_mode_are_present", PASS)


def test_colour_workstation_is_complete():
    html, app = load_sources()
    for key in ("exposure", "brightness", "contrast", "saturation", "warmth", "tint", "highlights", "shadows", "red", "green", "blue", "sharpness"):
        assert f'key: "{key}"' in app, key
    assert 'data-studio-open="tone"' in html
    assert 'data-tone-preset="natural"' in html
    assert "function applyTonePreset(" in app
    assert "All identity-preserving colour, lighting and backdrop tools are unlocked" in app
    print("test_colour_workstation_is_complete", PASS)


def test_guest_demo_library_and_walkthrough():
    html, app = load_sources()
    demo = (ROOT / "src" / "demo-library.js").read_text(encoding="utf-8")
    server = (ROOT / "server.py").read_text(encoding="utf-8")
    portraits = sorted((ROOT / "assets" / "demo").glob("*.jpg"))
    for element_id in (
        "demo-library",
        "demo-library-count",
        "demo-filters",
        "demo-grid",
        "demo-start",
        "demo-walkthrough",
        "demo-walkthrough-primary",
        "demo-walkthrough-secondary",
        "demo-walkthrough-close",
    ):
        assert f'id="{element_id}"' in html, element_id
    assert demo.count('path: "assets/demo/') == 24
    assert len(portraits) == 24, len(portraits)
    assert all(path.stat().st_size > 10_000 for path in portraits)
    assert "function renderDemoLibrary()" in app
    assert "function loadDemoPortrait(" in app
    assert "function renderDemoWalkthrough()" in app
    assert "elements.previewMode.checked = true;" in app
    assert "handlePreviewModeChange();" in app
    assert "elements.demoLibrary.hidden = !state.guestSession;" in app
    assert 'document.body.dataset.guest = state.guestSession ? "true" : "false";' in app
    assert 'app.mount("/assets", StaticFiles(directory=ROOT / "assets"), name="assets")' in server
    print("test_guest_demo_library_and_walkthrough", PASS)


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
        test_guided_catalogue_and_studio_mode_are_present,
        test_colour_workstation_is_complete,
        test_guest_demo_library_and_walkthrough,
        test_original_download_survives_processing_failure,
        test_background_variant_respects_programme_policy,
    ]
    for test in tests:
        test()
    print(f"\nAll {len(tests)} workflow tests passed.")


if __name__ == "__main__":
    main()
