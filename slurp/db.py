from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_db_and_tables(app):
    # from slurp.models.task import FetchTask

    db.init_app(app)

    # Scrappily make database tables - to be replaced with proper migrations Soon (tm)
    with app.app_context():
        db.create_all()
