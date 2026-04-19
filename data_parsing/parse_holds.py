'''
Detect all the circles (the location of the holds!) in the image
'''
import cv2
import numpy as np

def get_hold_locations(image):
    
    cv2.imshow("full color image", image) # you can uncomment these two lines to visualize the holds that are detected for the given image and color
    cv2.waitKey()

    colored_hold_locations = {'Green': [], 'Teal': [], 'Magenta': [], 'Orange': []}

    color_selector = {"Green":[1,0,2],"Teal":[0,1,2],"Magenta":[0,2,1],"Orange":[1,2,0]} # this dictionary is used to tell apart different colors based on the relative rgb pixel values
    for hy in range(1, 39+1): # for all rows with even hold coordinates
        py = round(20.83 * hy - 29.67)
        for hx in range(1, 35+1): # for all columns with even hold coordinates
            px = round(20.83 * hx + 13.33)
            # pixel_location = [px,py]
            # Check if this pixel location has a hold of the specified color
            pixel_rgb = image[py][px]
            for color in color_selector:
                if color == "Green":
                    if (pixel_rgb[color_selector[color][0]] > 200 and pixel_rgb[color_selector[color][1]]<120 and pixel_rgb[color_selector[color][2]]<120): #record the locations of all the holds with a green circle
                        colored_hold_locations[color].append([hx,40-hy]) # we do 40-hy instead of hy so the holds start from the bottom of the board instead of the top
                elif (pixel_rgb[color_selector[color][0]] > 150 and pixel_rgb[color_selector[color][1]] > 200 and pixel_rgb[color_selector[color][2]]<120): #record the locations of all the holds with other colored circles
                    colored_hold_locations[color].append([hx,40-hy]) # we do 40-hy instead of hy so the holds start from the bottom of the board instead of the top
    # Then we return the hold coordinates for all the holds of the given color
    hold_locations = {'Start': colored_hold_locations['Green'], 'Any': colored_hold_locations['Teal'], 'Finish': colored_hold_locations['Magenta'], 'Feet': colored_hold_locations['Orange']}
    return hold_locations

'''
The methods below are easier to follow but they are very slow because of single_color_image = black_all_but_color(color,image)
black_all_but_color(color,image) looks at every pixel in the image that isn't the specified color and makes it black
When the images are large this can take a long time
There is no need to look at every pixel of the image -- we only have to check a small subset of pixels, which will be faster
Checking on the small subset of pixels is implemented above
'''

def get_hold_locations_slow(bottom_image):
    colored_hold_locations = {'Green': [], 'Teal': [], 'Magenta': [], 'Orange': []}
    hold_colors = ['Green','Teal','Magenta','Orange']
    for color in hold_colors: # get the hold location for each of the four colors
        # print(color)
        # print(detect_holds(color,bottom_image))
        image = bottom_image.copy()
        colored_hold_locations[color] = detect_holds_slow(color,image)
        # colored_hold_locations[color] = detect_holds_slow(color,image)
    hold_locations = {'Start': colored_hold_locations['Green'], 'Any': colored_hold_locations['Teal'], 'Finish': colored_hold_locations['Magenta'], 'Feet': colored_hold_locations['Orange']}
    return hold_locations

def detect_holds_slow(color,image):
    single_color_image = black_all_but_color(color,image)
    # cv2.imshow("single_color_image", single_color_image) # you can uncomment these two lines to visualize the holds that are detected for the given image and color
    # cv2.waitKey()
    
    """ 
    We have to find the pixel coordinates of each circle and map it to a hold coordinate
    We can do this by only checking pixels that are 41.67 pixels away from the last value, which is the periodic distance between handholds
    We want to check a predefined set of pixels that may or may not contain a circle of a certain hold color
        First, we want to find out which pixels to check in the image
        We label all the holds by a set of coordinates defined in Hold Coordinates Guide Part 1.jpeg and Hold Coordinates Guide Part 2.jpeg
        Then we identify each hold by using a pixel in the northeast sector of each hold
        We create a mapping between the hold coordinate and the pixel coordinate below
            (2,2) <-> (whole image (55,412)) <-> bottom image (55,12)
            (2,38) <-> (whole image (55,1162)) <-> bottom image (55,762)
            (34,38) <-> (whole image (722,1162)) <-> bottom image (722,762)
            (hx,hy) <-> (px,py) (note that pixel and hold values must be integers)
            px = round(a * hx + bx), a = 41.67/2 = 20.83 (empirically determined)
            bx = 13.33
            py = round(a * hy + by), a = 41.67/2 = 20.83 (empirically determined)
            by = -29.67
        Thus, px = round(20.83 * hx + 13.33), py = round(20.83 * hy - 29.67)
    We can use the mapping between the hold coordinate and the pixel coordinate to determine which set of pixels to check for holds
    The set of pixels to check for holds will just be a nested array of coordinates, where each coordinate is [px,py]"""

    hold_locations = []
    for hy in range(1, 39+1): # for all rows with even hold coordinates
        py = round(20.83 * hy - 29.67)
        for hx in range(1, 35+1): # for all columns with even hold coordinates
            px = round(20.83 * hx + 13.33)
            # pixel_location = [px,py]
            # Check if this pixel location has a hold
            if (image[py][px] != [0,0,0]).all():
                hold_locations.append([hx,hy])
    # Then we return the hold coordinates for all the holds of the given color
    return hold_locations

