from __future__ import annotations

import networkx as nx
import plotly.graph_objects as go

STATUS_COLORS = {
    "PASS": "#2e8b57", "RESOLVED": "#2e8b57", "ACCEPTABLE": "#2e8b57", "ALIGNED": "#2e8b57",
    "PARTIAL": "#d08a00", "AMBIGUOUS": "#d08a00", "SEMANTICALLY_STALE": "#d08a00", "UNMATCHED": "#d08a00", "MISMATCH": "#c44e52",
    "BROKEN": "#c44e52", "INVALID": "#c44e52", "FAIL": "#c44e52", "UNALIGNED": "#c44e52", "URI_MISMATCH": "#c44e52",
    "MISSING": "#7b8794", "grey": "#7b8794",
}


def status_color(status: str) -> str:
    return STATUS_COLORS.get(status, "#7b8794")


# Translate cryptic change category codes into readable descriptions (shared with app.py).
_HUMAN_CHANGE_LABELS = {
    "IFC_GLOBALID_CHANGE": "IFC GlobalId changed",
    "IFC_TYPE_CHANGE": "IFC element type changed",
    "IFC_NAME_CHANGE": "IFC wall name changed",
    "IFC_FAMILY_CHANGE": "IFC construction family changed",
    "IFC_THICKNESS_CHANGE": "IFC thickness changed",
    "IFC_MATERIAL_CHANGE": "IFC materials changed",
    "IFC_NATIVE_URI_CHANGE": "IFC native record URI changed",
    "IFC_PSET_URI_CHANGE": "IFC pset record URI changed",
    "IFC_PSET_MAPPING_SERIES_URI_CHANGE": "IFC pset MappingSeries URI changed",
    "IFC_MAPPING_SERIES_URI_CHANGE": "IFC MappingSeries URI changed",
    "IFC_ASSOCIATION_TYPE_CHANGE": "IFC association type changed",
    "IFC_SEMANTIC_PROFILE_CHANGE": "IFC semantic profile changed",
    "RDF_RECORD_URI_CHANGE": "RDF record URI changed",
    "RDF_RECORD_ID_CHANGE": "RDF record ID changed",
    "RDF_FAMILY_CHANGE": "RDF construction family changed",
    "RDF_THICKNESS_CHANGE": "RDF thickness changed",
    "RDF_RW_CHANGE": "RDF Rw value changed",
    "RDF_UNIT_CHANGE": "RDF unit changed",
    "RDF_ASSEMBLY_CHANGE": "RDF assembly changed",
    "RDF_SOURCE_CHANGE": "RDF source organisation changed",
    "RDF_REPORT_CHANGE": "RDF report reference changed",
    "RDF_PROVENANCE_CHANGE": "RDF provenance note changed",
    "RDF_AVAILABILITY_CHANGE": "RDF record availability changed",
    "RDF_C_CHANGE": "RDF spectrum adaptation C changed",
    "RDF_CTR_CHANGE": "RDF spectrum adaptation Ctr changed",
    "RDF_MEASUREMENT_METHOD_CHANGE": "RDF measurement method changed",
    "RDF_FREQUENCY_DATA_CHANGE": "RDF frequency data changed",
    "RDF_LAYER_DATA_CHANGE": "RDF layer data changed",
    "VALIDATION_PROFILE_CHANGE": "Validation profile changed",
    "SEMANTIC_STALENESS_SETTING_CHANGE": "Semantic staleness setting changed",
    "REQUIRE_MAPPING_SERIES_SETTING_CHANGE": "Require MappingSeries setting changed",
    "SEMANTIC_OVERRIDE_CHANGE": "Semantic override status changed",
    "OVERRIDE_RATIONALE_CHANGE": "Override rationale changed",
    "TECHNICAL_STATE_CHANGE": "Technical link state changed",
    "SEMANTIC_STATUS_CHANGE": "Semantic status changed",
    "IDS_STATUS_CHANGE": "IDS readiness status changed",
    "BSDD_STATUS_CHANGE": "bSDD alignment status changed",
    "MAPPING_SERIES_VALIDITY_CHANGE": "MappingSeries validity changed",
    "LINK_STATUS_CHANGE": "Link status changed",
    "RDF_DATA_VALIDITY_CHANGE": "RDF data validity changed",
    "RECORD_TARGET_CHANGE": "Record target changed",
    "RATIONAL_CHANGE": "Assessment rationale changed",
    "REVIEW_STATE_CHANGE": "Review state changed",
    "MAPPING_SERIES_EXPECTED_URI_CHANGE": "Expected MappingSeries URI changed",
    "INITIAL_ASSESSMENT": "Initial assessment (no prior version)",
}


def human_change_label(category: str) -> str:
    return _HUMAN_CHANGE_LABELS.get(category, category)


