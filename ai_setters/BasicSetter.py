from .AbstractSetter import AbstractSetter
class BasicSetter(AbstractSetter):
    def __init__():
        pass
    def train(input_data):
        pass
        # first use a simple heuristic to determine the sequence of holds in the climb
        # (MAKE SURE to visualize this sequence of holds for a few dozen examples minimum so we know its limitations)
        # find the position difference vector between holds that are adjacent in sequence
        
        # make a distribution of the distance vectors for each grade called dist_vecs
        # also make a distribution of the starting hold row and starting hold column called start_pos
        # also make a bernoulli distirbution with p = two_hand_start probability and 1-p = match_start probablity called num_holds

    def create(number_of_climbs, grade, creativity_level):
        # 
        pass