def black_all_but_color(color,image):
    # NOTE: The pixel is actually a BGR pixel, so the first pixel value is blue, second is green, and third is red
    if color.lower() == "green": # if the color is green, then only the second pixel value is over 200
        high_g = 1
        low_r = 0
        low_b = 2
    if color.lower() == "teal" or color.lower() == "blue": # if the color is teal, then the first and second pixel values match
        match1 = 0
        match2 = 1
        other = 2
    if color.lower() == "magenta" or color.lower() == "purple": # if the color is magenta, then the first and third pixel values match
        match1 = 0
        match2 = 2
        other = 1
    if color.lower() == "orange": # if the color is orange, then the second and third pixel values match
        match1 = 1
        match2 = 2
        other = 0
    height = len(image)
    width = len(image[0])
    for y in range(height):
        for x in range(width):
            pixel_rgb = image[y][x]
            if color.lower() == "green":
                if not (pixel_rgb[high_g] > 200 and pixel_rgb[low_r]<120 and pixel_rgb[low_b]<120): #make any thing that isn't green into black
                    image[y][x] = [0,0,0]
            elif not (pixel_rgb[match1] > 150 and pixel_rgb[match2] > 200 and pixel_rgb[other]<120): #make any thing that isn't the specified color into black
                image[y][x] = [0,0,0]
    single_color_image = image
    return single_color_image

"Here we have some code that we aren't using right now, since there is an easier way to detect holds than circle detection."

# This function is incomplete and presently unused because a more straightforward method is used
# Only keeping it until I test the other method works (although the other method may not be as robust as this)
# If the interface changes, we may will consider using this method instead
# def detect_circles(color,image):
#     # Read image.
#     img = cv2.imread('eyes.jpg', cv2.IMREAD_COLOR)
    
#     # Convert to grayscale.
#     gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
#     # Blur using 3 * 3 kernel.
#     gray_blurred = cv2.blur(gray, (3, 3))
    
#     # Apply Hough transform on the blurred image.
#     detected_circles = cv2.HoughCircles(gray_blurred, 
#                     cv2.HOUGH_GRADIENT, 1, 20, param1 = 50,
#                 param2 = 30, minRadius = 1, maxRadius = 40)
    
#     # Draw circles that are detected.
#     if detected_circles is not None:
    
#         # Convert the circle parameters a, b and r to integers.
#         detected_circles = np.uint16(np.around(detected_circles))
    
#         for pt in detected_circles[0, :]:
#             a, b, r = pt[0], pt[1], pt[2]
    
#             # Draw the circumference of the circle.
#             cv2.circle(img, (a, b), r, (0, 255, 0), 2)
    
#             # Draw a small circle (of radius 1) to show the center.
#             cv2.circle(img, (a, b), 1, (0, 0, 255), 3)
#             cv2.imshow("Detected Circle", img)
#             cv2.waitKey(0)

"Below we have some code we can use if we run this file, to test that these methods work as expected."

if __name__ == "__main__":
    # below is an example of how to use the parse_holds functions to get holds coordinates for different colors
    # press any key to advance -- if you don't press any key you won't see any output

    import os
    screenshots_paths = []
    screenshots_dir_path = os.getcwd() + '/test_images'
    # screenshots_dir_path = os.getcwd() + '/kilter_climbs_output'

    # iterate through the names of contents of the folder
    for image_path in os.listdir(screenshots_dir_path):
        # create the full input path and read the file
        screenshots_paths.append(os.path.join(screenshots_dir_path, image_path))
    # print(screenshots_paths)
    for climb_screenshot in screenshots_paths:
        climb_image = cv2.imread(climb_screenshot)
        bottom_image = climb_image[400:-100, :]

        # cv2.imshow("bottom image", bottom_image)
        # cv2.waitKey()
        # single_color_image = black_all_but_color("Teal",bottom_image)
        # cv2.imshow("single color image", single_color_image)
        # cv2.waitKey()
        # print(detect_holds_slow("Teal",bottom_image))

        print(get_hold_locations(bottom_image))
        # print(get_hold_locations_slow(bottom_image))