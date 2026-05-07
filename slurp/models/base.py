import json
from datetime import datetime, timezone

from sqlalchemy import TIMESTAMP
from sqlmodel import Field, SQLModel


class BaseModel(SQLModel):
    """
    Base model
    """

    __abstract__ = True
    # Ordinarily I prefer UUIDs for all objects, but as we want SQLite we'll keep it simple and go auto-increment.
    id: int | None = Field(default=None, primary_key=True)
    ts_created: datetime = Field(default=datetime.now(timezone.utc), nullable=False)
    ts_updated: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_column_kwargs={
            "onupdate": lambda: datetime.now(timezone.utc),
        },
        sa_type=TIMESTAMP(timezone=True),
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

    # This must be overridden by derived classes
    def json(self) -> json:
        """
        Get model data in JSON format
        """
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
