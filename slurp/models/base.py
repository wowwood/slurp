from datetime import datetime, timezone

from redis_om import Field, JsonModel

from slurp import db


class BaseModel(JsonModel):
    """
    Base model
    """

    ts_created: datetime = Field(sortable=True, default=datetime.now(timezone.utc))
    ts_updated: datetime = Field(sortable=True, default=datetime.now(timezone.utc))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ts_created = datetime.now(timezone.utc)

    def save(self, **kwargs):
        self.ts_updated = datetime.now(timezone.utc)
        super().save(**kwargs)

    class Meta:
        database = db.redis
