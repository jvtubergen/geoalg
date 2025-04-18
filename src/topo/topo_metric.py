#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Thu Jun 28 08:32:18 2018

@author: avanetten

Implemention of the TOPO metric
https://pdfs.semanticscholar.org/51b0/51eba4f58afc34021ae23641fc8e168fdf07.pdf

"""

import os
import sys
import time
import numpy as np
import networkx as nx
import scipy.spatial
import matplotlib.pyplot as plt
import copy
from matplotlib.patches import Circle
from matplotlib.collections import PatchCollection
from shapely.geometry import Point, LineString
# import math
# import osmnx as ox

path_apls_src = os.path.dirname(os.path.realpath(__file__))
path_apls = os.path.dirname(path_apls_src)
sys.path.append(path_apls_src)
import apls
import apls_plots
import apls_utils
import osmnx_funcs


###############################################################################
def cut_linestring(line, distance, verbose=False):
    """
    Cuts a shapely linestring at a specified distance from its starting point.

    Notes
    ----
    Return orignal linestring if distance <= 0 or greater than the length of
    the line.
    Reference:
        http://toblerity.org/shapely/manual.html#linear-referencing-methods

    Arguments
    ---------
    line : shapely linestring
        Input shapely linestring to cut.
    distanct : float
        Distance from start of line to cut it in two.
    verbose : boolean
        Switch to print relevant values to screen.  Defaults to ``False``.

    Returns
    -------
    [line1, line2] : list
        Cut linestrings.  If distance <= 0 or greater than the length of
        the line, return input line.
    """

    if verbose:
        print("Cutting linestring at distance", distance, "...")
    if distance <= 0.0 or distance >= line.length:
        return [LineString(line)]

    # iterate through coorda and check if interpolated point has been passed
    # already or not
    coords = list(line.coords)
    for i, p in enumerate(coords):
        pdl = line.project(Point(p))
        if verbose:
            print(i, p, "line.project point:", pdl)
        if pdl == distance:
            return [
                LineString(coords[:i+1]),
                LineString(coords[i:])]
        if pdl > distance:
            cp = line.interpolate(distance)
            return [
                LineString(coords[:i] + [(cp.x, cp.y)]),
                LineString([(cp.x, cp.y)] + coords[i:])]

    # if we've reached here then that means we've encountered a self-loop and
    # the interpolated point is between the final midpoint and the the original
    # node
    i = len(coords) - 1
    cp = line.interpolate(distance)
    return [
        LineString(coords[:i] + [(cp.x, cp.y)]),
        LineString([(cp.x, cp.y)] + coords[i:])]


###############################################################################
def get_closest_edge_from_G(G_, point, nearby_nodes_set=set([]),
                            verbose=False):
    """
    Return closest edge to point, and distance to said edge.

    Notes
    -----
    Just discovered a similar function:
        https://github.com/gboeing/osmnx/blob/master/osmnx/utils.py#L501

    Arguments
    ---------
    G_ : networkx graph
        Input networkx graph, with edges assumed to have a dictioary of
        properties that includes the 'geometry' key.
    point : shapely Point
        Shapely point containing (x, y) coordinates.
    nearby_nodes_set : set
        Set of possible edge endpoints to search.  If nearby_nodes_set is not
        empty, only edges with a node in this set will be checked (this can
        greatly speed compuation on large graphs).  If nearby_nodes_set is
        empty, check all possible edges in the graph.
        Defaults to ``set([])``.
    verbose : boolean
        Switch to print relevant values to screen.  Defaults to ``False``.

    Returns
    -------
    best_edge, min_dist, best_geom : tuple
        best_edge is the closest edge to the point
        min_dist is the distance to that edge
        best_geom is the geometry of the ege
    """

    # get distances from point to lines
    dist_list = []
    edge_list = []
    geom_list = []
    p = point  # Point(point_coords)
    for i, (u, v, key, data) in enumerate(G_.edges(keys=True, data=True)):
        # print((" in get_closest_edge(): u,v,key,data:", u,v,key,data))
        # print ("  in get_closest_edge(): data:", data)

        # skip if u,v not in nearby nodes
        if len(nearby_nodes_set) > 0:
            if (u not in nearby_nodes_set) and (v not in nearby_nodes_set):
                continue
        if verbose:
            print(("u,v,key,data:", u, v, key, data))
            print(("  type data['geometry']:", type(data['geometry'])))
        try:
            line = data['geometry']
        except KeyError:
            line = data['attr_dict']['geometry']
        geom_list.append(line)
        dist_list.append(p.distance(line))
        edge_list.append([u, v, key])
    # get closest edge
    min_idx = np.argmin(dist_list)
    min_dist = dist_list[min_idx]
    best_edge = edge_list[min_idx]
    best_geom = geom_list[min_idx]

    return best_edge, min_dist, best_geom


###############################################################################
def insert_point_into_G(G_, point, node_id=100000, max_distance_meters=5,
                        nearby_nodes_set=set([]), allow_renaming=True,
                        verbose=False, super_verbose=False):
    """
    Insert a new node in the graph closest to the given point.

    Notes
    -----
    If the point is too far from the graph, don't insert a node.
    Assume all edges have a linestring geometry
    http://toblerity.org/shapely/manual.html#object.simplify
    Sometimes the point to insert will have the same coordinates as an
    existing point.  If allow_renaming == True, relabel the existing node.
    convert linestring to multipoint?
     https://github.com/Toblerity/Shapely/issues/190

    TODO : Implement a version without renaming that tracks which node is
        closest to the desired point.

    Arguments
    ---------
    G_ : networkx graph
        Input networkx graph, with edges assumed to have a dictioary of
        properties that includes the 'geometry' key.
    point : shapely Point
        Shapely point containing (x, y) coordinates
    node_id : int
        Unique identifier of node to insert. Defaults to ``100000``.
    max_distance_meters : float
        Maximum distance in meters between point and graph. Defaults to ``5``.
    nearby_nodes_set : set
        Set of possible edge endpoints to search.  If nearby_nodes_set is not
        empty, only edges with a node in this set will be checked (this can
        greatly speed compuation on large graphs).  If nearby_nodes_set is
        empty, check all possible edges in the graph.
        Defaults to ``set([])``.
    allow_renameing : boolean
        Switch to allow renaming of an existing node with node_id if the
        existing node is closest to the point. Defaults to ``False``.
    verbose : boolean
        Switch to print relevant values to screen.  Defaults to ``False``.
    super_verbose : boolean
        Switch to print mucho values to screen.  Defaults to ``False``.

    Returns
    -------
    G_, node_props, min_dist : tuple
        G_ is the updated graph
        node_props gives the properties of the inserted node
        min_dist is the distance from the point to the graph
    """

    # check if node_id already exists in G
    # if node_id in set(G_.nodes()):
    #    print ("node_id:", node_id, "already in G, cannot insert node!")
    #    return

    best_edge, min_dist, best_geom = get_closest_edge_from_G(
            G_, point, nearby_nodes_set=nearby_nodes_set,
            verbose=super_verbose)
    [u, v, key] = best_edge
    G_node_set = set(G_.nodes())

    if verbose:
        print("Inserting point:", node_id)
        print("best edge:", best_edge)
        print("  best edge dist:", min_dist)
        u_loc = [G_.nodes[u]['x'], G_.nodes[u]['y']]
        v_loc = [G_.nodes[v]['x'], G_.nodes[v]['y']]
        print("ploc:", (point.x, point.y))
        print("uloc:", u_loc)
        print("vloc:", v_loc)

    if min_dist > max_distance_meters:
        if verbose:
            print("min_dist > max_distance_meters, skipping...")
        return G_, {}, -1, -1

    else:
        # updated graph

        # skip if node exists already
        if node_id in G_node_set:
            if verbose:
                print("Node ID:", node_id, "already exists, skipping...")
            return G_, {}, -1, -1

        # G_.edges[best_edge[0]][best_edge[1]][0]['geometry']
        line_geom = best_geom

        # Length along line that is closest to the point
        line_proj = line_geom.project(point)

        # Now combine with interpolated point on line
        new_point = line_geom.interpolate(line_geom.project(point))
        x, y = new_point.x, new_point.y

        #################
        # create new node
        
        try:
            # first get zone, then convert to latlon
            _, _, zone_num, zone_letter = utm.from_latlon(G_.nodes[u]['lat'],
                                                          G_.nodes[u]['lon'])
            # convert utm to latlon
            lat, lon = utm.to_latlon(x, y, zone_num, zone_letter)
        except:
            lat, lon = y, x

        # set properties
        # props = G_.nodes[u]
        node_props = {'highway': 'insertQ',
                      'lat':     lat,
                      'lon':     lon,
                      'osmid':   node_id,
                      'x':       x,
                      'y':       y}
        # add node
        G_.add_node(node_id, **node_props)

        # assign, then update edge props for new edge
        _, _, edge_props_new = copy.deepcopy(
            list(G_.edges([u, v], data=True))[0])
        # remove extraneous 0 key

        # print ("edge_props_new.keys():", edge_props_new)
        # if list(edge_props_new.keys()) == [0]:
        #    edge_props_new = edge_props_new[0]

        # cut line
        split_line = cut_linestring(line_geom, line_proj)
        # line1, line2, cp = cut_linestring(line_geom, line_proj)
        if split_line is None:
            print("Failure in cut_linestring()...")
            print("type(split_line):", type(split_line))
            print("split_line:", split_line)
            print("line_geom:", line_geom)
            print("line_geom.length:", line_geom.length)
            print("line_proj:", line_proj)
            print("min_dist:", min_dist)
            return G_, {}, 0, 0

        if verbose:
            print("split_line:", split_line)

        # if cp.is_empty:
        if len(split_line) == 1:
            if verbose:
                print("split line empty, min_dist:", min_dist)
            # get coincident node
            outnode = ''
            outnode_x, outnode_y = -1, -1
            x_p, y_p = new_point.x, new_point.y
            x_u, y_u = G_.nodes[u]['x'], G_.nodes[u]['y']
            x_v, y_v = G_.nodes[v]['x'], G_.nodes[v]['y']
            # if verbose:
            #    print "x_p, y_p:", x_p, y_p
            #    print "x_u, y_u:", x_u, y_u
            #    print "x_v, y_v:", x_v, y_v

            # sometimes it seems that the nodes aren't perfectly coincident,
            # so see if it's within a buffer
            buff = 0.05  # meters
            if (abs(x_p - x_u) <= buff) and (abs(y_p - y_u) <= buff):
                outnode = u
                outnode_x, outnode_y = x_u, y_u
            elif (abs(x_p - x_v) <= buff) and (abs(y_p - y_v) <= buff):
                outnode = v
                outnode_x, outnode_y = x_v, y_v
            # original method with exact matching
            # if (x_p == x_u) and (y_p == y_u):
            #    outnode = u
            #    outnode_x, outnode_y = x_u, y_u
            # elif (x_p == x_v) and (y_p == y_v):
            #    outnode = v
            #    outnode_x, outnode_y = x_v, y_v
            else:
                print("Error in determining node coincident with node: "
                      + str(node_id) + " along edge: " + str(best_edge))
                print("x_p, y_p:", x_p, y_p)
                print("x_u, y_u:", x_u, y_u)
                print("x_v, y_v:", x_v, y_v)
                # return
                return G_, {}, 0, 0

            # if the line cannot be split, that means that the new node
            # is coincident with an existing node.  Relabel, if desired
            if allow_renaming:
                node_props = G_.nodes[outnode]
                # A dictionary with the old labels as keys and new labels
                #  as values. A partial mapping is allowed.
                mapping = {outnode: node_id}
                Gout = nx.relabel_nodes(G_, mapping)
                if verbose:
                    print("Swapping out node ids:", mapping)
                return Gout, node_props, x_p, y_p

            else:
                # new node is already added, presumably at the exact location
                # of an existing node.  So just remove the best edge and make
                # an edge from new node to existing node, length should be 0.0

                line1 = LineString([new_point, Point(outnode_x, outnode_y)])
                edge_props_line1 = edge_props_new.copy()
                edge_props_line1['length'] = line1.length
                edge_props_line1['geometry'] = line1
                # make sure length is zero
                if line1.length > buff:
                    print("Nodes should be coincident and length 0!")
                    print("  line1.length:", line1.length)
                    print("  x_u, y_u :", x_u, y_u)
                    print("  x_v, y_v :", x_v, y_v)
                    print("  x_p, y_p :", x_p, y_p)
                    print("  new_point:", new_point)
                    print("  Point(outnode_x, outnode_y):",
                          Point(outnode_x, outnode_y))
                    return

                # add edge of length 0 from new node to neareest existing node
                G_.add_edge(node_id, outnode, **edge_props_line1)
                return G_, node_props, x, y

                # originally, if not renaming nodes,
                # just ignore this complication and return the orignal
                # return G_, node_props, 0, 0

        else:
            # else, create new edges
            line1, line2 = split_line

            # get distances
            # print ("insert_point(), G_.nodes[v]:", G_.nodes[v])
            u_loc = [G_.nodes[u]['x'], G_.nodes[u]['y']]
            v_loc = [G_.nodes[v]['x'], G_.nodes[v]['y']]
            # compare to first point in linestring
            geom_p0 = list(line_geom.coords)[0]
            # or compare to inserted point? [this might fail if line is very
            #    curved!]
            # geom_p0 = (x,y)
            dist_to_u = scipy.spatial.distance.euclidean(u_loc, geom_p0)
            dist_to_v = scipy.spatial.distance.euclidean(v_loc, geom_p0)
            # reverse edge order if v closer than u
            if dist_to_v < dist_to_u:
                line2, line1 = split_line

            if verbose:
                print("Creating two edges from split...")
                print("   original_length:", line_geom.length)
                print("   line1_length:", line1.length)
                print("   line2_length:", line2.length)
                print("   u, dist_u_to_point:", u, dist_to_u)
                print("   v, dist_v_to_point:", v, dist_to_v)
                print("   min_dist:", min_dist)

            # add new edges
            edge_props_line1 = edge_props_new.copy()
            edge_props_line1['length'] = line1.length
            edge_props_line1['geometry'] = line1
            # remove geometry?
            # edge_props_line1.pop('geometry', None)
            # line2
            edge_props_line2 = edge_props_new.copy()
            edge_props_line2['length'] = line2.length
            edge_props_line2['geometry'] = line2
            # remove geometry?
            # edge_props_line1.pop('geometry', None)

            # insert edge regardless of direction
            # G_.add_edge(u, node_id, **edge_props_line1)
            # G_.add_edge(node_id, v, **edge_props_line2)

            # check which direction linestring is travelling (it may be going
            # from v -> u, which means we need to reverse the linestring)
            # otherwise new edge is tangled
            geom_p0 = list(line_geom.coords)[0]
            dist_to_u = scipy.spatial.distance.euclidean(u_loc, geom_p0)
            dist_to_v = scipy.spatial.distance.euclidean(v_loc, geom_p0)
            # if verbose:
            #    print "dist_to_u, dist_to_v:", dist_to_u, dist_to_v
            if dist_to_u < dist_to_v:
                G_.add_edge(u, node_id, **edge_props_line1)
                G_.add_edge(node_id, v, **edge_props_line2)
            else:
                G_.add_edge(node_id, u, **edge_props_line1)
                G_.add_edge(v, node_id, **edge_props_line2)

            if verbose:
                print("insert edges:", u, '-', node_id, 'and', node_id, '-', v)

            # remove initial edge
            G_.remove_edge(u, v, key)

            return G_, node_props, x, y




###############################################################################
def ensure_radial_linestrings(G_sub_, origin_node, x_coord='x', y_coord='y',
                              verbose=True):
    """
    Since we are injecting points on edges every X meters, make sure that
    the edge geometry is always pointing radially outward from the center
    node.  If geometries aren't always pointing the same direction we might
    inject points at different locations on the ground truth and proposal
    graphs.  Assume all edges have the geometry tag
    """

    # get location of graph center
    n_props = G_sub_.nodes[origin_node]
    origin_loc = [n_props[x_coord], n_props[y_coord]]

    # iterate through edges and check in linestring goes toward or away from
    #   center node
    for i, (u, v, key, data) in enumerate(G_sub_.edges(keys=True, data=True)):

        # now ensure linestring points away from origin
        #  assume that the start and end point arene't exactly the same
        #  distance from the origin
        line_geom = data['geometry']
        geom_p_start = list(line_geom.coords)[0]
        geom_p_end = list(line_geom.coords)[-1]
        dist_to_start = scipy.spatial.distance.euclidean(
            origin_loc, geom_p_start)
        dist_to_end = scipy.spatial.distance.euclidean(origin_loc, geom_p_end)
        # reverse the line if the end is closer to the origin than the start
        if dist_to_end < dist_to_start:
            if verbose:
                print(("Reverse linestring from", u, "to", v))
            coords_rev = list(data['geometry'].coords)[::-1]
            line_geom_rev = LineString(coords_rev)
            data['geometry'] = line_geom_rev

    return G_sub_


###############################################################################
def insert_holes_or_marbles(G_, origin_node, interval=50, n_id_add_val=1,
                            verbose=False):
    """
    Insert points on the graph on the specified interval
    n_id_add_val sets min midpoint id above existing nodes
        e.g.: G.nodes() = [1,2,4], if n_id_add_val = 5, midpoints will
        be [9,10,11,...]
    Apapted from apls.py.create_graph(midpoints()
    """

    if len(G_.nodes()) == 0:
        return G_, [], []

    # midpoints
    xms, yms = [], []
    Gout = G_.copy()
    midpoint_name_val, midpoint_name_inc = np.max(
        list(G_.nodes())) + n_id_add_val, n_id_add_val
    # for u, v, key, data in G_.edges(keys=True, data=True):
    for u, v, data in G_.edges(data=True):

        # curved line
        if 'geometry' in data:

            edge_props_init = G_.edges([u, v])

            linelen = data['length']
            line = data['geometry']

            xs, ys = line.xy  # for plotting

            #################
            # ignore short lines
            if linelen < interval:
                # print "Line too short, skipping..."
                continue
            #################

            if verbose:
                print("u,v:", u, v)
                print("data:", data)
                print("edge_props_init:", edge_props_init)

            # interpolate injection points
            # get evenly spaced points (skip first point at 0)
            interp_dists = np.arange(0, linelen, interval)[1:]
            # evenly spaced midpoints (from apls.create_graph(midpoints()
            # npoints = len(np.arange(0, linelen, interval)) + 1
            # interp_dists = np.linspace(0, linelen, npoints)[1:-1]
            if verbose:
                print("interp_dists:", interp_dists)

            # create nodes
            node_id_new_list = []
            xms_tmp, yms_tmp = [], []
            for j, d in enumerate(interp_dists):
                if verbose:
                    print("j,d", j, d)

                midPoint = line.interpolate(d)
                xm0, ym0 = midPoint.xy
                xm = xm0[-1]
                ym = ym0[-1]
                point = Point(xm, ym)
                xms.append(xm)
                yms.append(ym)
                xms_tmp.append(xm)
                yms_tmp.append(ym)
                if verbose:
                    print("midpoint:", xm, ym)

                # add node to graph, with properties of u
                node_id = midpoint_name_val
                # node_id = np.round(u + midpoint_name_val,2)
                midpoint_name_val += midpoint_name_inc
                node_id_new_list.append(node_id)
                if verbose:
                    print("node_id:", node_id)

                # add to graph
                Gout, node_props, xn, yn = insert_point_into_G(
                    Gout, point, node_id=node_id, allow_renaming=False,
                    verbose=verbose)

    return Gout, xms, yms


###############################################################################
def compute_single_topo(G_sub_gt_, G_sub_p_,
                        x_coord='x', y_coord='y', hole_size=5,
                        allow_multi_hole=False,
                        verbose=False, super_verbose=False):
    '''compute filled and empty holes for a single subgraph
    By default, Only allow one marble in each hole (allow_multi_hole=False)'''

    # get node positions
    pos_gt = apls_utils._get_node_positions(G_sub_gt_, x_coord=x_coord,
                                            y_coord=y_coord)
    pos_p = apls_utils._get_node_positions(G_sub_p_, x_coord=x_coord,
                                           y_coord=y_coord)

    # construct kdtree of ground truth
    kd_idx_dic0, kdtree0, pos_arr0 = apls_utils.G_to_kdtree(G_sub_gt_)

    prop_tp, prop_fp = [], []
    gt_tp, gt_fn = [], []
    gt_match_idxs_set = set()   # set of already matched gt idxs
    # iterate through marbles to see if it fall in a hole
    for i, prop_point in enumerate(pos_p):
        if verbose:
            print(("prop i:", i, "prop node:", list(G_sub_p_.nodes())[i]))
        # see if a marble is close to a hole
        # dists, idxs = kdtree.query(prop_point, k=100,
        #                           distance_upper_bount=hole_size)

        idxs_raw = kdtree0.query_ball_point(prop_point, r=hole_size)
        if not allow_multi_hole:
            # subtract previously matched items from indices
            idxs = list(set(idxs_raw) - gt_match_idxs_set)
        else:
            # allow multiple marbles to fall into the same hole
            idxs = idxs_raw

        if super_verbose:
            print(("idxs:", idxs))
            print(("idxs_raw:", idxs_raw))

        # if no results, add to false positive
        if len(idxs) == 0:
            prop_fp.append(i)

        # otherwise, check what's close
        else:

            # check distances of remaining items
            dists_m = np.asarray([scipy.spatial.distance.euclidean(
                prop_point, [kdtree0.data[itmp][0], kdtree0.data[itmp][1]])
                for itmp in idxs])
            # get min distance
            jmin = np.argmin(dists_m)
            idx_min = idxs[jmin]

            # add to true positive
            prop_tp.append(i)
            gt_tp.append(idx_min)
            gt_match_idxs_set.add(idx_min)

    # count up how many holes we've filled
    n_holes = len(pos_gt)
    n_marbles = len(pos_p)
    true_pos_count = len(prop_tp)
    # this should be the same as n_marbles_in_holes
    n_holes_filled = len(gt_tp)
    false_pos_count = len(prop_fp)
    gt_fn = list(set(range(len(pos_gt))) - gt_match_idxs_set)
    n_empty_holes = n_holes - true_pos_count
    false_neg_count = n_empty_holes
    try:
        precision = float(true_pos_count) / \
            float(true_pos_count + false_pos_count)
    except:
        precision = 0
    try:
        recall = float(true_pos_count) / \
            float(true_pos_count + false_neg_count)
    except:
        recall = 0
    try:
        f1 = 2. * precision * recall / (precision + recall)
    except:
        f1 = 0

    if verbose:
        print(("Num holes:", n_holes))
        print(("Num marbles:", n_marbles))
        print(("gt_match_idxs_set:", gt_match_idxs_set))
        print(("Num marbles in holes (true pos):", true_pos_count))
        print(("Num extra marbles:", false_pos_count))
        print(("Num holes filled:", n_holes_filled))
        print(("Num empty holes0:", false_neg_count))
        print(("Num empty holes1:", len(gt_fn)))
        print(("precision:", precision))
        print(("recall:", recall))
        print(("f1:", f1))

    # return  pos_gt, gt_tp, gt_fn, \
    #        pos_p, prop_tp, prop_fp

    return true_pos_count, false_pos_count, false_neg_count, \
        precision, recall, f1


###############################################################################
def compute_topo(G_gt_, G_p_, subgraph_radius=150, interval=30, hole_size=5,
                 n_measurement_nodes=10000, x_coord='x', y_coord='y',
                 allow_multi_hole=False, prime=False,
                 make_plots=False, verbose=False):
    '''Compute topo metric
     subgraph_radius = radius for topo computation
     interval is spacing of inserted points
     hole_size is the buffer within which proposals must fall
     '''

    t0 = time.time()
    if (len(G_gt_) == 0) or (len(G_p_) == 0):
        return 0, 0, 0, 0, 0, 0

    if verbose:
        print(("G_gt_.nodes():", G_gt_.nodes()))
    # define ground truth kdtree
    kd_idx_dic, kdtree, pos_arr = apls_utils.G_to_kdtree(G_gt_)
    # proposal graph kdtree
    kd_idx_dic_p, kdtree_p, pos_arr_p = apls_utils.G_to_kdtree(G_p_)

    true_pos_count_l, false_pos_count_l, false_neg_count_l = [], [], []
    # precision_l, recall_l, f1_l = [], [], []

    samples_metadata = [] # Capture samples.

    if not prime: # In case of normal we can deal with missing start or end nodes.
        origin_nodes = G_gt_.nodes()
    else: # In case of prime, we prefilter origin nodes which have a proposed node nearby.
        origin_nodes = []
        
        for node in G_gt_.nodes():

            n_props = G_gt_.nodes[node]
            x0, y0 = n_props[x_coord], n_props[y_coord]
            origin_point = [x0, y0]

            node_names_p, idxs_refine_p, dists_m_refine_p = apls_utils._query_kd_ball(
                kdtree_p, kd_idx_dic_p, origin_point, hole_size)

            if len(node_names_p) > 0:
                origin_nodes.append(node)
    
    # Make sure we don't pick more nodes than exist in the graph
    n_pick = min(n_measurement_nodes, len(G_gt_.nodes()))
    # Picking nodes.
    origin_nodes = np.random.choice(origin_nodes, n_pick)

    for i, origin_node in enumerate(origin_nodes):

        if (i % 20) == 0:
            print(i, "Origin node:", origin_node)
        n_props = G_gt_.nodes[origin_node]
        x0, y0 = n_props[x_coord], n_props[y_coord]
        origin_point = [x0, y0]

        # get subgraph
        node_names, node_dists = apls_utils._nodes_near_origin(
            G_gt_, origin_node,
            kdtree, kd_idx_dic,
            x_coord=x_coord, y_coord=y_coord,
            radius_m=subgraph_radius,
            verbose=verbose)

        if verbose and len(node_names) == 0:
            print("subgraph empty")

        # get subgraph
        G_sub0 = G_gt_.subgraph(node_names)
        if verbose:
            print(("G_sub0.nodes():", G_sub0.nodes()))

        # make sure all nodes connect to origin
        node_names_conn = nx.node_connected_component(G_sub0, origin_node)
        G_sub1 = G_sub0.subgraph(node_names_conn)

        # ensure linestrings are radially out from origin point
        G_sub = ensure_radial_linestrings(G_sub1, origin_node,
                                          x_coord='x', y_coord='y',
                                          verbose=verbose)

        # insert points
        G_holes, xms, yms = insert_holes_or_marbles(
            G_sub, origin_node,
            interval=interval, n_id_add_val=1,
            verbose=False)

        #####
        # Proposal

        # determine nearast node to ground_truth origin_point
        # query kd tree for origin node
        node_names_p, idxs_refine_p, dists_m_refine_p = apls_utils._query_kd_ball(
            kdtree_p, kd_idx_dic_p, origin_point, hole_size)

        if len(node_names_p) == 0:
            if verbose:
                print(("Oops, no proposal node correspnding to", origin_node))
            # all nodes are false positives in this case
            true_pos_count_l.append(0)
            false_pos_count_l.append(0)
            false_neg_count_l.append(len(G_holes.nodes()))
            samples_metadata.append(0)
            continue

        # get closest node
        origin_node_p = node_names_p[np.argmin(dists_m_refine_p)]
        # get coords of the closest point
        n_props = G_p_.nodes[origin_node_p]
        xp, yp = n_props['x'], n_props['y']
        if verbose:
            print(("origin_node_p:", origin_node_p))

        # get subgraph
        node_names_p, node_dists_p = apls_utils._nodes_near_origin(
            G_p_, origin_node_p,
            kdtree_p, kd_idx_dic_p,
            x_coord=x_coord, y_coord=y_coord,
            radius_m=subgraph_radius,
            verbose=verbose)

        # get subgraph
        G_sub0_p = G_p_.subgraph(node_names_p)
        if verbose:
            print(("G_sub0_p.nodes():", G_sub0_p.nodes()))

        # make sure all nodes connect to origin
        node_names_conn_p = nx.node_connected_component(
            G_sub0_p, origin_node_p)
        G_sub1_p = G_sub0_p.subgraph(node_names_conn_p)

        # ensure linestrings are radially out from origin point
        G_sub_p = ensure_radial_linestrings(G_sub1_p, origin_node_p,
                                            x_coord='x', y_coord='y',
                                            verbose=verbose)

        # insert points
        G_holes_p, xms, yms = insert_holes_or_marbles(
            G_sub_p, origin_node_p,
            interval=interval, n_id_add_val=1,
            verbose=False)

        ####################
        # compute topo metric
        true_pos_count, false_pos_count, false_neg_count, \
            precision, recall, f1 = compute_single_topo(
                G_holes, G_holes_p,
                x_coord=x_coord, y_coord=y_coord,
                allow_multi_hole=allow_multi_hole,
                hole_size=hole_size, verbose=verbose)
        true_pos_count_l.append(true_pos_count)
        false_pos_count_l.append(false_pos_count)
        false_neg_count_l.append(false_neg_count)

        samples_metadata.append(f1)

        # plot if i == 0:
        if i == 0 and make_plots:
            # plot G_gt_
            plt.close('all')
            # plot initial graph
            fig, ax = osmnx_funcs.plot_graph(G_gt_, axis_off=False)
            ax.set_title("Ground Truth Input plot")
            # draw a circle (this doesn't work unless it's a PatchCollection!)
            patches = [Circle((x0, y0), hole_size, alpha=0.3)]
            p = PatchCollection(patches, alpha=0.4)
            ax.add_collection(p)
            # also a simple point
            ax.scatter([x0], [y0], c='red')
            plt.close('all')

            # plot subgraph
            fig2, ax2 = osmnx_funcs.plot_graph(G_sub, axis_off=False)
            ax2.set_title("Subgraph")
            plt.close('all')

            # plot G_holes
            fig, ax = osmnx_funcs.plot_graph(G_holes, axis_off=False)
            ax.set_title("Subgraph with holes")
            # plot holes
            # draw a circle (this doesn't work unless it's a PatchCollection!)
            node_coords = []
            for i, n in enumerate(G_holes.nodes()):
                n_props = G_holes.nodes[n]
                node_coords.append([n_props[x_coord], n_props[y_coord]])
            patches = [Circle((coord), hole_size, alpha=0.3)
                       for coord in node_coords]
            p = PatchCollection(patches, alpha=0.4, color='yellow')
            ax.add_collection(p)
            plt.close('all')

            # plot initial graph
            fig, ax = osmnx_funcs.plot_graph(G_p_, axis_off=False)
            ax.set_title("Proposal Input plot")
            # draw a circle (this doesn't work unless it's a PatchCollection!)
            patches = [Circle((xp, yp), hole_size, alpha=0.3)]
            p = PatchCollection(patches, alpha=0.4)
            ax.add_collection(p)
            # also scatter plot a simple point
            ax.scatter([xp], [yp], c='red')
            plt.close('all')

            # plot subgraph
            fig2, ax2 = osmnx_funcs.plot_graph(G_sub_p, axis_off=False)
            ax2.set_title("Proposal Subgraph")
            plt.close('all')

            # plot G_holes
            fig, ax = osmnx_funcs.plot_graph(
                G_holes_p, axis_off=False, node_color='red')
            ax.set_title("Proposal Subgraph with marbles")
            # plot marbles?  (Since marbles have size 0 and only fall into holes, skip)
            # draw a circle (this doesn't work unless it's a PatchCollection!)
            #node_coords  = []
            # for i,n in enumerate(G_holes_p.nodes()):
            #    n_props = G_holes_p.node[n]
            #    node_coords.append([n_props[x_coord], n_props[y_coord]])
            #patches = [Circle((coord), hole_size, alpha=0.3) for coord in node_coords]
            #p = PatchCollection(patches, alpha=0.4, color='yellow')
            # ax.add_collection(p)
            plt.close('all')

            # plot marbles overlaid on holes
            # plot G_holes
            fig, ax = osmnx_funcs.plot_graph(G_holes, axis_off=False)
            ax.set_title("GT graph and holes (yellow), Prop marbles (red)")
            # plot holes
            # draw a circle (this doesn't work unless it's a PatchCollection!)
            node_coords = []
            for i, n in enumerate(G_holes.nodes()):
                n_props = G_holes.nodes[n]
                node_coords.append([n_props[x_coord], n_props[y_coord]])
            patches = [Circle((coord), hole_size, alpha=0.3)
                       for coord in node_coords]
            p = PatchCollection(patches, alpha=0.4, color='yellow')
            ax.add_collection(p)
            # scatter proposal nodes
            arr_marbles = apls_utils._get_node_positions(
                G_holes_p, x_coord='x', y_coord='y')
            ax.scatter(arr_marbles[:, 0], arr_marbles[:, 1], c='red')

            # show gt node ids
            ax = apls_plots._plot_node_ids(G_holes, ax, fontsize=9)  # node ids

            # show prop node ids
            ax = apls_plots.plot_node_ids(
                G_holes_p, ax, fontsize=9)  # node ids
            plt.close('all')

    # compute total score
    tp_tot = np.sum(true_pos_count_l)
    fp_tot = np.sum(false_pos_count_l)
    fn_tot = np.sum(false_neg_count_l)

    try:
        precision = float(tp_tot) / float(tp_tot + fp_tot)
    except:
        precision = 0
    try:
        recall = float(tp_tot) / float(tp_tot + fn_tot)
    except:
        recall = 0
    try:
        f1 = 2. * precision * recall / (precision + recall)
    except:
        f1 = 0

    # print("TOPO metric:")
    # print("  total time elapsed to compute TOPO and make plots:",
        #   time.time() - t0, "seconds")
    # print("  total precison:", precision)
    # print("  total recall:", recall)
    # print("  total f1:", f1)

    data = {
        "tp_tot"   : tp_tot,
        "fp_tot"   : fp_tot,
        "fn_tot"   : fn_tot,
        "precision": precision,
        "recall"   : recall,
        "f1"       : f1,
        "samples"  : samples_metadata
    }

    return f1, data


###############################################################################
###############################################################################

###############################################################################
if __name__ == "__main__":

    # Test
    ##########################
    n_measurement_nodes = 10  # there are ~30 nodes per graph
    subgraph_radius = 150     # radius for topo computation
    interval = 30    # interval for holes/marbles
    hole_size = 5
    x_coord = 'x'
    y_coord = 'y'
    allow_multi_hole = False
    make_plots = True
    run_all = True
    verbose = True
    # pick_random_start_node = True

    truth_dir = '/raid/cosmiq/spacenet/data/spacenetv2/AOI_2_Vegas_Test/400m/gt_graph_pkls'
    prop_dir = 'raid/cosmiq/basiss/inference_mod_new/results/rgb_test_sn_vegas/graphs'
    ##########################

    name_list = os.listdir(truth_dir)
    f = name_list[np.random.randint(len(name_list))]
    f = 'AOI_2_Vegas_img150.pkl'
    # f = 'AOI_2_Vegas_img1532.pkl'  # empty proposal

    print(("f:", f))
    t0 = time.time()

    # get original graph
    outroot = f.split('.')[0]
    print("\noutroot:", outroot)
    gt_file = os.path.join(truth_dir, f)
    prop_file = os.path.join(prop_dir, outroot + '.gpickle')

    # ground truth graph
    G_gt_init = nx.read_gpickle(gt_file)
    # G_gt_init1 = osmnx_funcs.simplify_graph(G_gt_init0.to_directed()).to_undirected()
    # G_gt_init = osmnx_funcs.project_graph(G_gt_init1)
    G_gt_init = apls.create_edge_linestrings(
        G_gt_init, remove_redundant=True, verbose=False)

    print(("G_gt_init.nodes():", G_gt_init.nodes()))
    # define ground truth kdtree
    # kd_idx_dic, kdtree, pos_arr = G_to_kdtree(G_gt_init)

    # proposal graph
    # G_p_ = nx.read_gpickle(prop_file)
    G_p_init0 = nx.read_gpickle(prop_file)
    G_p_init1 = osmnx_funcs.simplify_graph(G_p_init0.to_directed()).to_undirected()
    G_p_init = osmnx_funcs.project_graph(G_p_init1)
    G_p_init = apls.create_edge_linestrings(
        G_p_init, remove_redundant=True, verbose=False)
    # kd_idx_dic_p, kdtree_p, pos_arr_p = G_to_kdtree(G_p_init)

    tp_tot, fp_tot, fn_tot, precision, recall, f1 = \
        compute_topo(G_gt_init, G_p_init, subgraph_radius=subgraph_radius,
                     interval=interval, hole_size=hole_size,
                     n_measurement_nodes=n_measurement_nodes,
                     x_coord=x_coord, y_coord=y_coord,
                     allow_multi_hole=allow_multi_hole,
                     make_plots=make_plots, verbose=verbose)

    ############
    # also compute total topo metric for entire folder
    if run_all:
        t0 = time.time()
        tp_tot_list, fp_tot_list, fn_tot_list = [], [], []
        for i, f in enumerate(name_list):

            # get original graph
            outroot = f.split('.')[0]
            print("\n", i, "/", len(name_list), "outroot:", outroot)
            #print ("\n", i, "/", len(name_list), "outroot:", outroot)
            gt_file = os.path.join(truth_dir, f)

            # ground truth graph
            G_gt_init = nx.read_gpickle(gt_file)
            # G_gt_init1 = osmnx_funcs.simplify_graph(G_gt_init0.to_directed()).to_undirected()
            # G_gt_init = osmnx_funcs.project_graph(G_gt_init1)
            G_gt_init = apls.create_edge_linestrings(
                G_gt_init, remove_redundant=True, verbose=False)
            if len(G_gt_init.nodes()) == 0:
                continue

            # proposal graph
            prop_file = os.path.join(prop_dir, outroot + '.gpickle')
            if not os.path.exists(prop_file):
                tp_tot_list.append(0)
                fp_tot_list.append(0)
                fn_tot_list.append(len(G_gt_init.nodes()))
                continue

            # G_p_init = nx.read_gpickle(prop_file)
            G_p_init0 = nx.read_gpickle(prop_file)
            G_p_init1 = osmnx_funcs.simplify_graph(
                G_p_init0.to_directed()).to_undirected()
            G_p_init = osmnx_funcs.project_graph(G_p_init1)
            G_p_init = apls.create_edge_linestrings(
                G_p_init, remove_redundant=True, verbose=False)

            tp, fp, fn, precision, recall, f1 = \
                compute_topo(G_gt_init, G_p_init,
                             subgraph_radius=subgraph_radius,
                             interval=interval, hole_size=hole_size,
                             n_measurement_nodes=n_measurement_nodes,
                             x_coord=x_coord, y_coord=y_coord,
                             allow_multi_hole=allow_multi_hole,
                             make_plots=False, verbose=False)

            tp_tot_list.append(tp)
            fp_tot_list.append(fp)
            fn_tot_list.append(fn)

        # compute total score
        tp_tot = np.sum(tp_tot_list)
        fp_tot = np.sum(fp_tot_list)
        fn_tot = np.sum(fn_tot_list)
        precision = float(tp_tot) / float(tp_tot + fp_tot)
        recall = float(tp_tot) / float(tp_tot + fn_tot)
        f1 = 2. * precision * recall / (precision + recall)

        print(("Total TOPO metric for", len(name_list), "files:"))
        print(("  hole_size:", hole_size, "interval:", interval))
        print(("  subgraph_radius:", subgraph_radius,
               "allow_multi_hole?", allow_multi_hole))
        print(("  total time elapsed to compute TOPO and make plots:",
               time.time() - t0, "seconds"))
        print(("  total precison:", precision))
        print(("  total recall:", recall))
        print(("  total f1:", f1))
