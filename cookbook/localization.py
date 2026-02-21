import os
from ruamel.yaml import YAML

from .common import get_data_path

yaml = YAML()

LOC_FILES = {}
for file in os.listdir(get_data_path("localization")):
    if os.path.splitext(file)[1] == '.yml':
        lang = os.path.splitext(file)[0]
        print(f"Loading localization file for {lang}")
        loc_file_path = os.path.join(get_data_path("localization"), file)
        with open(loc_file_path) as loc_file:
            LOC_FILES[lang] = yaml.load(loc_file)

def is_localized(loc_id: str, lang: str):
    return lang in LOC_FILES and loc_id in LOC_FILES[lang]

def localize(loc_id: str, lang: str):
    if is_localized(loc_id, lang):
        return LOC_FILES[lang][loc_id]

    return loc_id