from .AbstractSetter import AbstractSetter
from .generators import RandomSetter


class BasicSetter(AbstractSetter):
    def __init__(self, input_data=None):
        self.model = RandomSetter(input_data)

    def train(self, input_data):
        self.model = RandomSetter(input_data)
        return {}

    def create(self, number_of_climbs=1, grade="V5", creativity_level=0.5):
        hand_count = max(5, round(6 + 5 * creativity_level))
        return [self.model.create(grade=grade, options={"hand_count": hand_count}) for _ in range(number_of_climbs)]
