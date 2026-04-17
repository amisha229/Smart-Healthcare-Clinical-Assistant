#!/usr/bin/env python3
"""Add admin user to database"""
from models.user import User
from database import SessionLocal

def add_admin_user(username: str, password: str, role: str = "Admin"):
    """Add a new admin user to the database"""
    db = SessionLocal()
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            print(f"❌ User '{username}' already exists!")
            return False
        
        # Create new admin user
        new_user = User(
            username=username,
            password=password,  # In production, this should be hashed!
            role=role
        )
        
        db.add(new_user)
        db.commit()
        print(f"✅ Admin user '{username}' created successfully!")
        print(f"   Username: {username}")
        print(f"   Password: {password}")
        print(f"   Role: {role}")
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating user: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    add_admin_user("Akash", "akash", "Admin")
