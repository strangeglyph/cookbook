class LoadException(Exception):
    def __init__(self, msg: str):
        super(LoadException, self).__init__(msg)
        self.context = []
        self.cause = None

    def add_note(self, msg: str):
        self.context.append(msg)

    def add_cause(self, cause: Exception):
        self.cause = cause
