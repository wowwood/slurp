from flask_redis import FlaskRedis
from redis_om import Migrator

redis = FlaskRedis()


def bind_redis(app):
    redis.init_app(app)

    # Migrate database.
    Migrator().run()
