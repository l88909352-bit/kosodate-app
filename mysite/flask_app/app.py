from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_
from flask_socketio import SocketIO, join_room, emit

from flask import session, render_template
from flask_login import current_user  # Flask-Login使っている場合
from datetime import datetime
from flask_migrate import Migrate




app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

app.secret_key = "secretkey"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# -------------------
# モデル
# -------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    password = db.Column(db.String(200))

    region = db.Column(db.String(100))
    child_age = db.Column(db.Integer)
    bio = db.Column(db.String(300))

    followers = db.relationship(
        "Follow",
        foreign_keys="Follow.following_id",
        backref="followed_user",
        lazy="dynamic"
    )

    following = db.relationship(
        "Follow",
        foreign_keys="Follow.follower_id",
        backref="follower_user",
        lazy="dynamic"
    )

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    user = db.relationship("User")
    likes = db.relationship("Like", backref="post", cascade="all, delete")
class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"))

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"))

    user = db.relationship("User")
    post = db.relationship("Post", backref="comments")
    
class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    follower_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    following_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    follower = db.relationship("User", foreign_keys=[follower_id])
    following = db.relationship("User", foreign_keys=[following_id])

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship("User", foreign_keys=[sender_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])

class DM(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('chat_room.id'))
    sender_id = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
class ChatRoom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user1_id = db.Column(db.Integer, nullable=False)
    user2_id = db.Column(db.Integer, nullable=False)
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)        # 商品名
    category = db.Column(db.String(50))                     # 乳児・幼児・育児用品など
    price = db.Column(db.Float)                             # 価格
    description = db.Column(db.Text)                        # 詳細
    store = db.Column(db.String(100))                       # お店の名前
    url = db.Column(db.String(200)) 
class Support(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)   # タイトル
    description = db.Column(db.Text, nullable=False)    # 詳細
    url = db.Column(db.String(200))                     # 参考URL
    created_at = db.Column(db.DateTime, default=db.func.now())
      

# -------------------
# ルーティング
# -------------------

from sqlalchemy import or_

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect("/login")

    # セッションIDでユーザー取得
    user = db.session.get(User, session["user_id"])
    if not user:
        # セッションにあるIDがDBに存在しない場合はログアウト扱い
        session.pop("user_id", None)
        return redirect("/login")

    show_all = request.args.get("all")

    if show_all:
        # 全投稿表示
        posts = Post.query.order_by(Post.id.desc()).all()
    else:
        # フォロー中ユーザー＋自分の投稿
        following_ids = [
            f.following_id
            for f in Follow.query.filter_by(follower_id=user.id).all()
        ]
        posts = Post.query.filter(
            or_(
                Post.user_id == user.id,
                Post.user_id.in_(following_ids)
            )
        ).order_by(Post.id.desc()).all()

    # いいね済み投稿ID
    liked_post_ids = [
        like.post_id
        for like in Like.query.filter_by(user_id=user.id).all()
    ]

    return render_template(
        "home.html",
        user=user,
        posts=posts,
        liked_post_ids=liked_post_ids
    )

@app.route("/users")
def users():
    if "user_id" not in session:
        return redirect("/login")

    current_user_id = session["user_id"]

    all_users = User.query.all()

    # フォローしているユーザーID取得
    following_ids = [
        f.following_id
        for f in Follow.query.filter_by(
            follower_id=current_user_id
        ).all()
    ]

    return render_template(
        "users.html",
        users=all_users,
        following_ids=following_ids,
        current_user_id=current_user_id
    )
    
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user = User(
            name=request.form.get("name"),
            password=request.form.get("password"),
            region=request.form.get("region"),
            child_age=request.form.get("child_age"),
            bio=request.form.get("bio")
        )

        db.session.add(user)
        db.session.commit()

        return redirect("/login")

    return render_template("register.html")
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(
            name=request.form.get("name"),
            password=request.form.get("password")
        ).first()

        if user:
            session["user_id"] = user.id
            return redirect("/")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/post", methods=["POST"])
def post():
    if "user_id" not in session:
        return redirect("/login")

    content = request.form["content"]

    new_post = Post(
        content=content,
        user_id=session["user_id"]
    )

    db.session.add(new_post)
    db.session.commit()   # ← これ超重要

    return redirect("/")

@app.route("/comment/<int:post_id>", methods=["POST"])
def comment(post_id):
    if "user_id" not in session:
        return redirect("/login")

    new_comment = Comment(
        content=request.form.get("content"),
        user_id=session["user_id"],
        post_id=post_id
    )

    db.session.add(new_comment)
    db.session.commit()

    return redirect("/")


@app.route("/delete_comment/<int:comment_id>")
def delete_comment(comment_id):
    if "user_id" not in session:
        return redirect("/login")

    comment = db.session.get(Comment, comment_id)

    if comment and comment.user_id == session["user_id"]:
        db.session.delete(comment)
        db.session.commit()

    return redirect("/")

@app.route("/like/<int:post_id>")
def like(post_id):
    if "user_id" not in session:
        return redirect("/login")

    existing_like = Like.query.filter_by(
        user_id=session["user_id"],
        post_id=post_id
    ).first()

    if existing_like:
        db.session.delete(existing_like)
    else:
        new_like = Like(
            user_id=session["user_id"],
            post_id=post_id
        )
        db.session.add(new_like)

    db.session.commit()
    return redirect("/")
