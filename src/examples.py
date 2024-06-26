

# Example (re-construct all graphs from mapconstruction dataset):
# for name in graphnames["mapconstruction"]:
#     extract_graph(name, True)


# Example (extracting nearest vertex):
# nearest_point(extract_graph("chicago"), np.asarray((4.422440 , 46.346080), dtype=np.float64, order='c'))


# Example (Render chicago):
# G = extract_graph("maps_chicago")
# G = extract_graph("berlin")
# ox.plot_graph(G)


# Example (Extract specific position and render):
# ox.settings.use_cache = True
# G = ox.graph.graph_from_place("berlin", network_type='drive', simplify=False, retain_all=True)


# Example (Render all mapconstruction graphs):
# for name in graphnames["mapconstruction"]:
#     G = extract_graph(name)
#     ox.plot_graph(G)


# Example (Extract historical OSM of Chicago dataset) FAILS:
#   Place: South Campus Parkway, Chicago, IL, USA
#   Date: 2011-09-05
#   Position: 41.8625,-87.6453
# coordinate = (41.8625,-87.6453)
# dist = 500 # meters
# ox.settings.overpass_settings = f'[out:json][timeout:90][date:"2011-09-05T00:00:00Z"]'
# ox.graph_from_point(coordinate, dist=dist, retain_all=True, simplify=False)


# Example (vectorize and simplify again):
# Note: It contains a bug: bidirectional self-loops are incorrectly removed.
# G  = extract_graph("chicago_kevin")
# G2 = vectorize_graph(G)
# G2 = deduplicate_vectorized_graph(G2)
# G3 = ox.simplify_graph(G2)
# G5 = ox.simplify_graph(vectorize_graph(G3))
# # Simple check on vectorization validity (Wont pass: Intersection nodes are add).
# assert len(G.nodes()) == len(G3.nodes())
# assert len(G.edges()) == len(G3.edges())


# Example (Subgraph of nodes nearby curve):
# G = extract_graph("chicago")
# idx = graphnodes_to_rtree(G)
# ps = gen_random_shortest_path(G)
# bb = bounding_box(ps)
# H = rtree_subgraph_by_bounding_box(G, idx, bb)


###################################
###  Examples: Graph and Curve Rendering
###################################

# Example (rendering multiple paths)
# G = extract_graph("chicago")
# render_paths([gen_random_shortest_path(G), gen_random_shortest_path(G)])

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


# Example (subgraph around random shortest path and rendering both)
# G = extract_graph("chicago")
# G = vectorize_graph(G) # Vectorize graph.
# G = deduplicate_vectorized_graph(G)
# ps = gen_random_shortest_path(G)
# lam = 0.0015
# idx = graphnodes_to_rtree(G) # Place graph nodes coordinates in accelerated data structure (R-Tree).
# bb = bounding_box(ps, padding=lam) # Construct lambda-padded bounding box.
# nodes = list(idx.intersection((bb[0][0], bb[0][1], bb[1][0], bb[1][1]))) # Extract nodes within bounding box.
# H = G.subgraph(nodes) # Extract subgraph with nodes.
# # plot_graph_and_curve(G,ps) # Full graph with curve of interest
# plot_graph_and_curve(H,ps) # Subgraph with curve of interest


# Example (Retrieve/Construct image with GSD ~0.88 between two coordinates):
# upperleft  = (41.799575, -87.606117)
# lowerright = (41.787669, -87.585498)
# scale = 1
# zoom = 17 # For given latitude and scale results in gsd of ~ 0.88
# api_key = read_api_key()
# # superimage = construct_image(upperleft, lowerright, zoom, scale, api_key)   # Same result as below.
# superimage = construct_image(upperleft, lowerright, zoom-1, scale+1, api_key) # Same result as above.
# write_image(superimage, "superimage.png")
