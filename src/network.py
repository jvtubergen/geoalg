from dependencies import *

###################################
###  Graph construction/extraction
###################################

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


# Construct network out of paths (a list of a list of coordinates)
def convert_paths_into_graph(pss, nid=1, gid=1):
    # Provide node_id offset.
    # Provide group_id offset.
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


###################################
###  Node and path construction/extraction
###################################

# Extract nodes from a graph into the format `(id, nparray(x,y))`.
def extract_nodes(G):
    return [( node, np.asarray([data['x'], data['y']], dtype=np.float64, order='c') ) for node, data in G.nodes(data = True)]


# Extract nodes from a graph as a dictionary `{nid: nparray([x,y])}`.
def extract_nodes_dict(G):
    d = {}
    for node, data in G.nodes(data = True):
        d[node] = [data['x'], data['y']]
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



###################################
###  Graph vectorization
###################################


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

    G.graph["simplified"] = False # Mark the graph as no longer being simplified.
    G = nx.MultiDiGraph(G) # Require multidigraph for rendering.

    return G


###################################
###  Deduplication functionality
###################################

# Return node IDs which are duplicated (exact same coordinate).
# TODO: Group togeter node-IDs that are duplicates of one another as tuples.
def duplicated_nodes(G):
    # NOTE: Keep IDs (integeters) separate from coordinates (floats): Numpy arrays all have same type.
    nodes = G.nodes()
    coordinates = np.array([[info["x"], info["y"]] for node, info in G.nodes(data=True)])
    uniques, inverses, counts = np.unique( coordinates, return_inverse=True, axis=0, return_counts=True )
    duplicated = []
    for node_id, index_to_unique in zip(nodes, inverses):
        if counts[index_to_unique] > 1:
            duplicated.append(node_id)
    return duplicated


# Group duplicated nodes.
def duplicated_nodes_grouped(G):
    # NOTE: Keep IDs (integeters) separate from coordinates (floats): Numpy arrays all have same type.
    node_ids = G.nodes()
    coordinates = np.array([[info["x"], info["y"]] for node, info in G.nodes(data=True)])
    uniques, inverses, counts = np.unique( coordinates, return_inverse=True, axis=0, return_counts=True )
    # Construct dictionary.
    duplicated = {}
    for node_id, index_to_unique in zip(node_ids, inverses):
        if counts[index_to_unique] > 1:
            if index_to_unique in duplicated.keys():
                duplicated[index_to_unique].append(node_id)
            else:
                duplicated[index_to_unique] = [node_id]
    # Convert dictionary into a list.
    result = []
    for v in duplicated:
        result.append(duplicated[v])
    return result


# Return edge IDs which are duplicated (exact same coordinates).
# NOTE: Expects vectorized graph.
# TODO: Group togeter edge-IDs that are duplicates of one another as tuples.
def duplicated_edges(G):

    if type(G) != nx.MultiDiGraph:
        raise BaseException("Expect to call duplicated_edge_grouped on an nx.MultiDiGraph.")

    if G.graph["simplified"]:
        raise BaseException("Duplicated edges function is supposed to be called on a vectorized graph.")

    # Construct edges coordinates in the format of `[x1,y1,x2,y2]`.
    # NOTE: Keep IDs (integeters) separate from coordinates (floats): Numpy arrays all have same type.
    edges = G.edges(keys=True)
    coordinates = []
    for (a, b, k, attrs) in G.edges(keys=True, data=True):
        x1 = G.nodes[a]["x"]
        y1 = G.nodes[a]["y"]
        x2 = G.nodes[b]["x"]
        y2 = G.nodes[b]["y"]
        coordinates.append([x1,y1,x2,y2])
    coordinates = np.array(coordinates)

    # Extract duplications
    uniques, inverses, counts = np.unique( coordinates, return_inverse=True, axis=0, return_counts=True )
    duplicated = []
    for edge_id, index_to_unique in zip(edges, inverses):
        if counts[index_to_unique] > 1:
            duplicated.append(edge_id)
    return duplicated


# Group duplicated edges.
# NOTE: Expects MultiDiGraph
def duplicated_edges_grouped(G):

    if type(G) != nx.MultiDiGraph:
        raise BaseException("Expect to call duplicated_edge_grouped on an nx.MultiDiGraph.")

    if G.graph["simplified"]:
        raise BaseException("Duplicated edges function is supposed to be called on a vectorized graph (thus not simplified).")

    # NOTE: Keep IDs (integeters) separate from coordinates (floats): Numpy arrays all have same type.
    edge_ids = G.edges(keys=True)
    coordinates = []
    for (a, b, k, attrs) in G.edges(keys=True, data=True):
        x1 = G.nodes[a]["x"]
        y1 = G.nodes[a]["y"]
        x2 = G.nodes[b]["x"]
        y2 = G.nodes[b]["y"]
        coordinates.append([x1,y1,x2,y2])
    coordinates = np.array(coordinates)

    # Construct dictionary.
    uniques, inverses, counts = np.unique( coordinates, return_inverse=True, axis=0, return_counts=True )
    duplicated = {}
    for edge_id, index_to_unique in zip(edge_ids, inverses):
        if counts[index_to_unique] > 1:
            if index_to_unique in duplicated.keys():
                duplicated[index_to_unique].append(edge_id)
            else:
                duplicated[index_to_unique] = [edge_id]

    # Convert dictionary into a list.
    result = []
    for v in duplicated:
        result.append(duplicated[v])

    return result


# Remove duplicated nodes and edges from vectorized graph.
# NOTE: Since a vectorized only stores directly
#       No need to 
def deduplicate_vectorized_graph(G):

    G = G.copy()
    G = nx.Graph(G)
    # Assert G is a Graph (unidirectional and single path)

    # Deduplicate nodes: Adjust edges of deleted nodes + Delete nodes.
    for group in duplicated_nodes_grouped(G):
        base = group[0]
        # for n, nbrs in G.adj.items():
        #     # n: from node id
        #     # nbrs: {<neighboring node id>: {<edge-id-connecting n with nbr>: <edge attributes>}}]
        for remove in group[1:]:
            # Replace edges
            nbrs = G.adj[remove]
            to_delete = []
            to_add = []
            for nbr in nbrs:
                edge = G[remove][nbr]
                to_delete.append((remove,nbr))
                to_add.append((base,nbr, *edge))
            # Delete and add in a single go to prevent changing the nbrs loop elements.
            G.remove_edges_from(to_delete)
            G.add_edges_from(to_add)
            
            # Expect remove node to be isolated now.
            assert len(G[remove]) == 0
            G.remove_node(remove)
    
    # Deduplicate edges:
    # Since G is a graph, adding the edges already resolves into edge deduplication.
    G = nx.MultiDiGraph(G) # Convert back into MultiDiGraph.
    
    return G