def lifecycle_graph(assertions):
    graph = nx.DiGraph()
    for assertion in assertions:
        series_id = f"series:{assertion.mapping_series_uri}"
        series_label = assertion.mapping_series_uri.rsplit("/", 1)[-1]
        graph.add_node(series_id, label=f"MappingSeries\n{series_label}", kind="series")
        rid = f"assertion:{assertion.assertion_uri}"
        graph.add_node(rid, label=f"MappingAssertion r{assertion.revision_number}\n{assertion.semantic_status}", kind="assertion", status=assertion.semantic_status)
        graph.add_edge(rid, series_id, label="belongsToSeries")
        activity = f"activity:{assertion.assertion_uri}"
        graph.add_node(activity, label=f"ValidationActivity r{assertion.revision_number}", kind="activity")
        graph.add_edge(rid, activity, label="wasGeneratedBy")
        for kind, prefix in (("IFC", "ifc"), ("RDF", "rdf")):
            snapshot = f"{prefix}:{assertion.assertion_uri}"
            graph.add_node(snapshot, label=f"{kind} Snapshot r{assertion.revision_number}", kind="snapshot")
            graph.add_edge(activity, snapshot, label="used")
        if assertion.previous_assertion_uri:
            graph.add_edge(rid, f"assertion:{assertion.previous_assertion_uri}", label="wasRevisionOf")
        if assertion.supersedes_series_uri:
            old_series_id = f"series:{assertion.supersedes_series_uri}"
            old_label = assertion.supersedes_series_uri.rsplit("/", 1)[-1]
            graph.add_node(old_series_id, label=f"MappingSeries\n{old_label}", kind="series")
            graph.add_edge(series_id, old_series_id, label="supersedes")
        for index, event in enumerate(assertion.change_events):
            event_id = f"event:{assertion.assertion_uri}:{index}"
            graph.add_node(event_id, label=human_change_label(event.category), kind="event")
            graph.add_edge(rid, event_id, label="hasChangeEvent")
    return graph


def plot_lifecycle_graph(assertions):
    graph = lifecycle_graph(assertions)
    if not graph.nodes:
        return go.Figure()
    positions = nx.spring_layout(graph, seed=11, k=1.4)
    edge_x, edge_y = [], []
    for source, target in graph.edges:
        x0, y0 = positions[source]; x1, y1 = positions[target]
        edge_x += [x0, x1, None]; edge_y += [y0, y1, None]
    edge_trace = go.Scatter(x=edge_x, y=edge_y, mode="lines", line=dict(width=1, color="#c9d2dc"), hoverinfo="none")
    node_x, node_y, labels, hover_text, colors = [], [], [], [], []
    for node, data in graph.nodes(data=True):
        x, y = positions[node]
        node_x.append(x); node_y.append(y); labels.append(data.get("label", node))
        hover_text.append(f"{data.get('label', node)}<br>{data.get('kind', 'resource')}")
        colors.append(status_color(data.get("status", "grey")) if data.get("kind") == "assertion" else {"series": "#17324d", "activity": "#39739d", "snapshot": "#7b8794", "event": "#d08a00"}.get(data.get("kind"), "#7b8794"))
    node_trace = go.Scatter(x=node_x, y=node_y, mode="markers+text", text=labels, textposition="top center", hovertext=hover_text, marker=dict(size=22, color=colors, line=dict(width=1, color="white")), hoverinfo="text")
    figure = go.Figure([edge_trace, node_trace])
    figure.update_layout(height=620, margin=dict(l=10, r=10, t=25, b=10), showlegend=False, xaxis=dict(visible=False), yaxis=dict(visible=False), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return figure


def validation_architecture_graph(result, assertion=None):
    """Build a compact left-to-right graph explaining one validation run."""
    graph = nx.DiGraph()
    transition = result.get("transition", {})
    stages = [
        ("ifc", "IFC evidence", "PASS"),
        ("link", "Native + Pset link", result["link_status"]),
        ("series", f"MappingSeries\n{transition.get('kind', 'NOT_ASSESSED')}", result["mapping"]["status"]),
        ("rdf", "Acoustic evidence", result["data"]["status"]),
        ("rules", f"IDS {result['ids']['status']}\nbSDD {result['bsdd']['status']}", result["ids"]["status"]),
        ("decision", f"Decision\n{result['semantic']['semantic_status']}", result["semantic"]["semantic_status"]),
        ("assertion", f"MappingAssertion\nr{assertion.revision_number}" if assertion else "No new assertion", assertion.semantic_status if assertion else "MISSING"),
    ]
    for node, label, status in stages:
        graph.add_node(node, label=label, status=status)
    graph.add_edges_from(zip([stage[0] for stage in stages], [stage[0] for stage in stages[1:]]))
    return graph


def plot_validation_architecture(result, assertion=None):
    graph = validation_architecture_graph(result, assertion)
    order = list(graph.nodes)
    positions = {node: (index, 0) for index, node in enumerate(order)}
    edge_x, edge_y = [], []
    for source, target in graph.edges:
        x0, y0 = positions[source]; x1, y1 = positions[target]
        edge_x += [x0, x1, None]; edge_y += [y0, y1, None]
    edge_trace = go.Scatter(x=edge_x, y=edge_y, mode="lines", line=dict(width=3, color="#64748b"), hoverinfo="none")
    node_trace = go.Scatter(
        x=[positions[node][0] for node in order],
        y=[0 for _ in order],
        mode="markers+text",
        text=[graph.nodes[node]["label"] for node in order],
        textposition="bottom center",
        hovertext=[f"{graph.nodes[node]['label']}<br>Status: {graph.nodes[node]['status']}" for node in order],
        hoverinfo="text",
        marker=dict(size=34, color=[status_color(graph.nodes[node]["status"]) for node in order], line=dict(width=2, color="white")),
    )
    figure = go.Figure([edge_trace, node_trace])
    figure.update_layout(height=330, margin=dict(l=20, r=20, t=30, b=90), showlegend=False, xaxis=dict(visible=False), yaxis=dict(visible=False, range=[-0.35, 0.35]), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return figure
