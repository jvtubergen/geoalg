from external import *

from graph_simplifying import *
from graph_coverage import * # Necessary for coverage computing of duplicated sat edges on injected gps edges.
from utilities import *


# Prune graph with threshold-annotated edges.
# * TODO: Only add edge connections with sat if gps edge as adjacent covered edges (thus concatenate with `merge_graph` logic).
# * Rather than filtering out below threshold, we can as well seek edges above threshold (thus inverting the result).
def prune_coverage_graph(G, prune_threshold=10, invert=False):

    assert not G.graph["simplified"]

    assert G.graph['max_threshold'] > 0 # Make sure thresholds are set.
    assert prune_threshold <= G.graph['max_threshold'] # Should not try to prune above max threshold used by annotation.

    retain = []
    for (a, b, attrs) in G.edges(data=True):
        # Iterate each edge and drop it if its threshold exceeds prune_threshold.
        if not invert and attrs["threshold"] <= prune_threshold:
            # Retain edge
            retain.append((a, b))
        elif invert and attrs["threshold"] > prune_threshold:
            retain.append((a, b))
    G = G.edge_subgraph(retain)

    return G


# Merges graph A into graph C.
# * Injects uncovered edges of graph A into graph C. 
# * Graph A has got its edges annotated with coverage threshold in relation to graph C.
# * Extension 1: Removal of duplicates.
# * Extension 2: Reconnecting C edges to injected A edges.
def merge_graphs(C=None, A=None, prune_threshold=20, remove_duplicates=False, reconnect_after=False):

    # Sanity checks.
    assert A.graph["simplified"] # We require simplified graphs for coverage to make sense.
    assert C.graph["simplified"]
    assert A.graph["coordinates"] == "utm" # We require UTM coordinates for prune threshold to make sense.
    assert C.graph["coordinates"] == "utm"
    assert A.graph['max_threshold'] > 0  # Make sure thresholds are set (indicator that edge coverage is computed and edges are annotated).
    assert prune_threshold <= A.graph['max_threshold'] # Should not try to prune above max threshold used by annotation.
    assert remove_duplicates or (remove_duplicates == reconnect_after) # Only possible to reconnect if duplicates are to be removed.

    A = A.copy()
    C = C.copy()

    # Relabel additional to prevent node id overlap. / # Adjust nids of A to ensure uniqueness once added to C.
    nid = max(C.nodes()) + 1
    relabel_mapping = {}
    for nidH in A.nodes():
        relabel_mapping[nidH] = nid
        nid += 1
    A = nx.relabel_nodes(A, relabel_mapping)

    # Edges above and below the prune threshold. We retain edges below the prune threshold.
    above = [eid for eid, attrs in iterate_edges(A) if attrs["threshold"] >  prune_threshold]
    below = [eid for eid, attrs in iterate_edges(A) if attrs["threshold"] <= prune_threshold]

    # Sanity check that retain and drop are disjoint.
    # NOTE: Set overlap here is about _edges_, not nodes. Thus therefore we can demand this uniqueness (non-overlapping) constraint.
    assert len(set(above) & set(below)) == 0
    assert len(set(above) ^ set(below)) == len(A.edges())

    # Retain edges above the coverage threshold (thus those edges of A not being covered by C).
    B = A.edge_subgraph(above)

    # Extract nids which are connected to an edge above and below threshold.
    nodes_above = set([nid for el in above for nid in el[0:2]]) 
    nodes_below = set([nid for el in below for nid in el[0:2]]) 

    # Obtain what nodes of B to connect with C (those nodes of A which are connected to both a covered and uncovered edge).
    # + Render nodes of B as either injected or connection points.
    connect_nodes = []
    for nid in B.nodes():
        # This logic checks every node whether it is connected to both a covered (below threshold) and uncovered (above threshold) edge.
        # With the `nearest_node` strategy, exactly these nodes (of B) have to be connected with C.
        if nid in nodes_below and nid in nodes_above:
            connect_nodes.append(nid)
            B.nodes[nid]["render"] = "connection" # Annotate as connection point.
        else:
            B.nodes[nid]["render"] = "injected"

    # Render edges of B as injected.
    for attrs in iterate_edge_attributes(B):
        attrs["render"] = "injected"

    # Render nodes and edges of C as original.
    for nid, attrs in C.nodes(data=True):
        attrs["render"] = "original"
    for attrs in iterate_edge_attributes(C):
        attrs["render"] = "original"

    # Construct rtree on nodes in C.
    nodetree = graphnodes_to_rtree(C)

    # Register edge connections for A to C. (Node-based inserted.)
    connections = [] 
    for nid in connect_nodes: # In case of `nearest_node` strategy we only care for node, ignore edge.

        # Draw edge between nearest node in C and edge endpoint at w in B.
        y, x = B._node[nid]['y'], A._node[nid]['x'],
        hit = list(nodetree.nearest((y, x, y, x)))[0] # Seek nearest node.

        # Add straight line curvature and geometry 
        y2, x2 = C._node[hit]['y'], C._node[hit]['x'],
        curvature = array([(y, x), (y2, x2)])
        geometry = to_linestring(curvature)
        connections.append((nid, hit, {"render": "connection", "geometry": geometry, "curvature": curvature}))

    # Inject B into C.
    C.add_nodes_from(B.nodes(data=True))
    C.add_edges_from(graph_edges(B))
    
    # Add edge connections between B and C.
    C.add_edges_from(connections)

    # TODO: Extract subgraph B_prime we get by taking both B with its connections to C.

    # TODO: Extension a: Remove duplicated edges of C.
    if remove_duplicates: 

        # Then find edges of C which are covered by the injected B edges (which are all of them in B_prime) and then remove them.

        # TODO: We should take the B edges _with_ their connection to C nodes.
        #       So inject connections, simplify graph, and extract those edges.

        # Track what nodes and edges are being injected. We need the selection of edges as subgraph to compare against.
        # ... computing B_prime :)

        # Compute coverage of C against B (covered edges are to be removed).
        C_covered_by_B = edge_graph_coverage(C, B, max_threshold=prune_threshold)
        assert C_covered_by_B.graph['max_threshold'] > 0 # Make sure thresholds are set.

        # Obtain edges of C below the threshold.
        above = [eid for eid, attrs in iterate_edges(C_covered_by_B) if attrs["threshold"] >  prune_threshold]
        below = [eid for eid, attrs in iterate_edges(C_covered_by_B) if attrs["threshold"] <= prune_threshold]
        edges_to_be_deleted = below

        # Take all nodes of edges_to_be_deleted, yet without those nodes as well part of uncovered edges.
        nodes_above = set([nid for el in above for nid in el[0:2]]) 
        nodes_below = set([nid for el in below for nid in el[0:2]]) 
        nodes_to_be_deleted = nodes_below - nodes_above

        # Mark edges that are deleted.
        render_update = {}
        for eid in edges_to_be_deleted:
            render_update[eid] = {**C_covered_by_B.edges[eid], "render": "deleted"}
        nx.set_edge_attributes(C, render_update)
        # C.remove_edges_from(edges_to_be_deleted)

        # Mark nodes that are deleted.
        render_update = {}
        for nid in nodes_to_be_deleted:
            render_update[nid] = {**C_covered_by_B.nodes[nid], "render": "deleted"}
        nx.set_node_attributes(C, render_update)
        # C.remove_nodes_from(nodes_to_be_deleted)

    # TODO: Extension b: Reconnect edges of C to injected edges of A into B.
    if reconnect_after:

        # We require a list of removed sat edges (or what sat edges have a sat edge removed) _and_ a list of injected gps edges (B_prime).
        #   Then we can find what sat nodes have a missing sat edge, _and_ what collection of (gps) edges it can be connected to.

        # Rules for sat edges that have to be reconnected:
        # * C edge is above threshold.
        # * C edge is connected an A edge which is below threshold.
        # * C edge is not contained in the set of injected A edges.

        # Obtain sat nodes which are to be connected to injected GPS edges.
        nodes_above = set([nid for el in above for nid in el[0:2]]) 
        nodes_below = set([nid for el in below for nid in el[0:2]]) 
        nodes_to_connect = set(nodes_above) & set(nodes_below)
        
        # # Find edges of sat to reconnect to injected gps edge.
        # connect_edges = [] # (eid and endpoint)
        # nodes_to_connect = 
        # for u, v in C_covered_by_B.edges(data=True):
        #     if nid in nodes_below and nid in nodes_above:
        #         connect_node()
        #         # We find a node at which a covered edge is connected to an uncovered edge.
        #         # Pick edges which are above threshold.
        #         candidates = [eid for eid in above if eid[0] == nid or eid[1] == nid]
        #         # Intersect edge with injected gps edge.

        #         merge_nearest_edge()
        #         connect_nodes.append(nid)

        # Apply nearest_edge injection.
        for nid in nodes_to_connect:
            connect_nearest_edge(C, nid)

    return C


