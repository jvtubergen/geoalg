import pandas as pd
import geopandas as gpd
import networkx as nx
import osmnx as ox
import numpy as np
import matplotlib as plt
import PIL as pil

import os
import subprocess

# Standard library
import math
import itertools
import random

# Geometry utilities
from shapely.geometry import LineString, Point
import utm
import rtree

# IO dependencies
from pathlib import Path
from fileinput import input

# Utils
from operator import itemgetter
import traceback


# Math functions
cos  = math.cos
sec  = lambda phi: 1/cos(phi) # Secant
sin  = math.sin
tan  = math.tan
atan = math.atan
sinh = math.sinh
exp  = math.exp
log  = math.log
pow  = math.pow
pi   = math.pi

ceil = math.ceil
