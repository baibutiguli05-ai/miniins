from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import jwt
import datetime
import os

app = Flask(__name__)

# 1. 替换为你的 PostgreSQL 连接字符串
# 注意：Render 的外部连接通常需要加上 sslmode=require
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://miniins_db_user:eSLhBtucYXILPrnDmJZYuNRlaT5U93EN@dpg-d77urihr0fns738bc7gg-a.oregon-postgres.render.com/miniins_db?sslmode=require'

# 建议：如果以后想更安全，可以改用环境变量：
# app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace("postgres://", "postgresql://", 1)

app.config['SECRET_KEY'] = 'secret123'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 定义用户模型
class User(db.Model):
    __tablename__ = 'users' # 明确指定表名
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)

# 在程序启动时创建表（如果表不存在）
with app.app_context():
    db.create_all()

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        # 检查用户是否已存在
        if User.query.filter_by(nickname=data['nickname']).first():
            return jsonify({"message": "User already exists"}), 400
            
        new_user = User(nickname=data['nickname'], password=data['password'])
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "Success"}), 201
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        user = User.query.filter_by(nickname=data['nickname'], password=data['password']).first()
        
        if user:
            # 生成 Token
            payload = {
                'id': user.id,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
            }
            token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')
            return jsonify({"token": token})
            
        return jsonify({"message": "Invalid nickname or password"}), 401
    except Exception as e:
        return jsonify({"message": str(e)}), 500

if __name__ == '__main__':
    # 这里的端口会根据环境自动调整
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
