import os
from scipy import misc
import cv2

def visualize_climbs(climbs,climb_type='Kilter'):
    if climb_type == 'Kilter':
        kilter_climbs = []
        climb_count = 1
        outPath = os.cwd() + '/kilter_climbs_output'
        for climb in climbs:
            kilter_climbs.append(visualize_one(climb))

            fullpath = os.path.join(outPath, f'climb{climb_count}.png')
            misc.imsave(fullpath, climb)
            climb_count = climb_count + 1
    
    return kilter_climbs

def visualize_one(climb):
    #eg. sequential_setter_climbs = {[{Name:"My First Climb",Grade:"6c+/V5",Holds:[[1,2],[3,4]]},{Name:"My Second Climb",Grade:"7c+/V10",Holds:[[1,2],[7,8]]}]}
    climb_name = climb["Name"]
    climb_grade = climb["Grade"]
    climb_holds = climb["Holds"]
    # take each of these parameters and translate them into a drawing on the image

    screenshots_paths = []
    screenshots_dir_path = os.getcwd() + '/kilter_climbs_output'
    # locate the template image which we will draw holds and name and grade on top of
    output_template = (os.path.join(screenshots_dir_path, 'output_template.png'))

    #make a copy of the output template to draw on so we don't overwrite the original
    output_image = cv2.imread(output_template).copy()

    # TODO: First add the climb name and grade to the image, centered and near the top.
    # make sure to add Set by: AISetter (SeqS)

    # Next add circles indicating where all the holds are:

    hold_locations = climb_holds
    colored_hold_locations = {'Green': hold_locations['Start'], 'Teal': hold_locations['Any'], 'Magenta': hold_locations['Finish'], 'Orange': hold_locations['Feet']}

    ''' To see the math for these linear equations for pcx and pcy, see the comments at the bottom of this file'''
    for key in colored_hold_locations.keys():
        for hold in colored_hold_locations[key]:
            hx = hold[0]; hy = hold[1]
            pcx = round(20.83 * hx + 2.92); pcy = round(20.83 * hy - 40.08) + 335 # add 335 pixels because pcx and pcy were computed using bottom half of image instead of full image
            # for each hold in climb_holds draw a circle on the appropriate coordinate
            # draw a circle with the center at (pcx,pcy), color given by key, and radius 10, on top of output_image

    cv2.imshow("output template image", output_image)
    cv2.waitKey()

    return climb_name

        
    ''' In parse_holds.py there is some code that converts pixel coordinates of a bottom half image (400:) to hold coordinates
    We want to make the reverse of this -- take hold coordinates and convert them to circle centers in a full image, then shift
    all the hold circles so they are aligned with the holds correctly

    We will test with (2,2), (2,38), (34,38), which will correspond to top left, bottom left, and bottom right corner holds
    
    First we will transfer over some math we were using in parse_holds.py:
    Let us ignore that we are using a bottom half image and worry about the vertical shift at the end. Luckily there is no horizontal shift and no scaling.

    (2,2) <-> (whole image (55,412)) <-> bottom image (55,12)
    (2,38) <-> (whole image (55,1162)) <-> bottom image (55,762)
    (34,38) <-> (whole image (722,1162)) <-> bottom image (722,762)

            Let us recall:
            (hx,hy) <-> (px,py) (note that pixel and hold values must be integers)
            px = round(a * hx + bx), a = 41.67/2 = 20.83 (empirically determined)
            bx = 13.33
            py = round(a * hy + by), a = 41.67/2 = 20.83 (empirically determined)
            by = -29.67

    So let's check this formula (you can check for yourself if you want!):
    (2,2) <-> bottom image true (55,12) <-> bottom image calculated (55,12)
    (2,38) <-> bottom image true (55,762) <-> bottom image calculated (55,762)
    (34,38) <-> bottom image true (722,762) <-> bottom image calculated (722,762)

    So the formula checks out! Great. Now lets transform hold coordinates (hx,hy)
    into circle_upper_right_pixels (px,py) into circle_center_pixels (pcx, pcy) into circles of the appropriate colors

    pcx = round(a * hx + bx - a/2) = round(20.83 * hx + 2.92)
    pcy = round(a * hy + by - a/2) = round(20.83 * hy - 40.08)

    Here is an example of the holds: 
    colored_hold_locations = {'Green': [[2,2]], 'Teal': [[2,38]], 'Magenta': [[34,38]], 'Orange': [[16,16],[15,15]]}
    '''