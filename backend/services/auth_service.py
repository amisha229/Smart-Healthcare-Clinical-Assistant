from sqlalchemy.orm import Session
from models.user import User

def create_user(db: Session, username: str, password: str, role: str):
    user = User(
        username=username,
        password=password,
        role=role
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()

    if not user:
        return None

    if user.password != password:
        return None

    return user