import cv2
import numpy as np



from parse_text import get_climb_description
from parse_holds import get_hold_locations

def generate_data(climb_screenshots,data_type=1):
    climb_data = {'Climb Description': [], 'Hold Locations': []}
    for climb_screenshot in climb_screenshots:
        climb_image = cv2.imread(climb_screenshot)
        top_image, bottom_image = split_image(climb_image)
        climb_data['Climb Description'] = get_climb_description(top_image)
        climb_data['Hold Locations'] = get_hold_locations(bottom_image)
    pass

def split_image(climb_image):
    top_image = climb_image[30:300, :]
    bottom_image = climb_image[400:, :]
    return top_image, bottom_image

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
        cv2.imshow("original", climb_image)
        cv2.waitKey()
        print(tuple(climb_image.shape[1::-1]))
        top_image, bottom_image = split_image(climb_image)
        print(tuple(top_image.shape[1::-1]))
        cv2.imshow("original", top_image)
        cv2.waitKey()
        cv2.imshow("original", bottom_image)
        cv2.waitKey()
