import os

from backend.models import db
from app import create_app

app = create_app()
with app.app_context():
    db.create_all()
    print("Tables created.")
print("Current working directory:", os.getcwd())
print("Database URI:", app.config['SQLALCHEMY_DATABASE_URI'])