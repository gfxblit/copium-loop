from unittest.mock import MagicMock, patch

from langgraph.graph import END

from copium_loop.graph import create_graph
from copium_loop.nodes.conditionals import should_continue_from_pr_pre_checker


class TestIssue59:

    @patch('copium_loop.nodes.conditionals.get_telemetry')
    def test_pr_pre_checker_bypasses_journaler(self, mock_get_telemetry):
        # Setup
        mock_telemetry = MagicMock()
        mock_get_telemetry.return_value = mock_telemetry

        state = {"review_status": "pre_check_passed"}

        # Action
        # This function currently returns "journaler" (based on reading the code)
        # We expect it to return "pr_creator" after the fix.
        next_node = should_continue_from_pr_pre_checker(state)

        # Assert
        assert next_node == "pr_creator"

    def test_graph_edges_bypass_journaler(self):
        # Verify that graph edges are updated to remove automatic routing to journaler
        with patch('copium_loop.graph.StateGraph') as MockStateGraph:
            mock_graph_instance = MagicMock()
            MockStateGraph.return_value = mock_graph_instance
            mock_graph_instance.compile.return_value = MagicMock()

            def wrap(_name, func): return func
            create_graph(wrap)

            # Capture all calls to add_conditional_edges
            calls = mock_graph_instance.add_conditional_edges.call_args_list

            # Helper to find call for a start node
            def get_mapping_for(node_name):
                for call in calls:
                    args, _ = call
                    if args[0] == node_name:
                        return args[2] # The mapping dict
                return None

            # 1. tester -> END should NOT go to journaler
            tester_map = get_mapping_for("tester")
            assert tester_map.get(END) != "journaler", f"Tester maps END to {tester_map.get(END)}"

            # 2. architect -> END should NOT go to journaler
            arch_map = get_mapping_for("architect")
            assert arch_map.get(END) != "journaler", f"Architect maps END to {arch_map.get(END)}"

            # 3. reviewer -> END/pr_failed should NOT go to journaler
            rev_map = get_mapping_for("reviewer")
            assert rev_map.get(END) != "journaler", f"Reviewer maps END to {rev_map.get(END)}"
            assert rev_map.get("pr_failed") != "journaler", f"Reviewer maps pr_failed to {rev_map.get('pr_failed')}"

            # 4. pr_pre_checker -> should route to pr_creator
            pre_check_map = get_mapping_for("pr_pre_checker")
            assert pre_check_map.get(END) != "journaler", f"PR Pre-checker maps END to {pre_check_map.get(END)}"
            # Verify connection to pr_creator is present (key must match return value of conditional)
            # The test_pr_pre_checker_bypasses_journaler expects return value "pr_creator"
            # So the map should contain "pr_creator": "pr_creator" or similar
            assert "pr_creator" in pre_check_map, "PR Pre-checker mapping missing 'pr_creator'"
            assert pre_check_map["pr_creator"] == "pr_creator"
