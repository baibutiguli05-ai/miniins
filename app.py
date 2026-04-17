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
    likes_count = db.Column(db.Integer, default=0)
    comments = db.relationship('Comment', backref='post', lazy=True, cascade="all, delete-orphan")
    likes = db.relationship('Like', backref='post', lazy=True, cascade="all, delete-orphan")

    def to_dict(self, current_user=None):
        """封装一个通用的转换方法"""
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

# --- 路由接口 ---

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# 1. 获取所有帖子 (首页流)
@app.route('/posts', methods=['GET'])
def get_posts():
    current_user = request.args.get('username')
    posts = Post.query.order_by(Post.id.desc()).all()
    return jsonify([p.to_dict(current_user) for p in posts])

# 2. 获取特定用户发布的帖子 (个人主页-我的发布)
@app.route('/posts/me', methods=['GET'])
def get_my_posts():
    target_username = request.args.get('username') # 想要查询谁的
    if not target_username:
        return jsonify({"message": "Username is required"}), 400
    
    posts = Post.query.filter_by(username=target_username).order_by(Post.id.desc()).all()
    return jsonify([p.to_dict(target_username) for p in posts])

# 3. 获取用户点赞过的帖子 (个人主页-我的点赞)
@app.route('/posts/liked', methods=['GET'])
def get_liked_posts():
    username = request.args.get('username')
    if not username:
        return jsonify({"message": "Username is required"}), 400

    # 通过关联查询找到该用户点赞过的所有 Post
    posts = Post.query.join(Like).filter(Like.username == username).order_by(Post.id.desc()).all()
    return jsonify([p.to_dict(username) for p in posts])

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
        return jsonify({"message": str(e)}), 500

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

@app.route('/posts/<int:post_id>/like', methods=['POST'])
def toggle_like(post_id):
    try:
        data = request.get_json()
        username = data.get('username', 'Anonymous')

        post = Post.query.get(post_id)
        if not post:
            return jsonify({"message": "Post not found"}), 404

        existing_like = Like.query.filter_by(post_id=post_id, username=username).first()

        if existing_like:
            db.session.delete(existing_like)
            post.likes_count = max(0, post.likes_count - 1)
            message = "Unliked"
            is_liked = False
        else:
            new_like = Like(post_id=post_id, username=username)
            db.session.add(new_like)
            post.likes_count += 1
            message = "Liked"
            is_liked = True

        db.session.commit()
        
        return jsonify({
            "message": message, 
            "likes_count": post.likes_count,
            "is_liked": is_liked 
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500

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
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm="HS256")
        return jsonify({"token": token, "username": user.nickname})
    return jsonify({"message": "Invalid"}), 401

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