@app.route("/my_profile")
def my_profile():
    if "user_id" not in session:
        return redirect("/login")

    user = User.query.get(session["user_id"])  # ログインユーザー
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.id.desc()).all()

    liked_post_ids = [like.post_id for like in Like.query.filter_by(user_id=user.id).all()]

    return render_template(
        "my_profile.html",
        user=user,
        posts=posts,
        liked_post_ids=liked_post_ids
    )
    
@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if "user_id" not in session:
        return redirect("/login")

    user = User.query.get(session["user_id"])

    if request.method == "POST":
        user.name = request.form["name"]
        user.bio = request.form["bio"]  # もし自己紹介フィールドがあれば
        db.session.commit()
        return redirect("/my_profile")  # 保存後に自分のプロフィールに戻る

    return render_template("edit_profile.html", user=user)

@app.route("/profile/<int:user_id>")
def profile(user_id):
    current_user = db.session.get(User, session["user_id"])
    profile_user = db.session.get(User, user_id)

    if profile_user is None:
        abort(404)

    # フォローしているユーザーIDリスト
    following_ids = [f.following_id for f in current_user.following]

    # 投稿一覧
    profile_posts = Post.query.filter_by(user_id=user_id).order_by(Post.created_at.desc()).all()
    posts = profile_posts  # 既存コードに合わせる

    return render_template(
        "profile.html",
        current_user=current_user,
        profile_user=profile_user,
        user=profile_user,  # ← これがポイント。テンプレートで user.name を使ってる場合必要
        following_ids=following_ids,
        profile_posts=profile_posts,
        posts=posts
    )
    
def get_or_create_room(user1, user2):
    room = ChatRoom.query.filter(
        ((ChatRoom.user1_id == user1) & (ChatRoom.user2_id == user2)) |
        ((ChatRoom.user1_id == user2) & (ChatRoom.user2_id == user1))
    ).first()

    if not room:
        room = ChatRoom(user1_id=user1, user2_id=user2)
        db.session.add(room)
        db.session.commit()

    return room



@app.route("/follow/<int:user_id>", methods=["POST"])
def follow(user_id):
    if "user_id" not in session:
        return redirect("/login")
    current_user_id = session["user_id"]

    # フォロー済みならアンフォロー
    follow = Follow.query.filter_by(
        follower_id=current_user_id,
        following_id=user_id
    ).first()

    if follow:
        db.session.delete(follow)
    else:
        new_follow = Follow(follower_id=current_user_id, following_id=user_id)
        db.session.add(new_follow)

    db.session.commit()
    return redirect(request.referrer or "/")  # 元ページに戻す

@app.route('/unfollow/<int:user_id>', methods=['POST'])
def unfollow(user_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    current_id = session["user_id"]

    follow = Follow.query.filter_by(
        follower_id=current_id,
        following_id=user_id
    ).first()

    if follow:
        db.session.delete(follow)
        db.session.commit()

    return redirect(url_for("profile", user_id=user_id))

@app.route("/delete_post/<int:post_id>")
def delete_post(post_id):
    post = Post.query.get(post_id)

    if post.user_id == session["user_id"]:
        db.session.delete(post)
        db.session.commit()

    return redirect("/")

@socketio.on('join')
def on_join(data):
    room_id = data['room_id']
    join_room(str(data['room_id']))

def get_room(user1, user2):
    return f"dm_{min(user1, user2)}_{max(user1, user2)}"

@app.route('/dm_rooms')
def dm_rooms():
    if "user_id" not in session:
        return redirect(url_for("login"))

    current_id = session["user_id"]

    # 自分がやり取りした相手のIDを取得
    sent_users = db.session.query(DM.receiver_id).filter(DM.sender_id==current_id)
    received_users = db.session.query(DM.sender_id).filter(DM.receiver_id==current_id)

    user_ids = set([u[0] for u in sent_users.all()] + [u[0] for u in received_users.all()])
    users = User.query.filter(User.id.in_(user_ids)).all()

    return render_template("dm_rooms.html", users=users)

@app.route('/dm/<int:other_user_id>')
def dm_chat(other_user_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    current_id = session["user_id"]

    # ルーム取得または作成
    room = get_or_create_room(current_id, other_user_id)

    # そのルームのメッセージだけ取得
    messages = DM.query.filter_by(room_id=room.id).order_by(DM.timestamp).all()

    other_user = User.query.get(other_user_id)

    return render_template("dm_chat.html",
                           messages=messages,
                           room_id=room.id,
                           other_user=other_user,
                           current_id=current_id)
    
@socketio.on('send_message')
def handle_send_message(data):

    room_id = int(data['room_id'])
    sender_id = data['sender_id']
    receiver_id = data['receiver_id']
    message = data['message']

    
    new_message = DM(
        room_id=room_id,
        sender_id=sender_id,
        receiver_id=receiver_id,
        content=message
    )

    db.session.add(new_message)
    db.session.commit()

    emit('receive_message', {
        'message': message,
        'sender_id': sender_id
    }, room=str(room_id))

@app.route('/items')
def item_list():
    items = Item.query.all()  # DBにある子育てグッズを全件取得
    return render_template('items.html', items=items)

@app.route("/support")
def support_list():
    supports = Support.query.order_by(Support.id.desc()).all()  # Supportテーブルから取得
    return render_template("support.html", supports=supports)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
    
