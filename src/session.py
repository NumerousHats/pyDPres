from sqlalchemy.orm import sessionmaker

Session = sessionmaker()


class DuplicateIngestError(Exception):
    pass

