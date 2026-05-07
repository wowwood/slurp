import json
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from slurp.db import db


class BaseModel(db.Model):
    """
    Base model
    """

    __abstract__ = True
    # Ordinarily I prefer UUIDs for all objects, but as we want SQLite we'll keep it simple and go auto-increment.
    id: Mapped[int] = mapped_column(primary_key=True)
    ts_created: Mapped[datetime] = mapped_column(
        default=datetime.now(timezone.utc), server_default=func.now(), nullable=False
    )
    ts_updated: Mapped[datetime] = mapped_column(
        default=datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    @classmethod
    def first_by(cls, **kwargs):
        """
        Get first entity that matches to criterion
        """
        return cls.query.filter_by(**kwargs).first()

    @classmethod
    def first(cls, *criterion):
        """
        Get first entity that matches to criterion
        """
        return cls.query.filter(*criterion).first()

    @classmethod
    def exists(cls, *criterion) -> bool:
        """
        Check if entry with criterion exists
        """
        return cls.query.filter(*criterion).scalar()

    @classmethod
    def get(cls, _id: int):
        """
        Get the entity that matches the id
        """
        return cls.query.get(_id)
