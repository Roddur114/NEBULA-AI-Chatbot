from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_dance.contrib.google import make_google_blueprint, google
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from dotenv import load_dotenv
import os
from groq import Groq

# Load environment variables
load_dotenv()

# Initialize the Flask app
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")  # Add a secret key for session management

# Initialize the Groq client
client = Groq()

# Configure Google OAuth
google_bp = make_google_blueprint(
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    redirect_to="google_login",
)
app.register_blueprint(google_bp, url_prefix="/auth")

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.login_view = "index"
login_manager.init_app(app)


# Mock User class (for demo purposes)
class User:
    def __init__(self, email):
        self.email = email

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return self.email


# In-memory storage for authenticated users
users = {}


@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)


# Index (Login) Route
@app.route("/")
def index():
    return render_template("user_login.html")


# Google login route callback
@app.route("/google_login")
def google_login():
    if not google.authorized:
        return redirect(url_for("google.login"))

    resp = google.get("/oauth2/v1/userinfo")
    if resp.ok:
        user_info = resp.json()
        email = user_info["email"]

        # Check if user exists, otherwise "sign them up"
        user = users.get(email)
        if user is None:
            user = User(email)
            users[email] = user

        login_user(user)
        return redirect(url_for("chatbot"))

    return redirect(url_for("index"))


# Logout route
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


# Chatbot Route
@app.route("/chatbot")
@login_required
def chatbot():
    return render_template("chatbot.html")


# Chatbot message route
@app.route("/send_message", methods=["POST"])
def send_message():
    data = request.get_json()
    user_message = data.get("message", "")

    if not user_message:
        return jsonify({"bot_response": "Please enter a message."})

    # Generate chatbot response using Groq's LLaMA model
    try:
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_message},
            ],
            temperature=1,
            max_tokens=1024,
            top_p=1,
            stream=True,
            stop=None,
        )

        # Collect the streaming response
        bot_response = ""
        for chunk in completion:
            bot_response += chunk.choices[0].delta.content or ""
            bot_response = bot_response.replace("\n", "<br>")

        return jsonify({"bot_response": bot_response})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify(
            {"bot_response": "Sorry, there was an error processing your request."}
        )


# Start the Flask app
if __name__ == "__main__":
    app.run(debug=True)
