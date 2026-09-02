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


def lifecycle_graph(assertions):
    graph = nx.DiGraph()
    series_uri = assertions[-1].mapping_series_uri if assertions else "MappingSeries"
    graph.add_node("series", label="MappingSeries", kind="series")
    for assertion in assertions:
        rid = f"assertion-{assertion.revision_number}"
        graph.add_node(rid, label=f"MappingAssertion r{assertion.revision_number}\n{assertion.semantic_status}", kind="assertion", status=assertion.semantic_status)
        graph.add_edge(rid, "series", label="belongsTo")
        activity = f"activity-{assertion.revision_number}"
        graph.add_node(activity, label=f"ValidationActivity r{assertion.revision_number}", kind="activity")
        graph.add_edge(rid, activity, label="wasGeneratedBy")
        for kind, prefix in (("IFC", "ifc"), ("RDF", "rdf")):
            snapshot = f"{prefix}-{assertion.revision_number}"
            graph.add_node(snapshot, label=f"{kind} Snapshot r{assertion.revision_number}", kind="snapshot")
            graph.add_edge(activity, snapshot, label="used")
        if assertion.previous_revision:
            graph.add_edge(rid, f"assertion-{assertion.previous_revision}", label="wasRevisionOf")
        for index, event in enumerate(assertion.change_events):
            event_id = f"event-{assertion.revision_number}-{index}"
            graph.add_node(event_id, label=event.category, kind="event")
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
    node_x, node_y, labels, colors = [], [], [], []
    for node, data in graph.nodes(data=True):
        x, y = positions[node]
        node_x.append(x); node_y.append(y); labels.append(data.get("label", node))
        colors.append(status_color(data.get("status", "grey")) if data.get("kind") == "assertion" else {"series": "#17324d", "activity": "#39739d", "snapshot": "#7b8794", "event": "#d08a00"}.get(data.get("kind"), "#7b8794"))
    node_trace = go.Scatter(x=node_x, y=node_y, mode="markers+text", text=labels, textposition="top center", marker=dict(size=22, color=colors, line=dict(width=1, color="white")), hoverinfo="text")
    figure = go.Figure([edge_trace, node_trace])
    figure.update_layout(height=560, margin=dict(l=10, r=10, t=25, b=10), showlegend=False, xaxis=dict(visible=False), yaxis=dict(visible=False), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return figure
