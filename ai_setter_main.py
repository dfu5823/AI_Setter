# Here is the AI Setter!
# Training Data: All the climbs with above n repeats currently available on the Kilterboard App!
# Input: Optional parameters such as: Boulder difficulty, reachiness factor, hold type(s)
# Output: Brand new, auto-generated kilterboard climbs matching to the input parameters

from ai_setter_helpers.generate_data import generate_data
from ai_setter_helpers.visualize_climbs import visualize_climbs
from ai_setters.sequential_setter import SequentialSetter
import kilter_climbs_data as screenshots

'''
Step 1: Get the training data
Quick and Dirty Idea: 
    1. take a screenshot of every single relevant climb on the app. Should be a few thousand. Do this for one angle
        - I just started with 150 screenshots for now
    2. Write an OpenCV method that reads the image and translates the image of the holds into training data
        - Using OpenCV to idenitfy the holds and OCR.Space to read the text description (including name and grade)
    3. Make different versions of training data
        example 1: list of all the holds, unlabeled [(5,10), (7,12), (5,15), ...]
        example 2: dictionary of all the holds, labeled {start:[(1,2),(1,7)],finish:[...],feet:[...],hands:[...]}
    4. Add to the hold location data the other relevant information, aka features, including:
        climbing grade, board angle, star rating, number of ascents
Better Idea which we can't do because the Kilter Board developper is busy:
    1. access the Kilter Board API and request all climbs, which will return all of the raw training data
    2. Process the training data to make version1 and version2
    3. Filter out the climbs below n repeats, say n=20. We want n as low as possible without including too much choss.

In general it is a good idea to try many different training datasets. 
We can start with n=20, unlabeled holds, and climbing grade only, for simplicity.
Then we can try more featured training datasets with n<20, labeled holds, all relevant features
'''
print(screenshots[0])

climbdata1 = generate_data(climb_screenshots=screenshots,data_type=1)
climbdata2 = generate_data(climb_screenshots=screenshots,data_type=2)

'''
Step 2: Choose and implement a (few) generative model(s), then train the model(s) on the training data
'''
sequential_setter = SequentialSetter()
sequential_setter.train(input_data = climbdata1)

'''
Step 3: Generate some climbs!
'''
sequential_setter_climbs = sequential_setter.create(number_of_climbs = 10, grade = "V5", creativity_level = 0.5)
#eg. sequential_setter_climbs = {[{Name:"My First Climb",Grade:"6c+/V5",Holds:[[1,2],[3,4]]},{Name:"My Second Climb",Grade:"7c+/V10",Holds:[[1,2],[7,8]]}]}
'''
Step 4: Show off the climbs to your friends :)
'''
visualize_climbs(sequential_setter_climbs)