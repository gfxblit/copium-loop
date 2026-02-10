from langgraph.graph import END

from copium_loop import constants
from copium_loop.nodes import (
    should_continue_from_architect,
    should_continue_from_coder,
    should_continue_from_journaler,
    should_continue_from_pr_creator,
    should_continue_from_pr_pre_checker,
    should_continue_from_review,
    should_continue_from_test,
)


class TestConditionalLogic:
    """Tests for conditional state transitions."""

    def test_should_continue_from_test_on_pass(self):
        """Test transition from test to architect on pass."""
        assert should_continue_from_test({"test_output": "PASS"}) == "architect"

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
                {"test_output": "FAIL", "retry_count": constants.MAX_RETRIES}
            )
            == END
        )
        assert (
            should_continue_from_test(
                {"test_output": "FAIL", "retry_count": constants.MAX_RETRIES + 1}
            )
            == END
        )

    def test_should_continue_from_architect_on_ok(self):
        """Test transition from architect to reviewer on ok."""
        assert should_continue_from_architect({"architect_status": "ok"}) == "reviewer"

    def test_should_continue_from_architect_on_refactor(self):
        """Test transition from architect to coder on refactor."""
        assert (
            should_continue_from_architect(
                {"architect_status": "refactor", "retry_count": 0}
            )
            == "coder"
        )

    def test_should_continue_from_architect_on_error(self):
        """Test transition from architect to architect on error."""
        assert (
            should_continue_from_architect(
                {"architect_status": "error", "retry_count": 0}
            )
            == "architect"
        )

    def test_should_continue_from_architect_max_retries(self):
        """Test END transition on max retries from architect."""
        assert (
            should_continue_from_architect(
                {
                    "architect_status": "refactor",
                    "retry_count": constants.MAX_RETRIES,
                }
            )
            == END
        )
        assert (
            should_continue_from_architect(
                {
                    "architect_status": "refactor",
                    "retry_count": constants.MAX_RETRIES + 1,
                }
            )
            == END
        )
        assert (
            should_continue_from_architect(
                {"architect_status": "error", "retry_count": constants.MAX_RETRIES}
            )
            == END
        )
        assert (
            should_continue_from_architect(
                {"architect_status": "error", "retry_count": constants.MAX_RETRIES + 1}
            )
            == END
        )

    def test_should_continue_from_review_on_approved(self):
        """Test transition from review to pr_pre_checker on approval."""
        assert (
            should_continue_from_review({"review_status": "approved"})
            == "pr_pre_checker"
        )

    def test_should_continue_from_review_on_rejected(self):
        """Test transition from review to coder on rejection."""
        assert (
            should_continue_from_review({"review_status": "rejected", "retry_count": 0})
            == "coder"
        )

    def test_should_continue_from_review_on_error(self):
        """Test transition from review to reviewer on error."""
        assert (
            should_continue_from_review({"review_status": "error", "retry_count": 0})
            == "reviewer"
        )

    def test_should_continue_from_review_max_retries(self):
        """Test END transition on max retries from reviewer."""
        assert (
            should_continue_from_review(
                {"review_status": "rejected", "retry_count": constants.MAX_RETRIES}
            )
            == END
        )
        assert (
            should_continue_from_review(
                {"review_status": "rejected", "retry_count": constants.MAX_RETRIES + 1}
            )
            == END
        )
        assert (
            should_continue_from_review(
                {"review_status": "error", "retry_count": constants.MAX_RETRIES}
            )
            == END
        )
        assert (
            should_continue_from_review(
                {"review_status": "error", "retry_count": constants.MAX_RETRIES + 1}
            )
            == END
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

    def test_should_continue_from_pr_creator_max_retries(self):
        """Test END transition on max retries from pr_creator."""
        assert (
            should_continue_from_pr_creator(
                {"review_status": "pr_failed", "retry_count": constants.MAX_RETRIES + 1}
            )
            == END
        )

    def test_should_continue_from_pr_pre_checker_on_success(self):
        """Test journaler transition on success from pr_pre_checker."""
        assert (
            should_continue_from_pr_pre_checker({"review_status": "pre_check_passed"})
            == "pr_creator"
        )

    def test_should_continue_from_pr_pre_checker_on_skipped(self):
        """Test journaler transition on skipped from pr_pre_checker."""
        assert (
            should_continue_from_pr_pre_checker({"review_status": "pr_skipped"}) == END
        )

    def test_should_continue_from_pr_pre_checker_on_failure(self):
        """Test coder transition on failure from pr_pre_checker."""
        assert (
            should_continue_from_pr_pre_checker({"review_status": "pr_failed"})
            == "coder"
        )

    def test_should_continue_from_journaler_on_pr_flow(self):
        """Test pr_creator transition from journaler if in PR flow."""
        assert (
            should_continue_from_journaler({"review_status": "pre_check_passed"})
            == "pr_creator"
        )

    def test_should_continue_from_journaler_on_normal_flow(self):
        """Test END transition from journaler if not in PR flow."""
        assert should_continue_from_journaler({"review_status": "pending"}) == END

    def test_should_continue_from_coder_on_success(self):
        """Test transition from coder to tester on success."""
        assert should_continue_from_coder({"code_status": "coded"}) == "tester"

    def test_should_continue_from_coder_on_fail_retry(self):
        """Test transition from coder back to coder on fail if retries available."""
        assert (
            should_continue_from_coder({"code_status": "failed", "retry_count": 0})
            == "coder"
        )
        assert (
            should_continue_from_coder(
                {"code_status": "failed", "retry_count": constants.MAX_RETRIES - 1}
            )
            == "coder"
        )

    def test_should_continue_from_coder_max_retries(self):
        """Test END transition on max retries from coder."""
        assert (
            should_continue_from_coder(
                {"code_status": "failed", "retry_count": constants.MAX_RETRIES}
            )
            == END
        )
        assert (
            should_continue_from_coder(
                {"code_status": "failed", "retry_count": constants.MAX_RETRIES + 1}
            )
            == END
        )
