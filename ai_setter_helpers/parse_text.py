import requests

def get_climb_description(climb_screenshot):
    extracted_text = ocr_space_file(climb_screenshot)
    print(extracted_text)
    return None

def ocr_space_file(filename, overlay=False, api_key='49064c626d88957', language='eng'):
    """ OCR.space API request with local file.
        Python3.5 - not tested on 2.7
    :param filename: Your file path & name.
    :param overlay: Is OCR.space overlay required in your response.
                    Defaults to False.
    :param api_key: OCR.space API key.
                    Defaults to 'helloworld'.
    :param language: Language code to be used in OCR.
                    List of available language codes can be found on https://ocr.space/OCRAPI
                    Defaults to 'en'.
    :return: Result in JSON format.
    """

    payload = {'isOverlayRequired': overlay,
               'apikey': api_key,
               'language': language,
               }
    with open(filename, 'rb') as f:
        r = requests.post('https://api.ocr.space/parse/image',
                          files={filename: f},
                          data=payload,
                          )
    return r.content.decode()

# Use examples:
# test_file = ocr_space_file(filename='example_image.png', language='eng')

if __name__ == "__main__":
    import os
    screenshots_paths = []
    screenshots_dir_path = os.getcwd() + '/test_images'

    # iterate through the names of contents of the folder
    for image_path in os.listdir(screenshots_dir_path):
        # create the full input path and read the file
        screenshots_paths.append(os.path.join(screenshots_dir_path, image_path))
    for climb_screenshot in screenshots_paths:
        print(get_climb_description(climb_screenshot))