from copium_loop.ui.utils import get_workflow_status_style


def test_get_workflow_status_style_success():
    style = get_workflow_status_style("success")
    assert style["color"] == "cyan"
    assert style["suffix"] == " ✓ SUCCESS"


def test_get_workflow_status_style_failed():
    style = get_workflow_status_style("failed")
    assert style["color"] == "red"
    assert style["suffix"] == " ⚠ FAILED"


def test_get_workflow_status_style_running():
    style = get_workflow_status_style("running")
    assert style["color"] == "yellow"
    assert style["suffix"] == ""


def test_get_workflow_status_style_idle():
    style = get_workflow_status_style("idle")
    assert style["color"] == "yellow"
    assert style["suffix"] == ""


def test_get_workflow_status_style_unknown():
    style = get_workflow_status_style("unknown")
    assert style["color"] == "yellow"
    assert style["suffix"] == ""
