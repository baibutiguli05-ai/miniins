from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash # 导入加密工具
import jwt
import datetime
import os
import re # 导入正则表达式用于校验

app = Flask(__name__)

# 数据库配置（保持你之前的环境变量读取逻辑）
uri = os.getenv("DATABASE_URL")
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri or 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'secret123'

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False) # 哈希后的密码较长，建议设为255

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    nickname = data.get('nickname')
    password = data.get('password')

    # --- 密码强度校验逻辑 ---
    # 条件：至少8位，包含字母和数字
    if len(password) < 8:
        return jsonify({"message": "Password must be at least 8 characters"}), 400
    if not re.search(r"[a-zA-Z]", password) or not re.search(r"[0-9]", password):
        return jsonify({"message": "Password must contain both letters and numbers"}), 400

    # 检查用户是否存在
    if User.query.filter_by(nickname=nickname).first():
        return jsonify({"message": "User already exists"}), 400

    # --- 哈希加密 ---
    hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
    
    new_user = User(nickname=nickname, password=hashed_pw)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "Success"}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(nickname=data.get('nickname')).first()

    # --- 校验哈希密码 ---
    # 不能用 == 判断，必须用 check_password_hash
    if user and check_password_hash(user.password, data.get('password')):
        token = jwt.encode({
            'id': user.id, 
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        return jsonify({"token": token})
    
    return jsonify({"message": "Invalid credentials"}), 401

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
