import numpy as np
import cv2
from scipy import ndimage
from IPython import embed

# TODO - camera calibration:
# http://opencv-python-tutroals.readthedocs.org/en/latest/py_tutorials/py_calib3d/py_calibration/py_calibration.html
# http://www.pyimagesearch.com/2015/01/19/find-distance-camera-objectmarker-using-python-opencv/
# http://www.pyimagesearch.com/2014/09/01/build-kick-ass-mobile-document-scanner-just-5-minutes/

# calculating contour sizes
MIN_THRESHOLD = 500
MAX_THRESHOLD = 100000

# square config
SQUARE_WIDTH = 7.5
SQUARE_N = 5
SQ_W = SQUARE_WIDTH / SQUARE_N
SQUARE_SPACING = 15

KNOWN_Z = 24
KNOWN_AREA = 7.5*7.5

# linear gradient config
#GRADIENT = []
GRADIENT_KNOWN_WIDTH = 12*12

# get hardlight contours of an image
# returns a tuple of (contours, hardlight_filtered_image)
def hardlight_contours(image_src, take_first=100):
    img = cv2.imread(image_src, 0) # 0 means grayscale
    # force hard black and white
    ret, img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # find contours, make sure to copy image otherwise it gets distorted
    (image, cnts, _) = cv2.findContours(img.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    cnts = sorted(cnts, key = cv2.contourArea, reverse = True)[:take_first]

    return (cnts, img)

# returns an array of tuples (object_code, size (w,h), rectangle)
def identify_objects(image_src):
    (cnts, img) = hardlight_contours(image_src)
    # loop over our contours
    objects = []
    for c in cnts:
        # approximate the contour
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.01 * peri, True)

        # if our approximated contour has four points and area is within our range
        #area = cv2.contourArea(approx)
        c_rect = x,y,w,h = cv2.boundingRect(c)
        area = w*h
        if len(approx) == 4 and area > MIN_THRESHOLD and area <= MAX_THRESHOLD:
            norm_img = four_point_transform(img, approx)
            rect = cv2.boundingRect(norm_img)
            code = get_object_code(norm_img, rect)
            if code > 0:
                objects.append((code, (rect[2], rect[3]), c_rect))

    return objects

# known(pixels, dist)
def locate_xyz(image_src, known, out):
    # debug stuff
    img_color = cv2.imread(image_src)

    objs = identify_objects(image_src)
    for o in objs:
        code, size, pos_rect = o
        x,y,w,h = pos_rect

        # debug stuff
        cv2.rectangle(img_color, (x, y), (x + w, y + h), (0,0,255), 3)
        cv2.putText(img_color, str(code), (x, y), cv2.FONT_HERSHEY_SIMPLEX, 2, (255,0,0))
        cv2.imwrite(out, img_color)

        y = float(known[0])/float(size[0]) * float(known[1])
        print y
        break

# find an object's code from a full-sized image object
# TODO: to make this better, instead of sampling one pixel average a small area within each shape
def get_object_code(image, rect):
    x,y,w,h = rect
    cx = x + w/2
    cy = y + h/2
    dx = w/SQUARE_N
    dy = h/SQUARE_N
    val = 511 - (binary(image[cy - dy, cx - dx]) * 1 + binary(image[cy - dy, cx]) * 2 + binary(image[cy - dy, cx + dx]) * 4 + \
           binary(image[cy, cx - dx]) * 8 + binary(image[cy, cx]) * 16 + binary(image[cy, cx + dx]) * 32 + \
           binary(image[cy + dy, cx - dx]) * 64 + binary(image[cy + dy, cx]) * 128 + binary(image[cy + dy, cx + dx]) * 256)
    return val if val >= 0 else 0

# returns either 0 or 1 if val is less than mid of max_val or greater
def binary(val, max_val=255):
    return 0 if val < max_val / 2 else 1

# normalizes an object with coordinates pts on image
def four_point_transform(image, pts):
    # obtain a consistent order of the points and unpack them individually
    rect = order_points(pts.reshape(4,2))
    (tl, tr, br, bl) = rect

    # compute the width of the new image, which will be the
    # maximum distance between bottom-right and bottom-left
    # x-coordiates or the top-right and top-left x-coordinates
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
 
    # compute the height of the new image, which will be the
    # maximum distance between the top-right and bottom-right
    # y-coordinates or the top-left and bottom-left y-coordinates
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))

    # now that we have the dimensions of the new image, construct
    # the set of destination points to obtain a "birds eye view",
    # (i.e. top-down view) of the image, again specifying points
    # in the top-left, top-right, bottom-right, and bottom-left
    # order
    dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]], dtype = "float32")

    # compute the perspective transform matrix and then apply it
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))

    # return the warped image
    return warped

def order_points(pts):
    # initialzie a list of coordinates that will be ordered
    # such that the first entry in the list is the top-left,
    # the second entry is the top-right, the third is the
    # bottom-right, and the fourth is the bottom-left
    rect = np.zeros((4, 2), dtype = "float32")

    # the top-left point will have the smallest sum, whereas
    # the bottom-right point will have the largest sum
    s = pts.sum(axis = 1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    # now, compute the difference between the points, the
    # top-right point will have the smallest difference,
    # whereas the bottom-left will have the largest difference
    diff = np.diff(pts, axis = 1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    # return the ordered coordinates
    return rect

# compute and retrn the distance from the maker to the camera
def distance_to_camera(knownWidth, focalLength, perWidth):
    return (knownWidth * focalLength) / perWidth

# calibrate
objects = identify_objects('image/12ft.jpg')
known_dist = 12
w,h = objects[0][1]
print "Focal length at", known_dist, "feet is", w, "px"
print objects

#for i in [2,3,4,6,8,10,12,'6-rot']:
for i in [12]:
    #get_contours(src, str(i) + '.jpg')
    src = 'image/' + str(i) + 'ft.jpg'
    out = "out/" + str(i) + '.jpg'
    print "locating", i
    locate_xyz(src, (w, known_dist), out)

