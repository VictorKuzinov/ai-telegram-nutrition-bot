from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError

from db.database import SessionLocal
from db.models import UserProfile, FoodLog


def create_user_profile(data: dict) -> UserProfile:
    """
    Функция создания профиля
    :return: UserProfile
    """
    session = SessionLocal()

    try:
        user = UserProfile(**data)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()


def get_user_profile(telegram_id: int) -> UserProfile | None:
    """
    Функция получения профиля
    :return: UserProfile
    """
    session = SessionLocal()
    try:
        result = select(UserProfile).where(UserProfile.telegram_id == telegram_id)
        user = session.execute(result).scalars().first()
        return user
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()

def update_user_profile(
        telegram_id: int,
        updates: dict,
) -> UserProfile | None:
    """
    Функция обновления профиля
    :return: UserProfile
    """
    session = SessionLocal()
    try:
        result = select(UserProfile).where(UserProfile.telegram_id == telegram_id)
        user = session.execute(result).scalars().first()
        if not user:
            return None
        for key, value in updates.items():
            if hasattr(user, key):
                setattr(user, key, value)
        session.commit()
        session.refresh(user)
        return user
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()

def create_food_log(data: dict) -> FoodLog:
    session = SessionLocal()

    try:
        food = FoodLog(**data)
        session.add(food)
        session.commit()
        session.refresh(food)
        return food
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()

def get_today_food_logs(telegram_id: int):
    session = SessionLocal()
    try:
        profile = get_user_profile(telegram_id=telegram_id)
        if profile is None:
            return []

        start_of_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_next_day = start_of_day + timedelta(days=1)

        result = (
            select(FoodLog)
            .where(FoodLog.user_id == profile.id)
            .where(FoodLog.created_at >= start_of_day)
            .where(FoodLog.created_at < start_next_day)
        )
        foods = session.execute(result).scalars().all()
        return foods
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()

def get_food_logs_for_period(telegram_id, days=7) -> list:
    session = SessionLocal()
    try:
        profile = get_user_profile(telegram_id=telegram_id)
        if profile is None:
            return []

        start_period = datetime.now() - timedelta(days=days)

        result = (
            select(
                func.strftime('%d.%m.%Y', FoodLog.created_at).label("date"),
                func.sum(FoodLog.kcal).label("total_kcal")
            )
            .where(FoodLog.user_id == profile.id)
            .where(FoodLog.created_at >= start_period)
            .group_by(func.date(FoodLog.created_at))
            .order_by(func.date(FoodLog.created_at).desc())
        )
        foods  = session.execute(result).all()
        return foods
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()