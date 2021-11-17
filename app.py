# Flask imports
import flask
import requests
from flask import Flask, redirect, request
from flask import render_template
from flask import session
from flask import abort


# Login tools
from flask_login import LoginManager
from flask_login import UserMixin
from flask_login import login_required
from flask_login import login_user
from flask_login import current_user

# Database imports
from flask_sqlalchemy import SQLAlchemy

# API tools
import os
import pathlib
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests
import google_auth_oauthlib.flow


# Local Imports
import YoutubeAPI as yt


# Fixing Database URI to postgresql format
uri = os.getenv("DATABASE_URL")
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

# Flask app initialization, db setup, login setup
app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = uri
db = SQLAlchemy(app)

# database: user and fav_flag_array for each user
class User(db.Model, UserMixin):
    id = db.Column(db.Integer)
    user_id = db.Column(db.String(50), primary_key=True)
    fav_flag_array = db.Column(db.String(10), nullable=True)


# pass the favorite flag array from home.html and make a python obj and add to db
# session.add(python_object)
# session.commit()

# google login ids ad secret keys
app.secret_key = os.getenv("secret_key")
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json")
scopes = [
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=scopes,
    redirect_uri="http://127.0.0.1:5000/callback",
)

login_manager = LoginManager(app)


@login_manager.user_loader
def load_user(id):
    return User.query.get((id))


# Database classes here
# Username probably subject to change based on how Google OAuth works, as that's how we're logging users in.
# Country 1-5 are meant to store the user's 5 favorite countries to be pinned in order
# This is just an idea subject to change
# Accountage stored in hours

# UserPreferences Table
# username = db.Column(db.String(20), primary_key=True)
# country1 = db.Column(db.String(40))
# country2 = db.Column(db.String(40))
# country3 = db.Column(db.String(40))
# country4 = db.Column(db.String(40))
# country5 = db.Column(db.String(40))
# accountage = db.Column(db.Integer)

# App Routing
@app.route("/")
def index():
    # create table if it doesn't exist, if exists do nothing
    db.create_all()
    # Probably doesn't need to be modified
    return flask.redirect(flask.url_for("login_page"))


def login_is_required(function):  # decorator for requiring login on specific pages
    def wrapper(*args, **kwargs):
        if "google_id" not in session:
            return abort(401)  # Authorization required
        else:
            return function()

    wrapper.__name__ = function.__name__
    return wrapper


@app.route("/login")
def login_page():
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    # Expected input: none (redirects only)
    # Expected user input: Click on google login button
    # Expected output: Redirect user to Google's authorization endpoint, where they will log in
    return redirect(authorization_url)
    # Probably just a button to login with


@app.route("/callback")
def callback():

    # Expected input: Authorization code from google
    # If they are not already in the database, add their info to the database
    flow.fetch_token(authorization_response=request.url)
    # Authentication happens here!
    # If user is not authenticated properly, send them back to the login endpoint
    if not session["state"] == request.args["state"]:
        abort(500)  # State does not match!

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=os.getenv("GOOGLE_CLIENT_ID"),
    )

    session["google_id"] = id_info.get("sub")
    session["name"] = id_info.get("name")

    # variable pulls user email ID
    emailID = id_info.get("email")

    # Setup EmailID variable to get user's username here

    # Query the database of users to see if the user logging in exists in the db
    exists = (
        db.session.query(User.user_id).filter_by(user_id=emailID).first() is not None
    )
    if not exists:
        empty = db.session.query(User.id).first() is None
        if empty:
            new_id = 0
        else:
            new_id_row = db.session.query(User.id).order_by(User.id.desc()).first()
            new_id = new_id_row.id + 1
        # If we can't find the user, create a line for them and log them in.
        new_user = User(user_id=emailID, id=new_id)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)

    else:
        user = User.query.filter_by(user_id=emailID).first()
        login_user(user)
    # Expected output:
    # If user is authenticated properly, send them to the home endpoint
    return redirect("/home")


@app.route("/logout")
def logout():
    # Expected input: none
    # Expected output: redirect user to login endpoint

    # Log out user here
    session.clear()
    return redirect("/")


@app.route("/home")
@login_is_required
def home_page():
    # Expected input: none (redirects only)
    # Expected user input: click on country, click on logout button
    # Expected outputs:
    # Selected country (redirect to user endpoint)
    # Country code should be sent with post request and id "code"
    # Expecting the 2 digit country codes on the flag png files.
    # Log Out (redirect to logout endpoint)
    return render_template("home.html")


@app.route("/user", methods=["POST"])
@login_is_required
def user_page():
    # Expected input: Selected country
    # Input should be received through post request with id "code"
    # Expected user input: click on video, click on logout button, click on home button
    # Expected outputs
    # Video (Redirect to youtube)
    # Home (redirect to home endpoint)
    # Log Out (redirect to logout endpoint)
    # Url should come in format "/user/us"

    # Get country code
    code = request.form["code"]
    # Calling API
    VideoInformation = yt.GetTopFive(code)

    # Create image link to render flag
    flag = "../static/resources/" + code + ".png"
    print(flag)

    # Load user info

    # Load country video info
    # Youtube API calls here
    # Expected input for API call: country name (string)
    # Expected output: the top 5 trending videos in that country
    # This should be a list of urls extracted from a JSON response.

    # Pass info to render in page
    return render_template(
        "user.html",
        videoinfo=VideoInformation,
        flagsrc=flag,
    )

@app.route("/save_favorite", methods=["POST"])
@login_is_required
def save_favorite():
    data = request.form['savefave']

    username = current_user.username
    user = User.query.filter_by(user_id=username).first()
    user.fav_flag_array = data
    db.session.commit()
    
    return redirect("/home")


# Initialize db and run application
# For testing, comment out host and port lines.

# Add once model for database has been created
# db.create_all()
app.run(
    debug=True
    # host="0.0.0.0",
    # port=int(os.getenv("PORT", 8080)),
)
