from gamr_engine.judges.registry import get_judge_pipeline
from langgraph.graph import END, START


def test_evidence_and_content_topology_nodes_and_edges() -> None:
    pipeline = get_judge_pipeline("evidence-and-content")
    graph = pipeline.graph
    drawable_graph = graph.get_graph()

    nodes = set(drawable_graph.nodes.keys())
    expected_nodes = {
        "prepare_verified_content",
        "decode_trajectory_content",
        "compare_reference_content",
        "preserve_execution_failure",
        "assess_evidence",
        "finalize_judgment",
    }
    assert expected_nodes.issubset(nodes)

    edge_tuples = {(edge.source, edge.target) for edge in drawable_graph.edges}
    assert (START, "prepare_verified_content") in edge_tuples
    assert ("prepare_verified_content", "decode_trajectory_content") in edge_tuples
    assert ("decode_trajectory_content", "compare_reference_content") in edge_tuples
    assert ("preserve_execution_failure", END) in edge_tuples
    assert ("assess_evidence", "finalize_judgment") in edge_tuples
    assert ("finalize_judgment", END) in edge_tuples


def test_evidence_and_content_topology_inspectable_without_side_effects() -> None:
    pipeline = get_judge_pipeline("evidence-and-content")
    g1 = pipeline.graph.get_graph()
    g2 = pipeline.graph.get_graph()
    assert set(g1.nodes.keys()) == set(g2.nodes.keys())
    assert set((e.source, e.target) for e in g1.edges) == set(
        (e.source, e.target) for e in g2.edges
    )
