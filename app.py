from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    flash,
    session,
)
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
import os
from groq import Groq

# Load environment variables
load_dotenv()

client = Groq()

# Initialize the Flask app
app = Flask(__name__)

# Set up the database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "your_secret_key_here"  # Needed for session management
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)


# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)


# Initialize the database
with app.app_context():
    db.create_all()


# Check if the user is logged in
@app.route("/check_login_status")
def check_login_status():
    if "user_id" in session:
        return jsonify({"logged_in": True})
    else:
        return jsonify({"logged_in": False})


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        # Check if user exists
        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password, password):
            # Password matches, store the user ID in the session
            session["user_id"] = user.id

            # Redirect after login, either to chatbot or next page (if redirected from prompt)
            next_page = request.args.get("next")
            prompt = request.args.get("prompt")

            if next_page == "chatbot" and prompt:
                return redirect(url_for("chatbot", prompt=prompt))
            return redirect(url_for("chatbot"))
        else:
            # Invalid login, reload the login page with an error
            flash("Invalid credentials. Please try again or sign up.")
            return redirect(url_for("login"))

    return render_template("user_login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            flash("User already exists. Please log in.")
            return redirect(url_for("login"))

        # Hash the password and store the user in the database
        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
        new_user = User(email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash("Sign up successful. Please log in.")
        return redirect(url_for("login"))

    return render_template("signup.html")


# Route for the chatbot interface
@app.route("/chatbot")
def chatbot():
    # Get the prompt if passed from the homepage
    prompt = request.args.get("prompt", "")

    return render_template("chatbot.html", prompt=prompt)


# Route to handle chatbot input and generate responses
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
            # print(bot_response)

        return jsonify({"bot_response": bot_response})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify(
            {"bot_response": "Sorry, there was an error processing your request."}
        )


# Start the Flask app
if __name__ == "__main__":
    app.run(debug=True)
