# food-recognition/backend/models.py

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from backend import db  # ✅ 改为绝对导入
db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    gender = db.Column(db.String(20))   # 新增
    age = db.Column(db.Integer)         # 新增
    height = db.Column(db.Float)        # 新增
    weight = db.Column(db.Float)        # 新增
    diet_goal = db.Column(db.String(80))  # 饮食目标
    activity_level = db.Column(db.String(40))
    special_diet = db.Column(db.String(255))  # 特殊饮食习惯
    avatar_url = db.Column(db.String(255))  # 头像URL（可选）

class AnalysisHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    food_name = db.Column(db.String(100))
    nutrients = db.Column(db.Text)
    ai_advice = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    tag = db.Column(db.String(20))