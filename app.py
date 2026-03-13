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

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)
    description = db.Column(db.String(255))

class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    name = db.Column(db.String(100))
    quantity = db.Column(db.Integer, default=0)
    project = db.relationship('Project', backref=db.backref('materials', lazy=True))

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


# Projects inventory
@app.route("/projects")
def projects():
    if "user" not in session:
        return redirect("/")
    projects = Project.query.order_by(Project.name).all()
    return render_template(
        "projects.html",
        projects=projects,
        role=session.get("role"),
        user=session.get("user")
    )


@app.route("/add_project", methods=["POST"])
def add_project():
    if "user" not in session:
        return redirect("/")
    if session.get("role") not in ["Project Lead", "Workshop Manager"]:
        return "Not allowed"

    project = Project(
        name=request.form["name"],
        description=request.form.get("description", "")
    )

    db.session.add(project)
    db.session.commit()

    return redirect("/projects")


@app.route("/project/<int:project_id>")
def project_detail(project_id):
    if "user" not in session:
        return redirect("/")
    project = Project.query.get_or_404(project_id)
    return render_template(
        "project_detail.html",
        project=project,
        role=session.get("role"),
        user=session.get("user")
    )


@app.route("/add_material/<int:project_id>", methods=["POST"])
def add_material(project_id):
    if "user" not in session:
        return redirect("/")
    if session.get("role") not in ["Project Lead", "Workshop Manager"]:
        return "Not allowed"

    material = Material(
        project_id=project_id,
        name=request.form["name"],
        quantity=int(request.form.get("quantity", 0))
    )
    db.session.add(material)
    db.session.commit()
    return redirect(f"/project/{project_id}")


@app.route("/take_material/<int:material_id>", methods=["POST"])
def take_material(material_id):
    if "user" not in session:
        return redirect("/")
    material = Material.query.get_or_404(material_id)
    if material.quantity > 0:
        material.quantity -= 1
        db.session.commit()
    return redirect(f"/project/{material.project_id}")


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
else:
    # Ensure tables exist when running under WSGI servers like gunicorn
    with app.app_context():
        db.create_all()
