from sqlalchemy.orm import Session
from models.user import User
from database import SessionLocal


def seed_test_users():
    """Add test users to database"""
    db = SessionLocal()
    try:
        # Ensure baseline users exist without duplicating existing accounts.
        test_users = [
            User(username="Adam", password="password123", role="Doctor"),
            User(username="Amisha", password="password123", role="Doctor"),
            User(username="Arjun", password="password123", role="Nurse"),
            User(username="Meera", password="password123", role="Doctor"),
            User(username="Rohan", password="password123", role="Nurse"),
            User(username="Akash", password="akash", role="Admin"),
        ]

        created_count = 0
        for user in test_users:
            existing_user = db.query(User).filter(User.username == user.username).first()
            if existing_user:
                continue

            db.add(user)
            created_count += 1

        db.commit()
        if created_count == 0:
            print("Default users already exist. No seed changes were needed.")
        else:
            print(f"Successfully seeded {created_count} default users.")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding test users: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_test_users()
