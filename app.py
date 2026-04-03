from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import jwt
import datetime

app = Flask(__name__)

# 暂时使用 SQLite 方便测试，如果你想连 PostgreSQL，稍后在 Render 环境变量里改
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'secret123'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)

with app.app_context():
    db.create_all()

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    new_user = User(nickname=data['nickname'], password=data['password'])
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "Success"}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(nickname=data['nickname'], password=data['password']).first()
    if user:
        token = jwt.encode({'id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)}, app.config['SECRET_KEY'])
        return jsonify({"token": token})
    return jsonify({"message": "Invalid"}), 401

if __name__ == '__main__':
    app.run()