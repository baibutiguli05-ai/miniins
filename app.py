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
        if not nickname or not password:
            return jsonify({"message": "Empty fields"}), 400
        if len(password) < 8 or not re.search(r"\d", password) or not re.search(r"[a-zA-Z]", password):
            return jsonify({"message": "Password weak"}), 400
        if User.query.filter_by(nickname=nickname).first():
            return jsonify({"message": "Nickname already taken"}), 400
        hashed_pw = generate_password_hash(password)
        new_user = User(nickname=nickname, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "Success"}), 201
    except Exception as e:
        return jsonify({"message": "Server error"}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(nickname=data.get('nickname')).first()
    if user and check_password_hash(user.password, data.get('password')):
        token = jwt.encode({
            'id': user.id, 
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        return jsonify({"token": token})
    return jsonify({"message": "Invalid nickname or password"}), 401

# --- 核心修改：支持 GET 获取和 POST 上传 ---
@app.route('/posts', methods=['GET', 'POST'])
def handle_posts():
    # 1. 上传数据 (解决 Postman 405 错误)
    if request.method == 'POST':
        data = request.get_json()
        try:
            new_post = Post(
                username=data.get('username'),
                caption=data.get('caption'),
                postImage=data.get('postImage')
            )
            db.session.add(new_post)
            db.session.commit()
            return jsonify({"message": "Post created successfully!"}), 201
        except Exception as e:
            return jsonify({"message": str(e)}), 400

    # 2. 获取数据 (让 Android 端看到真实数据)
    posts = Post.query.all()
    # 如果数据库没数据，先给两个假数据兜底，防止 Android 端一片空白
    if not posts:
        return jsonify([
            {
                "username": "Xiao_Man",
                "caption": "Database is empty, showing sample!",
                "postImage": "https://picsum.photos/800/800?random=1"
            }
        ])
    
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
