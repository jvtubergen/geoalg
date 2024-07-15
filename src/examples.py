

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


# Example (Extracting chicago ROI including pixel coordinates):
# upperleft = (41.880126, -87.659200)
# lowerright = (41.863563, -87.634062)
# scale = 2
# zoom = 17 # For given latitude and scale results in gsd of ~ 0.88
# image, coordinates = construct_image(upperleft, lowerright, zoom, scale, read_api_key())
# write_image(image, "chicago_zoomed.png")
# pickle.dump(coordinates, open("chicago_zoomed.pkl", "wb"))


# Example (Converting sat2graph inferred data into a graph):
# G = sat2graph_json_to_graph("chicago_zoomed.json", "chicago_zoomed.pkl")
# plot_graph_presentation(G)


# Example (Load networks sat, gps, truth and render gps-truth and sat-truth):
# ground_truth = extract_graph("maps_chicago")
# ground_truth2 = extract_graph("chicago")
# inferred_gps = extract_graph("inferredgps_chicago")
# inferred_sat = sat2graph_json_to_graph("chicago_zoomed.json", "chicago_zoomed.pkl")
# plot_two_graphs(ground_truth2, inferred_gps)
# plot_two_graphs(ground_truth2, inferred_sat)


# Example (Load networks sat, gps, truth and render gps-truth and sat-truth):
# web_coordinates = {
#     "chicago_zoomed"      : ((41.880126, -87.659200), (41.863563, -87.634062)),
#     "chicago_super_zoomed": ((41.878978, -87.651714), (41.871960, -87.640646)),
#     "chicago_gps"         : ((41.87600 , -87.68800 ), (41.86100 , -87.63900 ))
# }
# scale = 2
# zoom = 17
# roi    = "chicago_zoomed"
# roi    = "chicago_gps"
# action = "extract_image"
# action = "infer_graph"
# action = "plot_graphs"
# action = "plot_truth_gps"
# p1, p2 = web_coordinates[roi]
# p1, p2 = squarify_web_mercator_coordinates(p1, p2, zoom)
# match action:
#     case "extract_image":
#         image, coordinates = construct_image(p1, p2, zoom, scale, read_api_key())
#         write_image(image, roi+".png")
#     case "infer_graph":
#         json_file = roi + ".json"
#         G = sat2graph_json_to_graph(json_file, p1, p2)
#         plot_graph_presentation(G)
#         save_graph(G, "chicago_inferred_sat", overwrite=True)
#     case "plot_graphs":
#         truth = extract_graph("chicago_truth")
#         truth = cut_out_ROI(truth, p1, p2)
#         sat   = extract_graph("chicago_inferred_sat")
#         gps   = extract_graph("chicago_inferred_gps")
#         plot_three_graphs(truth, sat, gps)
#     case "plot_truth_gps":
#         truth = extract_graph("chicago_truth")
#         truth = cut_out_ROI(truth, p1, p2)
#         gps   = extract_graph("chicago_inferred_gps")
#         plot_two_graphs(truth, gps)