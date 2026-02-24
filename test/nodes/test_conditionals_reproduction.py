from langgraph.graph import END

from copium_loop.nodes import (
    should_continue_from_architect,
    should_continue_from_coder,
    should_continue_from_journaler,
    should_continue_from_pr_creator,
    should_continue_from_pr_pre_checker,
    should_continue_from_review,
    should_continue_from_test,
)


class TestConditionalsReproduction:
    """Reproduction tests for stale infrastructure errors."""

    def test_should_continue_if_error_is_from_different_node(self):
        """
        Verify that a node continues even if last_error contains an infra error,
        as long as that error didn't happen in the CURRENT node.
        """
        stale_error = "Node 'coder' failed with error: fatal: unable to access 'https://github.com/...' "

        # We are now in 'tester' (via should_continue_from_test)
        # It should NOT return END because the error is from 'coder'
        state = {"test_output": "PASS", "last_error": stale_error, "retry_count": 0}

        # It should return 'architect' (normal success path for tester)
        assert should_continue_from_test(state) == "architect"

    def test_should_continue_if_error_is_from_previous_node_on_fail(self):
        """
        Verify that a node correctly identifies a normal failure even if
        a stale infra error from a previous node is present.
        """
        stale_error = "Node 'coder' failed with error: fatal: unable to access 'https://github.com/...' "

        # We are now in 'tester', and it failed (normal failure, not infra)
        state = {"test_output": "FAIL", "last_error": stale_error, "retry_count": 0}

        # It should return 'coder' (normal retry path for tester failure)
        assert should_continue_from_test(state) == "coder"

    def test_should_continue_if_error_is_from_reviewer_in_tester(self):
        """
        Verify that tester continues if there is a stale error from reviewer.
        """
        stale_error = "Node 'reviewer' failed with error: fatal: unable to access 'https://github.com/...' "

        state = {"test_output": "FAIL", "last_error": stale_error, "retry_count": 0}

        # It should return 'coder', not END
        assert should_continue_from_test(state) == "coder"

    def test_all_nodes_ignore_stale_errors(self):
        """Verify that all nodes ignore errors from other nodes."""
        stale_error = "Node 'other' failed with error: fatal: unable to access..."

        # Coder
        assert (
            should_continue_from_coder(
                {"code_status": "coded", "last_error": stale_error}
            )
            == "tester"
        )
        # Architect
        assert (
            should_continue_from_architect(
                {"architect_status": "ok", "last_error": stale_error}
            )
            == "reviewer"
        )
        # Reviewer
        assert (
            should_continue_from_review(
                {"review_status": "approved", "last_error": stale_error}
            )
            == "pr_pre_checker"
        )
        # PR Pre-Checker
        assert (
            should_continue_from_pr_pre_checker(
                {"review_status": "pre_check_passed", "last_error": stale_error}
            )
            == "pr_creator"
        )
        # PR Creator
        assert (
            should_continue_from_pr_creator(
                {"review_status": "pr_created", "last_error": stale_error}
            )
            == END
        )
        # Journaler
        assert (
            should_continue_from_journaler(
                {"review_status": "pending", "last_error": stale_error}
            )
            == END
        )
