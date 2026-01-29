from langgraph.graph.state import CompiledStateGraph

from copium_loop.graph import create_graph


def test_create_graph():
    graph = create_graph(lambda _name, func: func)
    assert isinstance(graph, CompiledStateGraph)
    # Check that it has the expected nodes
    assert "coder" in graph.nodes
    assert "tester" in graph.nodes
    assert "reviewer" in graph.nodes
    assert "pr_creator" in graph.nodes
