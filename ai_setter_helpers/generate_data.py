from .parse_text import get_climb_description
from .parse_holds import get_hold_locations

def generate_data(climb_screenshots,data_type=1):
    climb_data = {'Climb Description': [], 'Hold Locations': []}
    for climb_screenshot in climb_screenshots:
        top_image, bottom_image = split_image(climb_screenshot)
        climb_data['Climb Description'] = get_climb_description(top_image)
        climb_data['Hold Locations'] = get_hold_locations(bottom_image)
    pass

def split_image(climb_screenshot):
    pass