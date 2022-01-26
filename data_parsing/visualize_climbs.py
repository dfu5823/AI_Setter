import os
from scipy import misc
import cv2

def visualize_climbs(climbs,climb_type='Kilter'):
    #eg. sequential_setter_climbs = [ {'Name':"My First Climb",'Grade':"6c+/V5",'Holds':{'Start':[[1,2],[3,4]]} } , {'Name':"My Second Climb",'Grade':"7c+/V10",'Holds':{'Start':[[1,2],[7,8]]} } ]
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
    #eg. sequential_setter_climbs[0] = {'Name':"My First Climb",'Grade':"6c+/V5",'Holds':{'Start': [[2, 8]], 'Any': [[2, 34]], 'Finish': [[1, 5], [5, 5]], 'Feet': [[1, 33], [5, 33]]} }

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
        if key == "Green": color = (80,210,)
        if key == "Teal": color = (250,250,0)
        if key == "Magenta": color = (250,0,250)
        if key == "Orange": color = (0,160,250)
        for hold in colored_hold_locations[key]:
            hx = hold[0]; hy = hold[1]
            pcx = round(20.8 * hx + 11.2 - 10.5); pcy = 1136 -  round(20.8 * hy - 27.8 + 10.5) # 20.8 is approximately the distance between holds in pixels, 10.5 is approxiamtely half the radius of the circle, then the pixels are shifted to match the image and the y pixels are flipped to fit cv2 conventions
            # for each hold in climb_holds draw a circle on the appropriate coordinate
            # draw a circle with the center at (pcx,pcy), color given by key, and radius 21, on top of output_image
            cv2.circle(img=output_image, center=(pcx,pcy), radius=21, color=color, thickness=3)

    
    output_image = add_centered_text(output_image,'AI Setter',70,relative_font_size=2)
    # angle = 50; output_image = add_centered_text(output_image,f'{angle}º'+u'\N{DEGREE SIGN}',110,color=(255,50,0)) # TODO: degree sign is broken
    output_image = add_centered_text(output_image,'By: Dan Fu',110,color=(150,50,0)) # TODO: degree sign is broken
    output_image = add_centered_text(output_image,f'{climb_name}',160)
    output_image = add_centered_text(output_image,f'{climb_grade}',190,relative_font_size=0.7)


    cv2.imshow(f"{climb_name}", output_image)
    cv2.waitKey()

    return climb_name

def add_centered_text(image,text,ypos,font_type=cv2.FONT_HERSHEY_SIMPLEX,relative_font_size=1,color=(255,255,255),thickness=2):
    textsize = cv2.getTextSize(text, font_type, relative_font_size, thickness)[0]
    textX=int((image.shape[1] - textsize[0]) / 2)
    output_image = cv2.putText(
        image, 
        text, 
        org=(textX,ypos), 
        fontFace=font_type, 
        fontScale=relative_font_size, 
        color=color, 
        thickness=thickness)
    return output_image

if __name__ == "__main__":
    climb_example = {'Name':"Hello World",'Grade':"6c+/V5",
    'Holds':{
        'Start': [[34, 10]], 
        'Any': [[18, 34], [18, 28], 
        [20, 28], [26, 26], [24, 24], 
        [30, 18], [26, 16]], 
        'Finish': [[22, 38]], 
        'Feet': [[21, 21], [17, 17], 
        [20, 10], [27, 1], [35, 1]]} 
        }

    visualize_one(climb_example)
