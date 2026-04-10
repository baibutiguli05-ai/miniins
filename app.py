from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import jwt
import datetime
import os

app = Flask(__name__)

# --- 配置部分 ---
# 创建上传文件夹
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
    postImage = db.Column(db.String(500)) 

# --- 静态资源路由 (解决图片加载感叹号问题) ---
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- 逻辑接口 ---
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
        return jsonify({"token": token})
    return jsonify({"message": "Invalid"}), 401

@app.route('/posts', methods=['GET', 'POST'])
def handle_posts():
    db.create_all() 

    if request.method == 'POST':
        # 兼容性处理
        if request.is_json:
            data = request.get_json()
            username = data.get('username')
            caption = data.get('caption')
            image_url = data.get('postImage') # JSON模式通常传URL
        else:
            # 处理真正的文件上传
            username = request.form.get('username', 'Anonymous')
            caption = request.form.get('caption', '')
            file = request.files.get('image')
            
            if file:
                filename = secure_filename(f"{datetime.datetime.now().timestamp()}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                # 拼凑出App可以直接访问的完整URL
                # 这里的域名请替换为你Render的实际域名
                image_url = f"{request.host_url}uploads/{filename}"
            else:
                image_url = ""

        new_post = Post(
            username=username,
            caption=caption,
            postImage=image_url
        )
        db.session.add(new_post)
        db.session.commit()
        return jsonify({"message": "Post created successfully!"}), 201

    # GET 请求：返回列表
    posts = Post.query.order_by(Post.id.desc()).all()
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
