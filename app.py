import os
import io
import smtplib
from email.message import EmailMessage
from flask import Flask, render_template, request, redirect, session, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
from openpyxl import Workbook

app = Flask(__name__)
app.secret_key = "lambda_secret"

db_url = os.getenv("DATABASE_URL", "sqlite:///tools.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
db = SQLAlchemy(app)


def ensure_schema():
    """Lightweight guard to add new columns when the DB already exists."""
    insp = db.inspect(db.engine)
    material_cols = [c['name'] for c in insp.get_columns('material')] if insp.has_table('material') else []
    if 'part_number' not in material_cols and insp.has_table('material'):
        with db.engine.connect() as conn:
            conn.execute(db.text("ALTER TABLE material ADD COLUMN part_number VARCHAR(100)"))
            conn.commit()
    # drop make column if exists (legacy)
    tool_cols = [c['name'] for c in insp.get_columns('tool')] if insp.has_table('tool') else []
    if 'make' in tool_cols:
        try:
            with db.engine.connect() as conn:
                conn.execute(db.text("ALTER TABLE tool RENAME TO tool_old"))
                conn.execute(db.text("""
                    CREATE TABLE tool(
                        id INTEGER NOT NULL,
                        tool_type VARCHAR(100),
                        serial VARCHAR(100),
                        status VARCHAR(50) DEFAULT 'Available',
                        booked_by VARCHAR(100) DEFAULT '',
                        PRIMARY KEY (id)
                    )
                """))
                conn.execute(db.text("""
                    INSERT INTO tool (id, tool_type, serial, status, booked_by)
                    SELECT id, tool_type, serial, status, booked_by FROM tool_old
                """))
                conn.execute(db.text("DROP TABLE tool_old"))
                conn.commit()
        except Exception as exc:
            print("Schema migration for tool table skipped due to:", exc)
    # create new tables if missing
    db.create_all()


def send_mail(to_email, subject, body, attachment=None, filename=None):
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    if not smtp_server or not smtp_user or not smtp_pass:
        raise RuntimeError("SMTP is not configured. Please set SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD.")

    msg = EmailMessage()
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    if attachment and filename:
        msg.add_attachment(attachment, maintype="application", subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=filename)

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        if use_tls:
            server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)


def build_tools_workbook():
    wb = Workbook()
    ws = wb.active
    ws.title = "Tools"
    ws.append(["Tool Type", "Serial Number", "Status", "Booked By"])
    for t in Tool.query.order_by(Tool.tool_type).all():
        ws.append([t.tool_type, t.serial, t.status, t.booked_by])
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio

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
    part_number = db.Column(db.String(100))
    quantity = db.Column(db.Integer, default=0)
    project = db.relationship('Project', backref=db.backref('materials', lazy=True))

class MaterialLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    material_name = db.Column(db.String(100))
    part_number = db.Column(db.String(100))
    quantity = db.Column(db.Integer)
    taken_by = db.Column(db.String(100))
    action = db.Column(db.String(20))  # Added / Taken / Deleted
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

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
        session["email"] = user.email
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


@app.route("/forgot")
def forgot_page():
    return render_template("forgot.html")


@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if request.method == "GET":
        return redirect("/forgot")
    email = request.form["email"]
    new_password = request.form["password"]
    user = User.query.filter_by(email=email).first()
    if user:
        user.password = new_password
        db.session.commit()
    # Always respond the same to avoid leaking user existence
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


@app.route("/export_tools")
def export_tools():
    if "user" not in session:
        return redirect("/")
    to_email = session.get("email")
    if not to_email:
        return "No email on session. Please log in again."

    bio = build_tools_workbook()

    try:
        send_mail(
            to_email,
            "Lambda Projects - Tool Export",
            "Attached is the latest tool list.",
            attachment=bio.read(),
            filename="tools.xlsx"
        )
        return "Export sent to your email."
    except Exception as exc:
        return f"Failed to send export: {exc}"


@app.route("/export_tools_download")
def export_tools_download():
    if "user" not in session:
        return redirect("/")
    bio = build_tools_workbook()
    return send_file(
        bio,
        as_attachment=True,
        download_name="tools.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


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
        part_number=request.form.get("part_number", ""),
        quantity=int(request.form.get("quantity", 0))
    )
    db.session.add(material)
    db.session.flush()
    db.session.add(MaterialLog(
        project_id=project_id,
        material_name=material.name,
        part_number=material.part_number,
        quantity=material.quantity,
        taken_by=session.get("user"),
        action="Added"
    ))
    db.session.commit()
    return redirect(f"/project/{project_id}")


@app.route("/take_material/<int:material_id>", methods=["POST"])
def take_material(material_id):
    if "user" not in session:
        return redirect("/")
    material = Material.query.get_or_404(material_id)
    amount = int(request.form.get("amount", 1))
    if amount < 0:
        amount = 0
    if material.quantity > 0:
        material.quantity = max(0, material.quantity - amount)
        db.session.add(MaterialLog(
            project_id=material.project_id,
            material_name=material.name,
            part_number=material.part_number,
            quantity=amount,
            taken_by=session.get("user"),
            action="Taken"
        ))
        db.session.commit()
    return redirect(f"/project/{material.project_id}")


@app.route("/delete_material/<int:material_id>")
def delete_material(material_id):
    if "user" not in session:
        return redirect("/")
    if session.get("role") not in ["Project Lead", "Workshop Manager"]:
        return "Not allowed"
    material = Material.query.get_or_404(material_id)
    db.session.add(MaterialLog(
        project_id=material.project_id,
        material_name=material.name,
        part_number=material.part_number,
        quantity=material.quantity,
        taken_by=session.get("user"),
        action="Deleted"
    ))
    db.session.delete(material)
    db.session.commit()
    return redirect(f"/project/{material.project_id}")


@app.route("/delete_project/<int:project_id>")
def delete_project(project_id):
    if "user" not in session:
        return redirect("/")
    if session.get("role") not in ["Project Lead", "Workshop Manager"]:
        return "Not allowed"
    project = Project.query.get_or_404(project_id)
    # remove materials and log deletion
    for m in project.materials:
        db.session.add(MaterialLog(
            project_id=project.id,
            material_name=m.name,
            part_number=m.part_number,
            quantity=m.quantity,
            taken_by=session.get("user"),
            action="Deleted"
        ))
        db.session.delete(m)
    db.session.delete(project)
    db.session.commit()
    return redirect("/projects")


@app.route("/project/<int:project_id>/logs")
def project_logs(project_id):
    if "user" not in session:
        return redirect("/")
    project = Project.query.get_or_404(project_id)
    logs = MaterialLog.query.filter_by(project_id=project_id)\
        .order_by(MaterialLog.timestamp.desc()).all()
    return render_template(
        "project_logs.html",
        project=project,
        logs=logs,
        role=session.get("role"),
        user=session.get("user")
    )


# PWA assets
@app.route('/manifest.json')
def manifest():
    return send_from_directory('.', 'manifest.json')


@app.route('/service-worker.js')
def service_worker():
    return send_from_directory('.', 'service-worker.js')

if __name__ == "__main__":
    with app.app_context():
        ensure_schema()

    app.run(debug=True)
else:
    # Ensure tables exist when running under WSGI servers like gunicorn
    with app.app_context():
        ensure_schema()
