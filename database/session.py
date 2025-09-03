import enum
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


class Environment(str, enum.Enum):
    dev = "dev"
    prod = "prod"


APP_ENV = os.getenv("APP_ENV", Environment.dev)

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
os.makedirs(DB_DIR, exist_ok=True)

DB_FILENAME = f"app_{APP_ENV}.db"
DATABASE_URL = f"sqlite:///{os.path.join(DB_DIR, DB_FILENAME)}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
