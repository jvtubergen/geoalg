from dependencies import *
from maps import *

# Extract vectorized nodes and edges from JSON file generated by Sat2Graph.
def sat2graph_extract_json(json_file, padding = 176):

    # Extract raw data.
    elements = json.load(open(json_file, "r"))
    edges    = elements["graph"]["edges"]
    vertices = elements["graph"]["vertices"]

    def padding_offset(v):
        return (v[0] + padding, v[1] + padding)

    # Add ID to nodes.
    nodeid = 1
    nodes = set()
    for v in vertices: 
        nodes.add(tuple(v))

    # Add edge endpoints to nodes.
    for e in edges:
        v1 = e[0]
        v2 = e[1]
        nodes.add(tuple(v1))
        nodes.add(tuple(v2))

    # Store as a dictionary.
    D = {}
    for nid, v in enumerate(nodes):
        D[v] = nid
    
    # Additionally, link node connections.
    E = []
    for e in edges:
        a = tuple(e[0])
        b = tuple(e[1])
        E.append((D[a],D[b]))
    
    return nodes, D, E


# # Convert Sat2Graph elements into a graph.
# # * json_file: Sat2Graph inferred road network data.
# # * upper-left and lower-right web mercator position, expect to be square.
def sat2graph_json_to_graph(json_file, upperleft, lowerright, padding = 176, zoom = 17):
    nodes, D, E = sat2graph_extract_json(json_file)
    p1, p2 = upperleft, lowerright

    # Construct coordinate mapping.
    lat1, lon1 = p1
    lat2, lon2 = p2
    y1, x1 = latlon_to_pixelcoord(lat1, lon1, zoom)
    y2, x2 = latlon_to_pixelcoord(lat2, lon2, zoom)

    G = nx.Graph()
    for v,i in D.items():
        py, px = v
        y = y1 + py + padding
        x = x1 + px + padding
        lat, lon = pixelcoord_to_latlon(y, x, zoom)
        G.add_node(i, y=lat, x=lon)

    for (a,b) in E:
        G.add_edge(a,b)
    
    return G