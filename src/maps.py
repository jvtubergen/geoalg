# Google Maps retrieval functionality
from dependencies import *

earth_radius = 6378137 # meters
earth_circumference = 2*pi*earth_radius

# Gudermann function. Real argument abs(rho) < 0.5*pi 
# https://en.wikipedia.org/wiki/Gudermannian_function
def gd(tau):
    return 2 * atan(exp(tau)) - 0.5 * pi
def gd_inv(rho):
    return log(sec(rho) + tan(rho))


# Conversion between radians and degrees (for readability).
def rad_to_deg(phi):
    return phi * 180 / pi
def deg_to_rad(rho):
    return rho * pi / 180


# Maximal latitude (of web mercator projection).
# https://en.wikipedia.org/wiki/Mercator_projection
max_lat = rad_to_deg(gd(pi)) # = atan(sinh(pi)) / pi * 180


# Read image file as numpy array.
def read_image(filename):
    image = pil.Image.open(filename)
    image = image.convert("RGB")
    image = np.array(image)
    return image


# Write numpy array with size (width, height, RGB) as an image file.
def write_image(image, filename):
    pil.Image.fromarray(image).save(filename) 


# Cut out pixels of image at borders.
def cut_logo(image, scale, margin):
    off = scale * margin
    return image[off:-off,off:-off,:]


# Build filename and url for image.
def build_url(lat, lon, zoom, resolution, scale, api_key):
    filename = "image_lat=%.6f_lon=%.6f_zoom=%d_scale=%d_size=%d.png" % (lat, lon, zoom, scale, resolution)
    url = "https://maps.googleapis.com/maps/api/staticmap?center="+("%.6f" % lat)+","+("%.6f" % lon)+"&zoom="+str(int(zoom))+"&scale="+str(int(scale))+"&size="+str(int(resolution))+"x"+str(int(resolution))+"&maptype=satellite&style=element:labels|visibility:off&key=" + api_key
    return filename, url


# Fetch url and store under fname.
def fetch_url(fname, url):
    if 0 == subprocess.Popen("timeout 5s wget -O tmp.png \"" + url + "\"", shell = True).wait():
        return 0 == subprocess.Popen("mv tmp.png " + fname, shell=True).wait()
    return False


# Uniform web mercator projection
# y,x in [0,1], starting in upper-left corner (thus lat 85 and lon -180)
# lat in [-85, 85], lon in [-180, 180]
def latlon_to_webmercator_uniform(lat, lon):
    x = 0.5 + deg_to_rad(lon) / (2*pi)
    y = 0.5 - gd_inv(deg_to_rad(lat)) / (2*pi)
    return y, x
def webmercator_uniform_to_latlon(y, x):
    lon = rad_to_deg(2*pi * (x - 0.5))
    lat = rad_to_deg(gd(2*pi * (0.5 - y)))
    return lat, lon


# Conversion between latlon and world/tile/pixelcoordinates.
# Tile and pixel coordinates depends on zoom level.
# In general, the uniform webmercator y,x values are scaled.
def latlon_to_pixelcoord(lat, lon, zoom):
    y, x = latlon_to_webmercator_uniform(lat, lon)
    pixelcount = int(256 * pow(2, zoom))
    return int(y * pixelcount), int(x * pixelcount)

def latlon_to_tilecoord(lat, lon, zoom):
    y, x = latlon_to_webmercator_uniform(lat, lon)
    tilecount = int(pow(2, zoom))
    return int(y * tilecount), int(x * tilecount)

def latlon_to_worldcoord(lat, lon):
    y, x = latlon_to_webmercator_uniform(lat, lon)
    return y * 256, x * 256

def pixelcoord_to_latlon(y, x, zoom):
    pixelcount = int(256 * pow(2, zoom))
    return webmercator_uniform_to_latlon(y / pixelcount, x / pixelcount)


# GSD (Ground Sampling Distance): spatial resolution (in meters) of the image.
def compute_gsd(lat, zoom, scale):
    k = sec(deg_to_rad(lat)) # Scale factor by mercator projection.
    w = earth_circumference  # Total image distance on 256x256 world image
    return w / (256 * pow(2, zoom) * k * scale)


# Retrieve images, stitch them together.
def construct_image(p1, p2, zoom, scale, api_key):

    # Deconstruct latlons.
    lat1, lon1 = p1 # Upper-left  corner (thus higher latitude and lower longitude).
    lat2, lon2 = p2 # Lower-right corner (thus lower latitude and higher longitude).

    # Obtain pixel range in google maps at given zoom.
    y1, x1 = latlon_to_pixelcoord(lat1, lon1, zoom)
    y2, x2 = latlon_to_pixelcoord(lat2, lon2, zoom)
    y2 += 1
    x2 += 1

    max_resolution = 640 # Google Maps images up to 640x640.
    margin = 22 # Necessary to cut out logo.

    # Pixels are considered without scale (Scale is doubling resolution so effectively acting on a higher zoom level, but in itself not influences pixel/latlon coordination.)
    maxpixelsperimage = max_resolution - 2 * margin # max resolution minus google logo pixels border.
    totalpixels  = int(max(x2-x1,y2-y1))
    centerpixelx = int(0.5 * (x1 + x2))
    centerpixely = int(0.5 * (y1 + y2))

    # Recompute resolution.
    imagecount = ceil(totalpixels / maxpixelsperimage)
    pixelsize  = totalpixels / imagecount
    resolution = ceil(pixelsize)

    # Recompute upperleft and lowerright pixel coordinates.
    upperleftpixelx  = centerpixelx - (0.5 + 0.5 * (imagecount - 1)) * resolution
    upperleftpixely  = centerpixely - (0.5 + 0.5 * (imagecount - 1)) * resolution
    lowerrightpixelx = centerpixelx + (0.5 + 0.5 * (imagecount - 1)) * resolution
    lowerrightpixely = centerpixely + (0.5 + 0.5 * (imagecount - 1)) * resolution

    # Figure out pixel coordinates for fetching.
    pixelcoords   = [(int(upperleftpixely + (j + 0.5) * resolution), int(upperleftpixelx + (i + 0.5) * resolution))for j in range(imagecount) for i in range(imagecount)]
    latloncoords  = [pixelcoord_to_latlon(y, x, zoom) for y,x in pixelcoords]
    uniformcoords = [latlon_to_webmercator_uniform(lat, lon) for lat,lon in latloncoords]

    # # Distance between pixel
    # print("resolution: ", resolution)
    # print("pcoords: ", [(x2-x1, y2-y1) for ((x1,y1),(x2,y2)) in zip(pixelcoords, pixelcoords[1:])])

    # Construct and fetch urls.
    urls = [build_url(lat, lon, zoom, resolution + 2*margin, scale, api_key) for (lat, lon) in latloncoords]
    for (fname, url) in urls:
        if not os.path.isfile(fname):
            assert fetch_url(fname, url)
    
    # Load images into program workmemory.
    images = [read_image(fname) for (fname, _) in urls]
    images = [cut_logo(image, scale, margin) for image in images]

    size = scale * resolution
    superimage = np.ndarray((imagecount*size, imagecount*size, 3), dtype="uint8")

    n = imagecount
    m = size
    for i in range(n):
        for j in range(n):
            superimage[i*m:(i+1)*m,j*m:(j+1)*m,:] = images[i*n+j]
    
    return superimage


# Read API key stored locally.
def read_api_key():
    with open("api_key.txt") as f: 
        api_key = f.read()
    return api_key
