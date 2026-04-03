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

# 新增 Post 模型，对应 Android 端的 Post.kt
class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    caption = db.Column(db.String(255))
    postImage = db.Column(db.String(500)) # 存储图片链接

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

# 新增获取帖子接口 (解决 404 错误)
@app.route('/posts', methods=['GET'])
def get_posts():
    # 这里先返回假数据，确保你 Android 端能刷出内容
    sample_posts = [
        {
            "username": "Xiao_Man",
            "caption": "Life is better when it is Xiao Man!",
            "postImage": "https://picsum.photos/800/800?random=1"
        },
        {
            "username": "Android_Dev",
            "caption": "Backend connected successfully!",
            "postImage": "https://picsum.photos/800/800?random=2"
        }
    ]
    return jsonify(sample_posts)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
