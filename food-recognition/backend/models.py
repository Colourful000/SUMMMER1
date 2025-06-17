# food-recognition/backend/models.py

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from backend import db  # ✅ 改为绝对导入
db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)

class AnalysisHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    food_name = db.Column(db.String(100))
    nutrients = db.Column(db.Text)
    ai_advice = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)