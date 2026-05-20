from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass

class UserProfile(Base):
    __tablename__ = "user_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        index=True,
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(String(255))
    gender: Mapped[str] = mapped_column(String(1))
    age: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    weight: Mapped[float] = mapped_column(Float)
    activity: Mapped[str] = mapped_column(String(50))
    target: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now
    )
    food_logs: Mapped[list["FoodLog"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

class FoodLog(Base):
    __tablename__ = "food_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_profile.id"),
        nullable=False,
        index=True,
    )
    food_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    weight: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0
    )
    kcal: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0
    )
    protein: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0
    )
    fat: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0
    )
    carbs: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0
    )
    source: Mapped[str] = mapped_column(
        String(20),
        default="photo"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        index=True
    )
    user: Mapped["UserProfile"] = relationship(
        back_populates="food_logs",
    )