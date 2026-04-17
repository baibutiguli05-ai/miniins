from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import jwt
import datetime
import os

app = Flask(__name__)

# --- 配置部分 ---
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 数据库连接处理
uri = os.getenv("DATABASE_URL")
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri or 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'secret123'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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
    postImage = db.Column(db.Text) 
    likes_count = db.Column(db.Integer, default=0) # 新增：点赞总数字段
    comments = db.relationship('Comment', backref='post', lazy=True)
    likes = db.relationship('Like', backref='post', lazy=True) # 建立与点赞表的关联

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    username = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)

# 新增：点赞模型，用于记录点赞历史
class Like(db.Model):
    __tablename__ = 'likes'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    username = db.Column(db.String(80), nullable=False) # 记录是谁点赞的

# --- 静态资源路由 ---
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- 核心接口：多图上传 ---
@app.route('/upload_multiple', methods=['POST'])
def upload_multiple():
    try:
        files = request.files.getlist('images') 
        caption = request.form.get('caption', '')
        username = request.form.get('username', 'Anonymous')
        
        if not files:
            return jsonify({"message": "No images provided"}), 400

        image_urls = []
        for file in files:
            if file and file.filename != '':
                filename = secure_filename(f"{datetime.datetime.now().timestamp()}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_urls.append(f"{request.host_url}uploads/{filename}")
        
        image_url_str = ",".join(image_urls)
        new_post = Post(username=username, caption=caption, postImage=image_url_str)
        
        db.session.add(new_post)
        db.session.commit()
        
        return jsonify({"message": "success", "urls": image_urls}), 201
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"message": str(e)}), 500

# --- 查询所有帖子 ---
@app.route('/posts', methods=['GET'])
def get_posts():
    posts = Post.query.order_by(Post.id.desc()).all()
    return jsonify([{
        "id": p.id, 
        "username": p.username,
        "caption": p.caption,
        "postImage": p.postImage,
        "likes_count": p.likes_count, # 返回点赞数
        "comments": [{"username": c.username, "content": c.content} for c in p.comments]
    } for p in posts])

# --- 发表评论接口 ---
@app.route('/posts/<int:post_id>/comments', methods=['POST'])
def add_comment(post_id):
    try:
        data = request.get_json()
        username = data.get('username', 'Anonymous')
        content = data.get('content')

        if not content:
            return jsonify({"message": "Content is empty"}), 400

        post = Post.query.get(post_id)
        if not post:
            return jsonify({"message": "Post not found"}), 404

        new_comment = Comment(post_id=post_id, username=username, content=content)
        db.session.add(new_comment)
        db.session.commit()

        return jsonify({"message": "Comment added"}), 201
    except Exception as e:
        return jsonify({"message": str(e)}), 500

# --- 完善后的点赞接口 ---
@app.route('/posts/<int:post_id>/like', methods=['POST'])
def toggle_like(post_id):
    try:
        data = request.get_json()
        username = data.get('username', 'Anonymous')

        post = Post.query.get(post_id)
        if not post:
            return jsonify({"message": "Post not found"}), 404

        # 检查该用户是否已经点过赞
        existing_like = Like.query.filter_by(post_id=post_id, username=username).first()

        if existing_like:
            # 如果点过，则取消点赞
            db.session.delete(existing_like)
            post.likes_count = max(0, post.likes_count - 1)
            message = "Unliked"
        else:
            # 如果没点过，新增记录
            new_like = Like(post_id=post_id, username=username)
            db.session.add(new_like)
            post.likes_count += 1
            message = "Liked"

        db.session.commit() # 关键：提交到数据库
        
        # 返回 JSON 格式的点赞总数给 Android 解析
        return jsonify({
            "message": message, 
            "likes_count": post.likes_count
        }), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

# --- 用户认证接口 ---
@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        nickname = data.get('nickname', '').strip()
        password = data.get('password', '')
        if not nickname or not password: 
            return jsonify({"message": "Empty fields"}), 400
        if User.query.filter_by(nickname=nickname).first(): 
            return jsonify({"message": "Exists"}), 400
        new_user = User(nickname=nickname, password=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "Success"}), 201
    except: 
        return jsonify({"message": "Error"}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(nickname=data.get('nickname')).first()
    if user and check_password_hash(user.password, data.get('password')):
        token = jwt.encode({
            'id': user.id, 
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm="HS256")
        return jsonify({"token": token, "username": user.nickname})
    return jsonify({"message": "Invalid"}), 401

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
