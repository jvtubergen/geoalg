import pandas as pd
import geopandas as gpd
import networkx as nx
import osmnx as ox
import numpy as np
import utm
from shapely.geometry import LineString, Point

from pathlib import Path
from fileinput import input

# Utils
from operator import itemgetter
import random

# Network related functionality.

# Log debug actions of OSMnx to stdout.
ox.settings.log_console = True

# graphnames to read and use
graphnames = {
    "mapconstruction": [
        'athens_large',
        'athens_small',
        'berlin',
        'chicago',
    ],
    "kevin": [
        'athens_large_kevin',
        'chicago_kevin',
    ],
    "roadster": [ # Inferred by Roadster
        'roadster_athens',
        'roadster_chicago'
    ],
    "osm": [ # Extracted with OSMnx/Overpass from OSM
        'osm_chicago',
        'utrecht' # why not
    ]
}

# Construct graph from data in specified folder. 
# Expect folder to have to files edges.txt and vertices.txt. 
# Expect those files to be CSV with u,v and id,x,y columns respectively .
def construct_graph(folder):

    edges_file_path    = folder + "/edges.txt"
    vertices_file_path = folder + "/vertices.txt"

    # Assuming the text files are CSV formatted
    edges_df = pd.read_csv(edges_file_path)
    vertices_df = pd.read_csv(vertices_file_path)

    # Construct NetworkX graph
    G = nx.Graph()

    # Track node dictionary to simplify node extraction when computing edge lengths.
    # TODO: nodedict unnecessary, use `G.nodes[key]` directly.
    nodedict = {}
    for node in vertices_df.iterrows():
        i, x, y = itemgetter('id', 'x', 'y')(node[1]) 
        y, x = utm.conversion.to_latlon(x, y , 16, zone_letter="N")
        G.add_node(int(i), x=x, y=y)
        nodedict[i] = np.asarray([x, y], dtype=np.float64, order='c')

    for edge in edges_df.iterrows():
        u, v = itemgetter('u', 'v')(edge[1]) 
        # Edge with edge length (inter-node distance) as attribute.
        G.add_edge(int(u), int(v), length = np.linalg.norm(nodedict[u] - nodedict[v]))

    G = nx.MultiDiGraph(G)
    G = ox.simplify_graph(G)
    G.graph['crs'] = "EPSG:4326"

    return G



# Utility function for convenience to extract graph by name.
# Either construction from raw data in folder or reading from graphml file.
# Expect folders with raw data to exist at "data/maps", further with properties described by `construct_graph`.
# Will either read and/or store from "graphs/" data folder.
def extract_graph(name, reconstruct=False):
    graphml_path = "graphs/"+name+".graphml"

    if Path(graphml_path).exists() and not reconstruct:
        G = ox.load_graphml(filepath=graphml_path)
    else:
        G = construct_graph("data/maps/" + name)
        ox.save_graphml(G, filepath=graphml_path)
    
    return G


# Example (re-construct all graphs from mapconstruction dataset):
# for name in graphnames["mapconstruction"]:
#     extract_graph(name, True)


# Extract nodes from a graph into the format `(id, nparray(x,y))`.
def extract_nodes(G):
    return [( node, np.asarray([data['x'], data['y']], dtype=np.float64, order='c') ) for node, data in G.nodes(data = True)]

# Extract nodes from a graph as a dictionary `{nid: nparray([x,y])}`.
def extract_nodes_dict(G):
    d = {}
    for node, data in G.nodes(data = True):
        d[node] = np.asarray([data['x'], data['y']], dtype=np.float64, order='c')
    return d

# Seek nearest vertex in graph of a specific coordinate of interest.
# Expect point to be a 2D numpy array.
def nearest_point(G, p):
    points = extract_nodes(G)

    # Seek nearest point
    dmin = 1000000
    ires = None
    qres = None
    for (i, q) in points:
        m = np.linalg.norm(p - q)
        if m < dmin:
            dmin = m
            (ires, qres) = (i, q)

    return (ires, qres)


