"""Run this to create users: python seed_users.py"""
from passlib.context import CryptContext
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import User, Base

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
hashed = pwd_context.hash('Gem@123')

engine = create_engine('sqlite:///./gem_automation.db')
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)
db = Session()

users = ['user1', 'user2', 'user3', 'user4', 'user5', 'user6', 'user7']

for u in users:
    existing = db.query(User).filter(User.email == f'{u}@gem.com').first()
    if not existing:
        user = User(
            email=f'{u}@gem.com',
            name=u.capitalize(),
            hashed_password=hashed,
            is_active=True
        )
        db.add(user)
        print(f'Created {u}@gem.com')
    else:
        print(f'{u}@gem.com already exists')

db.commit()
db.close()
print('Done!')
