from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from db.database import SessionLocal
from db.models import UserProfile

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
