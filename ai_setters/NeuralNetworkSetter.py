from .AbstractSetter import AbstractSetter
from .generators import NeuralSetter


class NeuralNetworkSetter(AbstractSetter):
    def __init__(self, input_data=None, checkpoint_path=None):
        self.model = NeuralSetter(input_data, checkpoint_path)

    def train(self, output_path="outputs/models/neural_setter.pt", epochs=None):
        return self.model.train(output_path, epochs=epochs)

    def create(self, number_of_climbs=1, grade="V5", creativity_level=0.5):
        hand_count = max(5, round(6 + 5 * creativity_level))
        return [self.model.create(grade=grade, options={"hand_count": hand_count}) for _ in range(number_of_climbs)]

    def encode(self, climb):
        return self.model.encode(climb)

    def decode(self, tensor, threshold=0.5):
        return self.model.decode(tensor, threshold=threshold)


NeuralNetwork = NeuralNetworkSetter
