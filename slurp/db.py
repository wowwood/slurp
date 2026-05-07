from sqlmodel import SQLModel, create_engine

from slurp.models.task import FetchTask

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url)


def create_db_and_tables():
    # Scrappily make database tables - to be replaced with proper migrations Soon (tm)
    SQLModel.metadata.create_all(engine)
