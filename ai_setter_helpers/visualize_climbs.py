import os
from scipy import misc

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
    pass