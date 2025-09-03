from . import models  # noqa: F401  # ensure models imported
from .session import engine, Base


def init_db():
    Base.metadata.create_all(bind=engine)


