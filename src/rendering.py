from external import *
from graph_deduplicating import *

# Convert a collection of paths into gid-annotated nodes and edges to thereby render with different colors.
def render_paths(pss):
    G = convert_paths_into_graph(pss)
    G = nx.MultiDiGraph(G)
    G.graph['crs'] = "EPSG:4326"
    nc = ox.plot.get_node_colors_by_attr(G, "gid", cmap="Paired")
    ec = ox.plot.get_edge_colors_by_attr(G, "gid", cmap="Paired")
    ox.plot_graph(G, bgcolor="#ffffff", node_color=nc, edge_color=ec, save=True)


# Pick random shortest paths until coverage, then render.
def render_random_nearby_shortest_paths():
    G = extract_graph("athens_small")
    found = False
    attempt = 0
    while True:
        while not found:
            ps = gen_random_shortest_path(G)
            qs = gen_random_shortest_path(G)
            found, histories, rev = curve_by_curve_coverage(ps,qs, lam=0.003)
            attempt += 1

            if random.random() < 0.01:
                print(attempt)
            
            if rev:
                qs = qs[::-1]

        print(found, histories, rev)

        # Render
        for history in histories:
            print("history:", history)
            steps = history_to_sequence(history)
            print("steps:", steps)

            maxdist = -1

            if not np.all(np.array( [np.linalg.norm(ps[ip] - qs[iq]) for (ip, iq) in steps] ) < 0.003):
                print( np.array([np.linalg.norm(ps[ip] - qs[iq]) for (ip, iq) in steps]) )
                breakpoint()

        ids = np.array(steps)[:,1]
        subqs = qs[ids]

        render_paths([ps, subqs])
        found = False


def plot_two_graphs(G,H):
    G = G.copy()
    H = H.copy()
    G.graph['crs'] = "EPSG:4326"
    G = nx.MultiDiGraph(G)
    H.graph['crs'] = "EPSG:4326"
    H = nx.MultiDiGraph(H)

    # To prevent node interference, update node IDs of H to start at highest index of G.
    nid=max(G.nodes())+1
    relabel_mapping = {}
    for nidH in H.nodes():
        relabel_mapping[nidH] = nid
        nid += 1
    H = nx.relabel_nodes(H, relabel_mapping)

    # Add gid 1 to all nodes and edges of G, 2 for H.
    # G = Blue
    # H = Green
    nx.set_node_attributes(G, 1, name="gid")
    nx.set_edge_attributes(G, 1, name="gid")
    nx.set_node_attributes(H, 2, name="gid")
    nx.set_edge_attributes(H, 2, name="gid")

    # Add two graphs together
    F = nx.compose(G,H)

    # Coloring of edges and nodes per gid.
    nc = ox.plot.get_node_colors_by_attr(F, "gid", cmap="winter")
    ec = ox.plot.get_edge_colors_by_attr(F, "gid", cmap="winter")
    ox.plot_graph(F, bgcolor="#ffffff", node_color=nc, edge_color=ec, save=True)


# Relabel all nodes in graph starting at a given node ID.
def relabel_graph_from_nid(G, nid):
    relabel_mapping = {}
    for nidG in G.nodes():
        relabel_mapping[nidG] = nid
        nid += 1
    G = nx.relabel_nodes(G, relabel_mapping)
    return G


def plot_three_graphs(G,H,I):
    G = G.copy()
    G.graph['crs'] = "EPSG:4326"
    G = nx.MultiDiGraph(G)

    H = H.copy()
    H = nx.MultiDiGraph(H)
    H.graph['crs'] = "EPSG:4326"

    I = I.copy()
    I = nx.MultiDiGraph(I)
    I.graph['crs'] = "EPSG:4326"

    # To prevent node interference, update node IDs of H and I.
    H = relabel_graph_from_nid(H, max(G.nodes())+1)
    I = relabel_graph_from_nid(I, max(H.nodes())+1)

    # Add gid 1 to all nodes and edges of G, 2 for H.
    # G = Blue
    # H = ?
    # I = ?
    nx.set_node_attributes(G, 1, name="gid")
    nx.set_edge_attributes(G, 1, name="gid")
    nx.set_node_attributes(H, 2, name="gid")
    nx.set_edge_attributes(H, 2, name="gid")
    nx.set_node_attributes(I, 3, name="gid")
    nx.set_edge_attributes(I, 3, name="gid")

    # Add two graphs together
    F = nx.compose(G,H)
    F = nx.compose(F,I)

    # Coloring of edges and nodes per gid.
    nc = ox.plot.get_node_colors_by_attr(F, "gid", cmap="tab20b")
    ec = ox.plot.get_edge_colors_by_attr(F, "gid", cmap="tab20b")
    ox.plot_graph(F, bgcolor="#ffffff", node_color=nc, edge_color=ec, save=True)


