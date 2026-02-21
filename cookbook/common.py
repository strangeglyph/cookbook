import os


def get_data_path(relpath: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relpath)