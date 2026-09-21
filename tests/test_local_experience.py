from typing import cast

from local_experience.api.recorded import recorded_result
from local_experience.api.scene import project_scene, scene_payload


def test_recorded_scene_preserves_source_qualified_graph_and_citations() -> None:
    scene = project_scene(recorded_result(), mode="recorded")
    payload = scene_payload(scene)

    assert scene.mode == "recorded"
    assert {node.kind for node in scene.nodes} >= {"project", "organization", "output", "evidence"}
    assert all(edge.source_url for edge in scene.edges)
    evidence = cast(list[dict[str, object]], payload["evidence"])
    brief = cast(dict[str, object], payload["brief"])
    recommendation = cast(dict[str, object], brief["recommendation"])
    citations = cast(list[dict[str, object]], recommendation["citations"])
    assert len(evidence) == 3
    assert cast(str, citations[0]["evidence_id"]).startswith(
        "publication:"
    )


def test_recorded_scene_is_current_only_and_does_not_claim_live_data() -> None:
    scene = project_scene(recorded_result(), mode="recorded")

    assert scene.gaps == (
        "This recorded UX snapshot is current-only; historical requests remain unsupported.",
    )
    assert scene.status == "completed"
