from flask import Flask, request, redirect, render_template, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, date
import atexit

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' #type: ignore

# Define the User and Song models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    soulmate_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    songs = db.relationship('Song', backref='user', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)

class Song(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# User loader callback for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create the database tables and predefined users within the application context
with app.app_context():
    db.create_all()

    def add_users():
        if not User.query.first():
            user1 = User(username="Aliqyan", password="Manisha", soulmate_id=2) #type: ignore
            user2 = User(username="Manisha", password="Aliqyan", soulmate_id=1) #type: ignore
            db.session.add(user1)
            db.session.add(user2)
            db.session.commit()

    add_users()

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def do_login():
    username = request.form['username']
    password = request.form['password']
    user = User.query.filter_by(username=username, password=password).first()
    if user:
        login_user(user)
        return redirect(url_for('dashboard'))
    return "Invalid credentials", 401

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    username = current_user.username
    user = User.query.filter_by(username=username).first()
    
    daily_song = Song.query.filter_by(user_id=user.id).order_by(Song.timestamp.desc()).first()
    notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.timestamp.desc()).all()
    
    return render_template('dashboard.html', username=username, daily_song=daily_song, notifications=notifications)

@app.route('/submit_song', methods=['POST'])
@login_required
def submit_song():
    song_url = request.form['song_url']
    username = current_user.username
    user = User.query.filter_by(username=username).first()
    
    # Store the song in the database with timestamp
    new_song = Song(url=song_url, timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id=user.id)
    db.session.add(new_song)
    db.session.commit()
    
    # Notify the soulmate
    if user.soulmate_id:
        soulmate = User.query.get(user.soulmate_id)
        notification = Notification(message=f"Your soulmate {user.username} uploaded the song of the day!", 
                                    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                                    user_id=soulmate.id)
        db.session.add(notification)
        db.session.commit()
    
    return redirect('/dashboard')

# Function to clear songs at midnight
def clear_songs():
    with app.app_context():
        db.session.query(Song).delete()
        db.session.commit()
        print("Songs cleared at midnight")

@app.route('/all_songs')
@login_required
def all_songs():
    user_id = current_user.id
    user = User.query.get(user_id)
    soulmate = User.query.get(user.soulmate_id)
    
    today = date.today().isoformat()

    # Check if the user has uploaded their song
    user_song = Song.query.filter(Song.user_id==user.id, Song.timestamp.startswith(today)).first()
    
    # Check if the soulmate has uploaded their song
    soulmate_song = None
    if soulmate:
        soulmate_song = Song.query.filter(Song.user_id==soulmate.id, Song.timestamp.startswith(today)).first()
    
    # Prepare the message
    message = ""
    if not soulmate_song:
        message = "Your soulmate has not uploaded the song of the day yet."

    return render_template('all_songs.html', user_song=user_song, soulmate_song=soulmate_song, message=message)

# Set up the scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=clear_songs, trigger="cron", hour=0, minute=0)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    app.run(debug=True)
