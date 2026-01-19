from langgraph.graph import END

from copium_loop.constants import MAX_RETRIES
from copium_loop.nodes import (
    should_continue_from_pr_creator,
    should_continue_from_review,
    should_continue_from_test,
)


class TestConditionalLogic:
    """Tests for conditional state transitions."""

    def test_should_continue_from_test_on_pass(self):
        """Test transition from test to reviewer on pass."""
        assert should_continue_from_test({"test_output": "PASS"}) == "reviewer"

    def test_should_continue_from_test_on_fail(self):
        """Test transition from test to coder on fail."""
        assert (
            should_continue_from_test({"test_output": "FAIL", "retry_count": 0})
            == "coder"
        )

    def test_should_continue_from_test_max_retries(self):
        """Test END transition on max retries."""
        assert (
            should_continue_from_test(
                {"test_output": "FAIL", "retry_count": MAX_RETRIES + 1}
            )
            == END
        )

    def test_should_continue_from_review_on_approved(self):
        """Test transition from review to pr_creator on approval."""
        assert (
            should_continue_from_review({"review_status": "approved"}) == "pr_creator"
        )

    def test_should_continue_from_review_on_rejected(self):
        """Test transition from review to coder on rejection."""
        assert (
            should_continue_from_review({"review_status": "rejected", "retry_count": 0})
            == "coder"
        )

    def test_should_continue_from_pr_creator_on_success(self):
        """Test END transition on PR creation success."""
        assert should_continue_from_pr_creator({"review_status": "pr_created"}) == END

    def test_should_continue_from_pr_creator_on_needs_commit(self):
        """Test transition to coder on needs_commit."""
        assert (
            should_continue_from_pr_creator(
                {"review_status": "needs_commit", "retry_count": 0}
            )
            == "coder"
        )

    def test_should_continue_from_pr_creator_on_failure(self):
        """Test transition to coder on pr_failed."""
        assert (
            should_continue_from_pr_creator(
                {"review_status": "pr_failed", "retry_count": 0}
            )
            == "coder"
        )
