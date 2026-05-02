from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import jwt
import datetime
import os

app = Flask(__name__)
CORS(app)  # 允许跨域，防止Android连接被阻断

# --- 配置部分 ---
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

uri = os.getenv("DATABASE_URL")
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri or 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'secret123'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)
# 初始化 SocketIO，使用 eventlet 模式以获得更好的并发性能
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- 数据库模型 (保持不变) ---
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
    postImage = db.Column(db.Text) 
    likes_count = db.Column(db.Integer, default=0)
    comments = db.relationship('Comment', backref='post', lazy=True, cascade="all, delete-orphan")
    likes = db.relationship('Like', backref='post', lazy=True, cascade="all, delete-orphan")

    def to_dict(self, current_user=None):
        is_liked = False
        if current_user:
            is_liked = any(like.username == current_user for like in self.likes)
        return {
            "id": self.id, 
            "username": self.username,
            "caption": self.caption,
            "postImage": self.postImage,
            "likes_count": self.likes_count,
            "is_liked": is_liked,
            "comments": [{"username": c.username, "content": c.content} for c in self.comments]
        }

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    username = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)

class Like(db.Model):
    __tablename__ = 'likes'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    username = db.Column(db.String(80), nullable=False)

# --- Socket 实时通信逻辑 ---

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected")

# 当用户在 Android 端发送消息时触发
@socketio.on('send_comment')
def handle_realtime_comment(data):
    """
    data 预想格式: {'post_id': 1, 'username': 'Gemini', 'content': 'Hello!'}
    """
    # 广播给所有人，这样别人的 App 会立刻跳出这条评论
    emit('receive_comment', data, broadcast=True)

# --- 原有路由接口 (保持不变) ---

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/posts', methods=['GET'])
def get_posts():
    current_user = request.args.get('username')
    posts = Post.query.order_by(Post.id.desc()).all()
    return jsonify([p.to_dict(current_user) for p in posts])

@app.route('/upload_multiple', methods=['POST'])
def upload_multiple():
    try:
        files = request.files.getlist('images') 
        caption = request.form.get('caption', '')
        username = request.form.get('username', 'Anonymous')
        if not files: return jsonify({"message": "No images provided"}), 400
        image_urls = []
        for file in files:
            if file and file.filename != '':
                filename = secure_filename(f"{datetime.datetime.now().timestamp()}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_urls.append(f"{request.host_url}uploads/{filename}")
        new_post = Post(username=username, caption=caption, postImage=",".join(image_urls))
        db.session.add(new_post)
        db.session.commit()
        return jsonify({"message": "success", "urls": image_urls}), 201
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/posts/<int:post_id>/comments', methods=['POST'])
def add_comment(post_id):
    try:
        data = request.get_json()
        username = data.get('username', 'Anonymous')
        content = data.get('content')
        if not content: return jsonify({"message": "Content is empty"}), 400
        post = Post.query.get(post_id)
        if not post: return jsonify({"message": "Post not found"}), 404
        new_comment = Comment(post_id=post_id, username=username, content=content)
        db.session.add(new_comment)
        db.session.commit()
        return jsonify({"message": "Comment added"}), 201
    except Exception as e:
        return jsonify({"message": str(e)}), 500

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
        token = jwt.encode({
            'id': user.id, 
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm="HS256")
        return jsonify({"token": token, "username": user.nickname})
    return jsonify({"message": "Invalid"}), 401

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 5000))
    # 重点：改用 socketio.run
    socketio.run(app, host='0.0.0.0', port=port)
