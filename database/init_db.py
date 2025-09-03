import logging

from . import models  # noqa: F401  # ensure models imported
from .session import engine, Base


def init_db():
    logging.info("init_db: Creating database tables if they do not exist...")
    Base.metadata.create_all(bind=engine)