# Example (extracting nearest vertex):
# nearest_point(extract_graph("chicago"), np.asarray((4.422440 , 46.346080), dtype=np.float64, order='c'))


# Utility function for convenience to extract graph by name.
#   Either construction from raw data in folder or reading from graphml file.
#   Expect folders with raw data to exist at "data/maps", further with properties described by `construct_graph`.
#   Will either read and/or store from "graphs/" data folder.
def extract_graph(name, reconstruct=False):
    graphml_path = "graphs/"+name+".graphml"

    if Path(graphml_path).exists() and not reconstruct:
        G = ox.load_graphml(filepath=graphml_path)
    else:
        G = construct_graph("data/maps/" + name)
        ox.save_graphml(G, filepath=graphml_path)
    
    return G


# Example (Render chicago):
# G = extract_graph("maps_chicago")
# G = extract_graph("berlin")
# ox.plot_graph(G)


# Example (Extract specific position and render):
# ox.settings.use_cache = True
# G = ox.graph.graph_from_place("berlin", network_type='drive', simplify=False, retain_all=True)


# Example (Render all mapconstruction graphs.):
# for name in graphnames["mapconstruction"]:
#     G = extract_graph(name)
#     ox.plot_graph(G)


# Construct network out of paths (a list of a list of coordinates)
def convert_paths_into_graph(pss):
    nid = 1 # node id
    gid = 1 # group id
    G = nx.Graph()
    for ps in pss:
        i = nid
        # Add nodes to graph.
        for p in ps:
            # Add random noise so its not overlapped in render
            G.add_node(nid, x=p[0] + 0.0001 * random.random(), y=p[1] + 0.0001 * random.random(), gid=gid)
            nid += 1
        # Add edges between nodes to graph.
        while i < nid - 1:
            G.add_edge(i, i+1, gid=gid)
            i += 1
        gid += 1
    return G


# Pick two nodes at random (repeat if in disconnected graphs) and find shortest path.
def gen_random_shortest_path(G):
    nodedict = extract_nodes_dict(G)
    # Pick two nodes from graph at random.
    nodes = random.sample(extract_nodes(G), 2)
    # Extract shortest path.
    path = None
    while path == None:
        nodes = random.sample(extract_nodes(G), 2)
        path = ox.routing.shortest_path(G, nodes[0][0], nodes[1][0])
    # Convert path node ids to coordinates.
    path = np.array([nodedict[nodeid] for nodeid in path])
    return path


# Convert a collection of paths into gid-annotated nodes and edges to thereby render with different colors.
def render_paths(pss):
    G = convert_paths_into_graph(pss)
    G = nx.MultiDiGraph(G)
    G.graph['crs'] = "EPSG:4326"
    nc = ox.plot.get_node_colors_by_attr(G, "gid", cmap="tab20b")
    ec = ox.plot.get_edge_colors_by_attr(G, "gid", cmap="tab20b")
    ox.plot_graph(G, bgcolor="#ffffff", node_color=nc, edge_color=ec)


# Example (rendering multiple paths)
# G = extract_graph("chicago")
# render_paths([gen_random_shortest_path(G), gen_random_shortest_path(G)])


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
    ox.plot_graph(F, bgcolor="#ffffff", node_color=nc, edge_color=ec)


# Example (obtain distance to obtain full chicago, use all_public just like mapconstruction graphs):
# coord_center = (41.87168, -87.65985)  # coordinate at approximately center 
# coord_edge   = (41.88318, -87.64129)  # coordinate at approximately furthest edge
# dist = ox.distance.great_circle(41.87168, -87.65985, 41.88318, -87.64129) # == 1999 
# G = ox.graph_from_point(coord_from, network_type="all_public", dist=dist) # padding included automatically  


# Example (difference all_public to drive_service network filter):
# coord_center = (41.87168, -87.65985)  # coordinate at approximately center 
# G = ox.graph_from_point(coord_center, network_type="all_public", dist=2000)
# H = ox.graph_from_point(coord_center, network_type="drive_service", dist=2000)
# plot_two_graphs(G, H)

