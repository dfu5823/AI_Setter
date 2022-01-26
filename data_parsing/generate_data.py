import cv2
import numpy as np

from parse_text import get_climb_description
from parse_holds import get_hold_locations

def generate_data(climb_screenshots,data_type=1):
    climbs_data = []
    for climb_screenshot in climb_screenshots:
        one_climb_data = {'Climb Description': [], 'Hold Locations': []}
        climb_image = cv2.imread(climb_screenshot)
        top_image, bottom_image = split_image(climb_image)
        one_climb_data['Climb Description'] = get_climb_description(climb_screenshot) # We pass in the path to the screenshot file (not an opencv image) so ocr.space can process it
        one_climb_data['Hold Locations'] = get_hold_locations(bottom_image)
        climbs_data.append(one_climb_data)
    return climbs_data

def split_image(climb_image):
    top_image = climb_image[30:300, :]
    bottom_image = climb_image[400:-100, :]
    return top_image, bottom_image

"Below we have some code we can use if we run this file, to test that these methods work as expected."

if __name__ == "__main__":
    import os
    screenshots_paths = []
    screenshots_dir_path = os.getcwd() + '/test_images'

    # iterate through the names of contents of the folder
    for image_path in os.listdir(screenshots_dir_path):
        # create the full input path and read the file
        screenshots_paths.append(os.path.join(screenshots_dir_path, image_path))
    print(generate_data(screenshots_paths))
    # for climb_screenshot in screenshots_paths:
    #     climb_image = cv2.imread(climb_screenshot)
    #     # cv2.imshow("original", climb_image)
    #     # cv2.waitKey()
    #     # print(tuple(climb_image.shape[1::-1]))
    #     top_image, bottom_image = split_image(climb_image)
    #     # cv2.imshow("original", top_image)
    #     # cv2.waitKey()
    #     # cv2.imshow("original", bottom_image)
    #     # cv2.waitKey()
    #     print(get_hold_locations(bottom_image))
    #     print(get_climb_description(climb_screenshot))
