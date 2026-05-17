from datetime import datetime, timezone

from redis_om import JsonModel

from slurp import db


class BaseModel(JsonModel):
    """
    Base model
    """

    ts_created: datetime = datetime.now(timezone.utc)
    ts_updated: datetime = datetime.now(timezone.utc)

    def save(self, **kwargs):
        self.ts_updated = datetime.now(timezone.utc)
        super().save(**kwargs)

    class Meta:
        database = db.redis
