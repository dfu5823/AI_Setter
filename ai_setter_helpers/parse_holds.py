'''
Detect all the circles (the location of the holds!) in the image
'''
import cv2
import numpy as np

def get_hold_locations(bottom_image):
    hold_locations = {'Green': [], 'Teal': [], 'Magenta': [], 'Orange': []}
    hold_locations['Green'] = detect_holds(color='green',image=bottom_image)
    hold_locations['Teal'] = detect_holds(color='teal',image=bottom_image)
    hold_locations['Magenta'] = detect_holds(color='magenta',image=bottom_image)
    hold_locations['Orange'] = detect_holds(color='orange',image=bottom_image)

    pass

def detect_holds(color,image):
    single_color_image = black_all_but_color(color,image)
    pass

def black_all_but_color(color,image):
    # NOTE: The pixel is actually a BGR pixel, so the first pixel value is blue, second is green, and third is red
    if color == "green": # if the color is green, then only the second pixel value is over 200
        low_r = 0
        high_g = 1
        low_b = 2
    if color == "teal": # if the color is teal, then the first and second pixel values match
        match1 = 0
        match2 = 1
        other = 2
    if color == "magenta": # if the color is magenta, then the first and third pixel values match
        match1 = 0
        match2 = 2
        other = 1
    if color == "orange": # if the color is orange, then the second and third pixel values match
        match1 = 1
        match2 = 2
        other = 0
    height = len(image)
    width = len(image[0])
    for y in range(height):
        for x in range(width):
            pixel_rgb = image[y][x]
            if color == "green":
                if not (pixel_rgb[high_g] > 200 and pixel_rgb[low_r]<120 and pixel_rgb[low_b]<120): #make any thing that isn't green into black
                    image[y][x] = [0,0,0]
            elif not (pixel_rgb[match1] > 150 and pixel_rgb[match2] > 200 and pixel_rgb[other]<120): #make any thing that isn't the specified color into black
                image[y][x] = [0,0,0]
    single_color_image = image
    return single_color_image

# This function is incomplete and presently unused because a more straightforward method is used
# Only keeping it until I test the other method works (although the other method may not be as robust as this)
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

if __name__ == "__main__":
    import os
    screenshots_paths = []
    screenshots_dir_path = os.getcwd() + '/test_images'

    # iterate through the names of contents of the folder
    for image_path in os.listdir(screenshots_dir_path):
        # create the full input path and read the file
        screenshots_paths.append(os.path.join(screenshots_dir_path, image_path))
    for climb_screenshot in screenshots_paths:
        climb_image = cv2.imread(climb_screenshot)
        # bottom_image = climb_image[400:442 , :]
        bottom_image = climb_image[400:-100, :]

        cv2.imshow("bottom image", bottom_image)
        cv2.waitKey()
        single_color_image = black_all_but_color("orange",bottom_image)
        cv2.imshow("single color image", single_color_image)
        cv2.waitKey()