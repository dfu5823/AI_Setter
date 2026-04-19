import math

from .AbstractSetter import AbstractSetter
from .generators import EmpiricalSequentialSetter


class SequentialSetter(AbstractSetter):
    def __init__(self, input_data=None):
        self.model = EmpiricalSequentialSetter(input_data)

    def get_hold_distance(self, hold1, hold2):
        return math.sqrt((hold2[0] - hold1[0]) ** 2 + (hold2[1] - hold1[1]) ** 2)

    def train(self, input_data):
        self.model.train(input_data)
        return self.model.transitions

    def create(self, number_of_climbs=1, grade="V5", creativity_level=0.5):
        return [
            self.model.create(grade=grade, options={"hand_count": max(5, round(7 + 4 * creativity_level))})
            for _ in range(number_of_climbs)
        ]
