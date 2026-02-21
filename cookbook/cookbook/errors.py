class LoadException(Exception):
    def __init__(self, msg: str):
        super(LoadException, self).__init__(msg)