# Rendering duplicated nodes and edges.
def render_duplicates_highlighted(G):
    G = G.copy()

    # Give everyone GID 2
    nx.set_node_attributes(G, 2, name="gid")
    nx.set_edge_attributes(G, 2, name="gid")

    for key in duplicated_nodes(G):
        G.nodes[key]["gid"] = 1

    for key in duplicated_edges(G):
        G.edges[key]["gid"] = 1

    # Render
    nc = ox.plot.get_node_colors_by_attr(G, "gid", cmap="winter")
    ec = ox.plot.get_edge_colors_by_attr(G, "gid", cmap="winter")
    ox.plot_graph(G, bgcolor="#ffffff", node_color=nc, edge_color=ec, save=True)


# Render a graph that meets the styling for presentation.
def plot_graph_presentation(G):
    # Coloring of edges and nodes per gid.
    G = G.copy()
    G.graph['crs'] = "EPSG:4326"
    G = nx.MultiDiGraph(G)
    white = "#fafafa"
    black = "#040404"
    ox.plot_graph(
        G, 
        bgcolor=white, 
        edge_color=black,
        edge_linewidth=1,
        node_color=white,
        node_edgecolor=black,
        node_size=10,
        save=True,
        # dpi=500,
        # figsize=(1024,1024)
    )


# Render curve and graph
def plot_graph_and_curve(G, ps):

    G = G.copy()
    nx.set_node_attributes(G, 2, name="gid")
    nx.set_edge_attributes(G, 2, name="gid")
    G.graph['crs'] = "EPSG:4326"
    G = G.to_directed()

    # Construct subgraph from ps.
    H = convert_paths_into_graph([ps], nid=max(G.nodes())+1)
    nx.set_node_attributes(H, 1, name="gid")
    nx.set_edge_attributes(H, 1, name="gid")
    H.graph['crs'] = "EPSG:4326"
    H = nx.MultiGraph(H)
    H = H.to_directed()

    F = nx.compose(G,H)
    nc = ox.plot.get_node_colors_by_attr(F, "gid", cmap="winter")
    ec = ox.plot.get_edge_colors_by_attr(F, "gid", cmap="winter")

    ox.plot_graph(F, bgcolor="#ffffff", node_color=nc, edge_color=ec, save=True)


def plot_graph_and_curves(G, ps, qs):

    G = G.copy()
    nx.set_node_attributes(G, 2, name="gid")
    nx.set_edge_attributes(G, 2, name="gid")
    G.graph['crs'] = "EPSG:4326"
    G = G.to_directed()

    # Construct subgraph for ps.
    H = convert_paths_into_graph([ps], nid=max(G.nodes())+1)
    nx.set_node_attributes(H, 1, name="gid")
    nx.set_edge_attributes(H, 1, name="gid")
    H.graph['crs'] = "EPSG:4326"
    H = nx.MultiGraph(H)
    H = H.to_directed()

    F = nx.compose(G,H)

    # Construct subgraph for qs.
    H = convert_paths_into_graph([qs], nid=max(F.nodes())+1)
    nx.set_node_attributes(H, 3, name="gid")
    nx.set_edge_attributes(H, 3, name="gid")
    H.graph['crs'] = "EPSG:4326"
    H = nx.MultiGraph(H)
    H = H.to_directed()

    F = nx.compose(F,H)

    nc = ox.plot.get_node_colors_by_attr(F, "gid", cmap="Paired")
    ec = ox.plot.get_edge_colors_by_attr(F, "gid", cmap="Paired")
    ox.plot_graph(F, bgcolor="#ffffff", node_color=nc, edge_color=ec, save=True)


