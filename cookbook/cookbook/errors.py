class LoadException(Exception):
    def __init__(self, msg: str):
        super(LoadException, self).__init__(msg)
        self.context = []

    def add_note(self, msg: str):
        self.context.append(msg)
