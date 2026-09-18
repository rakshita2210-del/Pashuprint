"""
database.py
------------
This file sets up the connection to our SQLite database using SQLAlchemy.

Think of this file as the "plumbing" that connects our Python code to the
actual database file on disk (pashuprint.db).

Other files (models.py, crud.py, routers/*) import from here to talk to the DB.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLite database file will be created in the same folder as this file.
# The "check_same_thread" flag is needed only for SQLite when used with FastAPI,
# because FastAPI can use multiple threads to handle requests.
SQLALCHEMY_DATABASE_URL = "sqlite:///./pashuprint.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# SessionLocal is a factory for creating new database sessions.
# A "session" is basically a temporary workspace for talking to the DB.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base is the class that all our database models (tables) will inherit from.
Base = declarative_base()


def get_db():
    """
    This function creates a new database session for each request,
    and makes sure it is closed afterwards (even if an error happens).

    FastAPI will call this automatically wherever we use `Depends(get_db)`.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
