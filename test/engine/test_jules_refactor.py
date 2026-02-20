import pytest

from copium_loop.engine.jules import JulesEngine


@pytest.mark.asyncio
async def test_jules_extract_summary_standard_verdict():
    """Verify that JulesEngine._extract_summary uses standard VERDICT: APPROVED."""
    engine = JulesEngine()

    status_data = {
        "outputs": [{"changeSet": {"gitPatch": {"unidiffPatch": "diff"}}}],
        "activities": [{"description": "Work done"}],
    }

    summary = engine._extract_summary(status_data)
    assert "VERDICT: APPROVED" in summary
    assert "IMPLICIT_VERDICT" not in summary


@pytest.mark.asyncio
async def test_jules_extract_summary_no_verdict_without_changeset():
    """Verify that JulesEngine._extract_summary doesn't add verdict if no changeset."""
    engine = JulesEngine()

    status_data = {
        "outputs": [],
        "activities": [{"description": "Work done"}],
    }

    summary = engine._extract_summary(status_data)
    assert "VERDICT: APPROVED" not in summary
