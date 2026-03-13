from flask import Flask, render_template, request, redirect, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "lambda_secret"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tools.db'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    surname = db.Column(db.String(50))
    email = db.Column(db.String(100), unique=True)
    phone = db.Column(db.String(20))
    role = db.Column(db.String(50))
    password = db.Column(db.String(100))

class Tool(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tool_type = db.Column(db.String(100))
    make = db.Column(db.String(100))
    serial = db.Column(db.String(100))
    status = db.Column(db.String(50), default="Available")
    booked_by = db.Column(db.String(100), default="")

@app.route("/")
def login_page():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"]
    password = request.form["password"]

    user = User.query.filter_by(email=email, password=password).first()

    if user:
        session["user"] = user.name
        session["role"] = user.role
        return redirect("/home")

    return "Login failed"

@app.route("/register")
def register_page():
    return render_template("register.html")

@app.route("/register_user", methods=["POST"])
def register_user():

    user = User(
        name=request.form["name"],
        surname=request.form["surname"],
        email=request.form["email"],
        phone=request.form["phone"],
        role=request.form["role"],
        password=request.form["password"]
    )

    db.session.add(user)
    db.session.commit()

    return redirect("/")

@app.route("/home")
def home():
    if "user" not in session:
        return redirect("/")
    return render_template("home.html", name=session["user"])

@app.route("/tools")
def tools():

    tools = Tool.query.all()

    return render_template(
        "tools.html",
        tools=tools,
        role=session.get("role"),
        user=session.get("user")
    )

@app.route("/add_tool", methods=["POST"])
def add_tool():

    if session.get("role") not in ["Project Lead","Workshop Manager"]:
        return "Not allowed"

    tool = Tool(
        tool_type=request.form["type"],
        make=request.form["make"],
        serial=request.form["serial"]
    )

    db.session.add(tool)
    db.session.commit()

    return redirect("/tools")

@app.route("/remove_tool/<id>")
def remove_tool(id):

    if session.get("role") not in ["Project Lead","Workshop Manager"]:
        return "Not allowed"

    tool = Tool.query.get(id)

    db.session.delete(tool)
    db.session.commit()

    return redirect("/tools")

@app.route("/book/<id>")
def book_tool(id):

    tool = Tool.query.get(id)

    if tool.status == "Available":
        tool.status = "Booked"
        tool.booked_by = session["user"]

    db.session.commit()

    return redirect("/tools")

@app.route("/return/<id>")
def return_tool(id):

    tool = Tool.query.get(id)

    tool.status = "Available"
    tool.booked_by = ""

    db.session.commit()

    return redirect("/tools")


# PWA assets
@app.route('/manifest.json')
def manifest():
    return send_from_directory('.', 'manifest.json')


@app.route('/service-worker.js')
def service_worker():
    return send_from_directory('.', 'service-worker.js')

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)
