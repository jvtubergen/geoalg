from external import * 

### R-Tree

# Construct R-Tree on graph edges.
def graphedges_to_rtree(G):

    edgetree = rtree.index.RtreeContainer()

    if type(G) == nx.MultiGraph:
        elements = [((u, v, k), edge_curvature(G, u, v, k=k)) for (u, v, k) in G.edges(keys=True)]
    if type(G) == nx.Graph:
        elements = [((u, v), edge_curvature(G, u, v)) for (u, v) in G.edges()]

    for (eid, curvature) in elements:
            minx = min(curvature[:,0])
            maxx = max(curvature[:,0])
            miny = min(curvature[:,1])
            maxy = max(curvature[:,1])
            edgetree.insert(eid, (minx, miny, maxx, maxy))
    
    return edgetree

# Construct R-Tree on graph nodes.
def graphnodes_to_rtree(G):
    idx = rtree.index.Index()
    for node, data in G.nodes(data = True):
        x, y = data['x'], data['y']
        idx.insert(node, (x, y, x, y))
    return idx


### Bounding boxes

# Construct dictionary that links edge id to a bounding box.
def graphedges_to_bboxs(G):

    bboxs = {}

    if type(G) == nx.MultiGraph:
        elements = [((u, v, k), edge_curvature(G, u, v, k=k)) for (u, v, k) in G.edges(keys=True)]
    if type(G) == nx.Graph:
        elements = [((u, v), edge_curvature(G, u, v)) for (u, v) in G.edges()]
    
    for (eid, curvature) in elements:
        minx = min(curvature[:,0])
        maxx = max(curvature[:,0])
        miny = min(curvature[:,1])
        maxy = max(curvature[:,1])
        bbox = array([(minx, miny), (maxx, maxy)])
        bboxs[eid] = bbox

    return bboxs

# Extract bounding box on a curve. Use padding to lambda pad.
def bounding_box(ps, padding):
    padding = array([padding, padding])
    lower = [np.min(ps[:,0]), np.min(ps[:,1])]
    higher = [np.max(ps[:,0]), np.max(ps[:,1])]
    return array([lower - padding, higher + padding])

# Pad a bounding box.
def pad_bounding_box(bb, padding):
    padding = array([padding, padding])
    return array([bb[0] - padding, bb[1] + padding])


## Curves

# Length of curve, return accumulated length of piecewise linear segments.
def curve_length(ps):
    return sum([norm(p1 - p2) for p1, p2 in zip(ps, ps[1:])])

# Cut a curve at a percentage (interval of [0, 1]).
def curve_cut(ps, percentage):
    assert len(ps) >= 2
    steps = [norm(p1 - p2) for p1, p2 in zip(ps, ps[1:])]
    length = sum(steps)
    target = percentage * length
    assert length > 0
    current = 0
    i = 0
    while True:
        step = steps[i]
        upcoming = current + step
        if upcoming > target: # Cut current edge.
            line_percentage = (target - current) / step
            p = line_percentage * ps[i+1] + (1 - line_percentage) * ps[i]
            left  = np.append(ps[:i+1], [p], axis=0)
            right = np.append([p], ps[i+1:], axis=0)
            return (left, right)
        current = upcoming

# Find cutpoints, cut curve into pieces, store curvature for each cut curve segment.
def curve_cut_pieces(ps, amount=10):

    assert len(ps) >= 2
    steps = array([norm(p1 - p2) for p1, p2 in zip(ps, ps[1:])])
    length = sum(steps)
    assert length > 0 # Expect non-zero length.

    qss = []
    percentage = 1. / amount
    current_step = 0
    current_interval = 0 # Interval element to obtain (skips the startpoint).
    current_distance = 0
    current_subcurve = [ps[0]]
    while True:
        target_length = (current_interval + 1) * percentage * length # Distance at which next cut has to be made.
        next_distance = current_distance + steps[current_step] # Distance we are at after walking the current line segment.
        if abs(target_length - next_distance) < 0.0001: # Cutpoint lies on curvature vertex.
            # Add curvature vertex to current subcurve.
            current_subcurve.append(ps[current_step + 1])
            qss.append(current_subcurve) # Commit subcurve.
            if len(qss) == amount:
                return qss # We cannot return a numpy array since subcurves point sequence length is inhomogeneous (can differ from one nother.)
            # Reset for next subcurve.
            current_subcurve = [ps[current_step + 1]]
            current_interval += 1
            # Move to next line segment.
            current_distance = next_distance
            current_step += 1
        elif target_length < next_distance: # Next cutpoint lies in current linesegment. 
            # Find cutpoint in line segment.
            segment_percentage = (target_length - current_distance) / steps[current_step]
            p = segment_percentage * ps[current_step + 1] + (1 - segment_percentage) * ps[current_step]
            # Add point to current subcurve.
            current_subcurve.append(p)
            qss.append(current_subcurve) # Commit subcurve.
            # Reset for next subcurve.
            current_subcurve = [p]
            current_interval += 1
        elif next_distance < target_length: # Next cutpoint lies beyond current linesegment. 
            # Add curvature vertex to current subcurve.
            current_subcurve.append(ps[current_step + 1])
            # Move to next line segment.
            current_distance = next_distance
            current_step += 1

# Test curve cutting into pieces (basic test).
def test_curve_cut_pieces():
    curve = array([(0., i) for i in range(11)])
    qss = curve_cut_pieces(curve, amount=10)
    assert len(qss) == 10
    assert all([abs(curve_length(qs) - 1) < 0.0001 for qs in qss])

    qss = curve_cut_pieces(curve, amount=5)
    assert len(qss) == 5
    assert all([abs(curve_length(qs) - 2) < 0.0001 for qs in qss])

    qss = curve_cut_pieces(curve, amount=2)
    assert len(qss) == 2
    assert all([abs(curve_length(qs) - 5) < 0.0001 for qs in qss])

    qss = curve_cut_pieces(curve, amount=3)
    assert len(qss) == 3
    assert all([abs(curve_length(qs) - 3.333333) < 0.0001 for qs in qss])


# Cut curve in half.
curve_cut_in_half = lambda ps: curve_cut(ps, 0.5)

# Generate a random curve.
def random_curve(length = 100, a = np.array([-10,-10]), b = np.array([10,10])):
    ps = np.random.random((length, 2))
    return a + (b - a) * ps


### Linestrings

to_linestring = lambda ps: LineString([Point(x, y) for x, y in ps])