class NearestNeighborSequencer():    
    def __init__(self,hand_holds_dict):
        # Note, the NearestNeighborSequencer ignores feet so self.hand_holds does not contain Feet
        hand_holds_locations_type = []
        for hold_location in hand_holds_dict['Start']:
            hold_location_type = hold_location+['start']
            hand_holds_locations_type.append(hold_location_type)
        for hold_location in hand_holds_dict['Any']:
            hold_location_type = hold_location+['middle']
            hand_holds_locations_type.append(hold_location_type)
        for hold_location in hand_holds_dict['Finish']:
            hold_location_type = hold_location+['finish']
            hand_holds_locations_type.append(hold_location_type)
        
        # self.hand_holds_remaining = hand_holds_locations_type
        self.hand_holds_remaining = [[2,0,'start'],[3,1,'middle'],[2,1,'middle'],[3,3,'middle'],[4,2,'finish']]
        self.pair = []
        self.sequence = []
        # self.sequence = [[2,0,'start'],[3,1,'middle'],[2,1,'middle'],[3,3,'middle'],[4,2,'finish']]
        self.pair_distance = []
        self.crossed = False
        self.is_end = False

    def get_nearest_neighbor_sequence(self):
        print(f"Sequencing with {len(self.hand_holds_remaining)} holds left")

    # def get_nearest_neighbor_sequence(hand_holds,pair,sequence,pair_distance,crossed,is_end):
        # this is a recursive function

        # *** let's assume a lateral (x-axis) span of 6 holds (or 12 coordinate steps) (+2 holds if tall?) and a vertical span of 9 (+2 holds if tall?) holds ***
        # we will use climber_span = 6 as a default value but it can be any value (as determined by the climber's actual height)
        # for now let's ignore that you can reach farther vertically (by dynoing) than horizontally and assume span = 12 coordinate steps
        # Note that this sequence selector doesn't account for the true "morphology handedness" (sidepull/undercling) of the holds
        # Also note that this sequence selector does not allow hold recycling to avoid infinite loops
        # TODO: this sequence selector doesn't currently allow for cross hands start
        # TODO: this sequence selector doesn't allow for matching any holds except for the start and finish
        # first, only consider the hand holds - no feet
        # consider the holds as a list of unordered holds we want to order
        # eg. [(2,0)(start=0),(3,1)(middle=1),(1,2)(middle=1),(3,3)(middle=1),(4,2)(finish=2)] 
        # 4       f
        # 3          m
        # 2    m           for this sequence you can see following the rules below that the proposed sequence is
        # 1          m     [(2,0)(start=0)(LR),(3,1)(middle=1)(R),(3,3)(middle=1)(R),(4,2)(finish=2)]
        # 0       s
        #   0  1  2  3  4

        # On the first call of get_nearest_neighbor_sequence, we need to initialize a 

        # Rules for determining next hold and the handedness of that hold
        # Note: firstly, always maintain a pair of holds which indicate which holds the hands are on
        #    0. if the pair contains one finish hold, the next move is to match the other/same finish hold, return final_sequence
        #    1. the next hold is the nearest neighbor to the pair of holds (test all four possibilities)
        #        a. there is always only ONE next hold chosen
        #        b. if there is a tie then choose the lower of the two holds
        #        c. if there is still a tie then choose randomly
        #    2. check if you are crossed (left hand hold is to the right of the right hand)
        #        a. if you are crossed and the next hold is to the L side of the pair, move left hand, if R move R
        #        b. if you are crossed and the next hold is x-wise between the pair, continue below
        #    3. the proposed handedness of the next hold to grab is based on it's x-position relative to its nearest neighbor
        #       we update the proposed pair by "moving the L/R hand to the next hold" and compute the pair distance
        #        a. if the next hold to grab is directly above it's nearest neighbor, 
        #           run a depth-1 search over the next hand positions and select the proposed handedness that prevents crossing
        #    4. if the next hold is equidistant from both holds in the pair, run depth-1 search over the next hand positions
        #       whichever of the pair distances for the depth one search is smaller or results in no crossing if equal, choose that hand and return
        #    5. if the proposed sequence causes the distance between the pair to exceed the span, then
        #        a. try moving the other hand to that hold and if the distance < span, use that sequence
        #        b. if neither hold puts the sequence below the span, choose the sequence with the least pair distance
        #    6. if the next hold is between the left and right hold non-inclusive, run depth-1 search over the next hand positions
        #       whichever pair distance doesn't have crossing is prefered otherwise chose the least pair distance, otherwise random
        #    7. get_nearest_neighbor_sequence(hand_holds,new_pair,new_sequence,new_pair_distance,new_crossed,is_end)

        if self.is_end:
            nearest_neighbor_sequence = self.sequence
            return nearest_neighbor_sequence
        
        #0
        if "finish" in self.pair[0] or self.pair[1]:
            # If our pair contains one finish hold, then next move is to match (either the only or the other finish hold)
            # First we identify the only or the other finish hold as finish_hold_choice
            finish_in_pair = self.pair[0] if "finish" in self.pair[0] else self.pair[1]
            finish_hold_options = []
            for hold in self.hand_holds_remaining:
                if "finish" in hold:
                    finish_hold_options.append(hold)
            finish_hold_choice = finish_in_pair[0:3] if len(finish_hold_options) == 0 else finish_hold_options[0]
            # Then we determine the handedness of that finish hold as the hand not currently on the finish hold in the pair
            # The third element of a hold in the pair is the handedness
            hold_not_on_finish_in_pair = self.pair[0] if not "finish" in self.pair[0] else self.pair[1]
            finish_hold_handedness = hold_not_on_finish_in_pair[3] 
            new_pair = self.update_pair(finish_hold_choice, finish_hold_handedness)
            # new_sequence = update_sequence(old sequence, new hold, new handedness)
            # new_pair_distance = get_pair_distances(old pair, new hold)
            # new_crossed = get_whether_crossed(new_pair)
            self.is_end = True
            # return get_nearest_neighbor_sequence(hand_holds,new_pair,new_sequence,new_pair_distance,new_crossed,is_end)
        
        #TODO:
        #1, #2, #3, etc.
        # edge cases to test:
        # start holds are the finish holds
        # all holds are one start hold and two finish holds
        # all holds are two start holds and one finish hold
        # all holds are two start holds and two finish holds
        # the climb is a traverse
        # all the holds are in a vertical line
        # TO TEST: try wagon lite, richard dugless, we are going to rocklands
        pass

    # Update self.pair moving the hand specified by new_handedness to new_hold
    def update_pair(self, new_hold, new_handedness):
        # Identify the old hand in the pair with the same hand as new_handedness
        for i in range(len(self.pair)):
            if self.pair[i][3] == new_handedness:
                hold_index_to_move = i
        # Move the hand specified by new_handedness to new_hold
        self.pair[hold_index_to_move] = new_hold + [new_handedness]

        return self.pair

if __name__ == "__main__":
    hand_holds = {'Start': [[4, 10], [6, 10]], 'Any': [[14, 32], [16, 24], [12, 22], [4, 20], [10, 14]], 'Finish': [[18, 38]], 'Feet': [[13, 21], [9, 13], [9, 5], [4, 2]]}
    nns = NearestNeighborSequencer(hand_holds)
    print(nns.get_nearest_neighbor_sequence())