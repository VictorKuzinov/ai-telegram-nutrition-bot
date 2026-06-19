from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError

from db.database import SessionLocal
from db.models import UserProfile, FoodLog
from services.review_dishes import normalize_food_log_name


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
        data["food_name"] = normalize_food_log_name(data["food_name"])
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

def get_food_log_by_id(log_id: int) -> FoodLog | None:
    session = SessionLocal()
    try:
        return session.get(FoodLog, log_id)
    finally:
        session.close()

def update_food_log(log_id: int, updates: dict) -> FoodLog | None:
    session = SessionLocal()
    try:
        food = session.get(FoodLog, log_id)

        if food is None:
            return None

        if "food_name" in updates and updates["food_name"]:
            updates["food_name"] = normalize_food_log_name(updates["food_name"])

        for key, value in updates.items():
            setattr(food, key, value)

        session.commit()
        session.refresh(food)

        return food

    except SQLAlchemyError:
        session.rollback()
        raise

    finally:
        session.close()

def delete_food_log(log_id: int) -> None:
    session = SessionLocal()
    try:
        food = session.get(FoodLog, log_id)

        if food is None:
            return

        session.delete(food)
        session.commit()

    except SQLAlchemyError:
        session.rollback()
        raise

    finally:
        session.close()

def get_food_stats_by_days(user_id: int, days: int) -> dict:
    start_period = datetime.now() - timedelta(days=days)

    with SessionLocal() as session:
        query = (
            select(
                func.strftime("%d.%m.%Y", FoodLog.created_at).label("date"),
                func.sum(FoodLog.kcal).label("kcal"),
                func.sum(FoodLog.protein).label("protein"),
                func.sum(FoodLog.fat).label("fat"),
                func.sum(FoodLog.carbs).label("carbs"),
            )
            .where(FoodLog.user_id == user_id)
            .where(FoodLog.created_at >= start_period)
            .group_by(func.date(FoodLog.created_at))
            .order_by(func.date(FoodLog.created_at).desc())
        )

        rows = session.execute(query).all()

    days_stats = []

    summary = {
        "kcal": 0,
        "protein": 0,
        "fat": 0,
        "carbs": 0,
    }

    for row in rows:
        day = {
            "date": row.date,
            "kcal": round(row.kcal or 0, 1),
            "protein": round(row.protein or 0, 1),
            "fat": round(row.fat or 0, 1),
            "carbs": round(row.carbs or 0, 1),
        }
        print(day)
        days_stats.append(day)

        summary["kcal"] += day["kcal"]
        summary["protein"] += day["protein"]
        summary["fat"] += day["fat"]
        summary["carbs"] += day["carbs"]

    tracked_days = len(days_stats)

    return {
        "days": days,
        "tracked_days": tracked_days,
        "daily": days_stats,
        "summary": {
            "kcal": round(summary["kcal"], 1),
            "protein": round(summary["protein"], 1),
            "fat": round(summary["fat"], 1),
            "carbs": round(summary["carbs"], 1),
        },
        "average": {
            "kcal": round(summary["kcal"] / tracked_days, 1) if tracked_days else 0,
            "protein": round(summary["protein"] / tracked_days, 1) if tracked_days else 0,
            "fat": round(summary["fat"] / tracked_days, 1) if tracked_days else 0,
            "carbs": round(summary["carbs"] / tracked_days, 1) if tracked_days else 0,
        },
    }
