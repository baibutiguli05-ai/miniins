from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import os
import re

app = Flask(__name__)

# 数据库配置
uri = os.getenv("DATABASE_URL")
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri or 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'secret123'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- 数据库模型 ---

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    caption = db.Column(db.String(255))
    postImage = db.Column(db.String(500)) 

# --- 路由接口 ---

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        nickname = data.get('nickname', '').strip()
        password = data.get('password', '')
        if not nickname or not password: return jsonify({"message": "Empty fields"}), 400
        if User.query.filter_by(nickname=nickname).first(): return jsonify({"message": "Exists"}), 400
        new_user = User(nickname=nickname, password=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "Success"}), 201
    except: return jsonify({"message": "Error"}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(nickname=data.get('nickname')).first()
    if user and check_password_hash(user.password, data.get('password')):
        token = jwt.encode({'id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)}, app.config['SECRET_KEY'])
        return jsonify({"token": token})
    return jsonify({"message": "Invalid"}), 401

# --- 核心修改：修复 UndefinedTable 错误 ---
@app.route('/posts', methods=['GET', 'POST'])
def handle_posts():
    # 强制在每次请求前检查表是否存在（解决 Render 部署不刷新的问题）
    db.create_all() 

    if request.method == 'POST':
        data = request.get_json()
        new_post = Post(
            username=data.get('username'),
            caption=data.get('caption'),
            postImage=data.get('postImage')
        )
        db.session.add(new_post)
        db.session.commit()
        return jsonify({"message": "Post created successfully!"}), 201

    posts = Post.query.all()
    return jsonify([{
        "username": p.username,
        "caption": p.caption,
        "postImage": p.postImage
    } for p in posts])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