def connect_nearest_edge(G, nid):
    position = G.nodes(data=True)[nid]
    y, x = position["y"], position["x"]

    # Find nearest node.
    hit, distance = osmnx.distance.nearest_nodes(G, x, y, return_dist=True)
    if distance < 10: # simply connect to node.
        if not G.graph["simplified"]:
            G.add_edges_from([(nid, hit, {"render": "connection"})])
        else:
            y2, x2 = G._node[hit]['y'], G._node[hit]['x'],
            curvature = array([(y, x), (y2, x2)])
            geometry = to_linestring(curvature)
            G.add_edges_from([(nid, hit, {"render": "connection", "geometry": geometry, "curvature": curvature})])
        return G

    # TODO: Optimization: Prefilter out edges within `distance` bounding box.
    # relevant_edges = [] # [(eid, attrs)]
    # Convert edges into curve_points, eid
    curves = G
        # TODO: Link eids to identifiers.
    # TODO: Find nearest edge and point of intersection.
    # TODO: Cut nearest edge at point of intersection, connect new node, resolve.
    nid = max(G.nodes()) + 1 
    return G


# Functionality for merging an edge with the `nearest_edge` strategy.
# Inject edge at endpoint with G.
# Find edge in G that is most suitable for injection.
# Apply 
def merge_nearest_edge(G, nidstart, edge, endpoint):
    nid = max(G.nodes()) + 1
    # Naive approach: 
    # Take curvature 