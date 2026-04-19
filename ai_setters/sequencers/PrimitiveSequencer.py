 def get_primitive_sequence():
        #   Note that this sequence selector clearly doesn't account for bumping or matching or crossing
        # first, only consider the hand holds - no feet
        # consider the holds as a list of unordered holds we want to order
        # eg. [(2,0)(start=0),(3,1)(middle=1),(1,2)(middle=1),(3,3)(middle=1),(4,2)(finish=2)] 
        # 4       f
        # 3          m
        # 2       m        for this sequence you can see that the correct sequence is
        # 1          m     [(2,0)(start=0),(3,1)(middle=1),(2,2)(middle=1),(3,3)(middle=1),(4,2)(finish=2)]
        # 0       s
        #   0  1  2  3  4
        # A. if there is one starting hold
        #   1. the next hold is the nearest neighbor
        #   2. the hold is right hand if it is to the right of the start, left hand if to the left
        # B. if there are two starting holds
        #   1. the next hold is the nearest neighbor to the pair of holds
        #   2. 
        pass
