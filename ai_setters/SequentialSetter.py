from .AbstractSetter import AbstractSetter
from.sequencers.NearestNeighborSequencer import NearestNeighborSequencer
import math
class SequentialSetter(AbstractSetter):
    def __init__():
        pass

    def get_hold_distance(hold1,hold2):
        # distance = sqrt( (x2-x1)^2 + (y2-y1)^2 )
        return math.sqrt( (hold2[0]-hold1[0])**2 + (hold2[1]-hold1[1])**2 )

    nn_sequencer = NearestNeighborSequencer()
    nearest_neighbor_sequence = nn_sequencer.get_nearest_neighbor_sequence()

    
    def train(input_data):

        pass
        # first use a simple heuristic to determine the sequence of holds in the climb
        # (MAKE SURE to visualize this sequence of holds for a few dozen examples minimum so we know its limitations)
        # then for each hold OR pair of holds (maybe sequential_setter_2?) make an empirical distribution of the next hold over all climbs
        # that means that for every hold in the dataset, we should have a list of all the next holds that are possible from that hold
        # empirical_sequence_distributions = [next_holds1, next_holds2, ... next_holdsn]
        # next_holdsi = [hold1,hold2,...holdn]
        # holdi = [hx,hy]
        # (MAKE SURE to visualize what empirical_sequence_distributions looks like. For instance, a heat map showing the number of next_holds each hold has, in a grid)

        # return empirical_sequence_distributions