# Example (mapconstruction.org chicago vs up-to-date OSM chicago):
# coord_center = (41.87168, -87.65985)  # coordinate at approximately center 
# G = ox.graph_from_point(coord_center, network_type="all_public", dist=2000)
# H = extract_graph("chicago")
# plot_two_graphs(G, H)


# Fails:
# Extract historical OSM of Chicago dataset
# Place: South Campus Parkway, Chicago, IL, USA
# Date: 2011-09-05
# Position: 41.8625,-87.6453
def extract_historic_chicago():
    coordinate = (41.8625,-87.6453)
    # date = "2011-09-05T00:00:00Z"
    dist = 500 # meters

    ox.settings.overpass_settings = f'[out:json][timeout:90][date:"2011-09-05T00:00:00Z"]'
    ox.graph_from_point(coordinate, dist=dist, retain_all=True, simplify=False)
    # , network_type="drive"





# Extract path from a network.



# 1. Use Minskowski sum around path
# 2. Construct minimal bounding box for area
# 3. Extract nodes within area.
# 4. Generate all paths within subnetwork.


# Apply Minskowski sum to obtain area
# def minskowski_curve(ps, l = 0.05)


# Extract a dictionary 
# NOTE: Superfluous function. Can be achieved with `G.nodes[node_id]`.
def graph_node_dict(G):
    nodedict = {}
    for node in list(G.nodes(data=True)):
        nodeid = node[0]
        # x = node[1]["x"]
        # y = node[1]["y"]
        nodedict[nodeid] = node[1]
    return nodedict


# TODO: Deduplicate self-loops.
def undirectional_selfloops(G):
    return 0


# Vectorize a network
# BUG: Somehow duplicated edge with G.edges(data=True)
# SOLUTION: Reduce MultiDiGraph to MultiGraph.
# BUG: Connecting first node with final node for no reason.
# SOLUTION: node_id got overwritten after initializing on unique value.
# BUG: Selfloops are incorrectly reduced when undirectionalized.
# SOLUTION: Build some function yourself to detect and remove duplicates
def vectorize_graph(G):

    if not G.graph.get("simplified"):
        msg = "Graph has to be simplified in order to vectorize it."
        raise BaseException(msg)

    G = G.copy()
    G = nx.MultiGraph(G) # We dont want about directionality in graph: Duplicates edges and nodes.

    # Extract nodes and edges.
    nodes = np.array(list(G.nodes(data=True)))
    edges = np.array(list(G.edges(data=True,keys=True)))

    # Obtain unique (incremental) node ID to use.
    newnodeid = np.max(np.array(nodes)[:,0]) + 1

    # Edges contain curvature information, extract.
    for edge in edges:

        a = edge[0]
        b = edge[1]
        k = edge[2]
        attrs = edge[3]

        # If there is no geometry component, there is no curvature to take care of. Thus already vectorized format.
        if "geometry" in attrs.keys():
            linestring = attrs["geometry"]
            ps = np.array(list(linestring.coords))

            # Drop first and last point because these are start and end node..
            ps = ps[1:-1]
            assert len(ps) >= 1 # We expect at least one point in between start and end node.

            # Delete this edge from network.
            # BUG: We are removing an edge without key identifier from a multigraph.
            #      It should 
            G.remove_edge(a,b, key=k)
            print("Removing edge ", a, b, k)

            # Ensured we are adding new curvature. 
            # Add new node ID to each coordinate.
            pathcoords = list(ps)
            pathids = list(range(newnodeid, newnodeid + len(ps)))
            newnodeid += len(ps) # Increment id appropriately.

            for node, coord in zip(pathids, pathcoords):
                G.add_node(node, x=coord[0], y=coord[1])

            # Add vectorized edges to graph.
            pathids = [a] + pathids + [b]
            for a,b in zip(pathids, pathids[1:]):
                G.add_edge(a, b)

    # TODO: Reduce duplicated nodes
    # TODO: Reduce duplicated edges

    G.graph["simplified"] = False # Mark the graph as no longer being simplified.
    G = nx.MultiDiGraph(G) # Require multidigraph for rendering.

    return G