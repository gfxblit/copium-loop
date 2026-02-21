from copium_loop.engine.jules import JulesEngine


def test_extract_summary_concatenation():
    """Verify that _extract_summary concatenates unique messages from all activities."""
    engine = JulesEngine()
    status_data = {
        "activities": [
            {"agentMessaged": {"text": "First message."}},
            {"progressUpdated": {"description": "Progress update."}},
            {"agentMessaged": {"message": "Second message with VERDICT: APPROVED"}},
            {"sessionCompleted": {}},
        ],
        "outputs": [
            {
                "pullRequest": {
                    "url": "https://github.com/owner/repo/pull/1",
                    "title": "PR Title",
                }
            }
        ],
    }

    summary = engine._extract_summary(status_data)

    assert "First message." in summary
    assert "Progress update." in summary
    assert "Second message with VERDICT: APPROVED" in summary
    assert "PR Created: https://github.com/owner/repo/pull/1" in summary
    # Check that it's concatenated with newlines
    assert "\n" in summary


def test_extract_summary_uniqueness():
    """Verify that duplicate messages are not repeated in the summary."""
    engine = JulesEngine()
    status_data = {
        "activities": [
            {"agentMessaged": {"text": "Same message."}},
            {"progressUpdated": {"description": "Same message."}},
            {"agentMessaged": {"message": "Different message."}},
        ]
    }

    summary = engine._extract_summary(status_data)
    assert summary.count("Same message.") == 1
    assert "Different message." in summary


def test_extract_summary_with_changeset():
    """Verify that _extract_summary adds IMPLICIT_VERDICT: APPROVED if a changeSet is present."""
    engine = JulesEngine()
    status_data = {
        "activities": [{"text": "Found some issues and fixed them."}],
        "outputs": [{"changeSet": {"gitPatch": {"unidiffPatch": "..."}}}],
    }

    summary = engine._extract_summary(status_data)
    assert "VERDICT: APPROVED" in summary