# Preplot a graph. Can be performed multiple times to render graphs together.
# * Optional to have general node and/or edge rendering properties (thus rendering all nodes/edges the same).
# * Otherwise each edge and node is checked for rendering properties in its attributes (thus each node and edge is considered uniquely).
def preplot_graph(G, ax, node_properties=None, edge_properties=None): 

    print("Plotting nodes.")
    # Nodes.
    uv, data = zip(*G.nodes(data=True))
    gdf_nodes = gpd.GeoDataFrame(data, index=uv)

    if node_properties != None:
        # Render all nodes with same render properties.
        render_attributes = node_properties
    else:
        # Render nodes with their specific render properties (stored under its attributes).
        render_attributes = {}
        for prop in ["color"]: 
            if prop in gdf_nodes.keys():
                render_attributes["color"] = gdf_nodes["color"]

    ax.scatter(**render_attributes, x=gdf_nodes["x"], y=gdf_nodes["y"])
    
    print("Plotting edges.")
    # Edges.
    x_lookup = nx.get_node_attributes(G, "x")
    y_lookup = nx.get_node_attributes(G, "y")

    def extract_edge_geometry(u, v, data):
        if not G.graph["simplified"]:
            return LineString((Point((x_lookup[u], y_lookup[u])), Point((x_lookup[v], y_lookup[v]))))
        else:
            return data["geometry"] # Always exists on simplified graph.

    if not G.graph["simplified"]:
        u, v, data = zip(*[(u, v, attrs) for (u, v), attrs in iterate_edges(G)])
        edge_geoms = map(extract_edge_geometry, u, v, data)
        gdf_edges  = gpd.GeoDataFrame(data, geometry=list(edge_geoms))
        gdf_edges["u"] = u
        gdf_edges["v"] = v
        gdf_edges = gdf_edges.set_index(["u", "v"])
    else:
        u, v, k, data = zip(*[(u, v, k, attrs) for (u, v, k), attrs in iterate_edges(G)])
        gdf_edges  = gpd.GeoDataFrame(data) # Simplified edges already have geometry attribute.
        gdf_edges["u"] = u
        gdf_edges["v"] = v
        gdf_edges["k"] = k
        gdf_edges = gdf_edges.set_index(["u", "v", "k"])

    if edge_properties != None: 
        # Render all edges with same render properties.
        render_attributes = edge_properties
    else:
        # Render edges with their specific render properties (stored under its attributes).
        render_attributes = {}
        for prop in ["color", "linestyle", "linewidth"]: 
            if prop in gdf_edges.keys():
                render_attributes[prop] = gdf_edges[prop]

    gdf_edges.plot(ax=ax, **render_attributes)


def preplot_curve(ps, ax, **properties):
    # Construct GeoDataFrame .
    edge = dataframe({"geometry": to_linestring(ps)}, index=[0])
    # edge.plot(ax=ax, color=color, linewidth=linewidth, linestyle=linestyle)
    edge.plot(ax=ax, **properties)


# Render target graph (dotted gray) + curve (green) + path (blue).
#   Example usage:
#   plot_without_projection2([S], [])
#   plot_without_projection2([], [ (random_curve(),{"color":(0,0,0,1)}) ])
#   plot_without_projection2([], [ (random_curve(),{"color":(0,0,0,1), "linewidth":1, "linestyle": ":"}), (random_curve(), {"color":(0.1,0.5,0.1,1), "linewidth":3}) ])
def plot_without_projection(Gs, pss):

    fig, ax = plt.subplots()

    for i, obj in enumerate(Gs):
        print(f"Plotting graph {i}.")
        if type(obj) == tuple:
            G, properties = obj
            preplot_graph(G,  ax, **properties) 
        else:
            G = obj
            preplot_graph(G,  ax) 

    for i, obj in enumerate(pss):
        print(f"Plotting paths {i}.")
        if type(obj) == tuple:
            ps, properties = obj
            preplot_curve(ps, ax, **properties) 
        else:
            ps = obj
            preplot_curve(ps, ax) 

    fig.canvas.draw()
    fig.canvas.flush_events()
    plt.show()



# Plot a list of graphs.
def plot_graphs(graphs):
    plot_without_projection(graphs, [])


# Plot a single graph.
def plot_graph(G):
    plot_without_projection([G], [])


# Annotate duplicated nodes as red.
def annotate_duplicated_nodes(G):
    duplicated = set([nid for group in duplicated_nodes(G) for nid in group])
    # print("duplicated:", duplicated)
    for nid, attrs in G.nodes(data=True):
        if nid in duplicated:
            attrs["color"] = (1., 0, 0, 1.) # Make duplicated node red.
            # print("Found duplicate", nid)
        else:
            attrs["color"] = (0, 0, 0, 1)
