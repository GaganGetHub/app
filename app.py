import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Replace with a secure key in production

# Use absolute path for database file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'project.db')

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.mkdir(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize Database
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
      CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT UNIQUE NOT NULL,
          password TEXT NOT NULL,
          role TEXT NOT NULL
      )
    ''')
    c.execute("SELECT * FROM users WHERE username='gagan'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role) VALUES ('gagan', 'gagan123', 'admin')")
    c.execute("SELECT * FROM users WHERE username='student'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role) VALUES ('student', 'student123', 'student')")

    c.execute('''
      CREATE TABLE IF NOT EXISTS projects (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          team_name TEXT,
          members TEXT,
          supervisor TEXT,
          project_title TEXT
      )
    ''')
    
    # Add reports table
    c.execute('''
      CREATE TABLE IF NOT EXISTS reports (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          project_id INTEGER,
          filename TEXT,
          upload_date TEXT,
          FOREIGN KEY(project_id) REFERENCES projects(id)
      )
    ''')
    
    # Add evaluation table
    c.execute('''
      CREATE TABLE IF NOT EXISTS evaluation (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          project_id INTEGER,
          evaluator TEXT,
          score INTEGER,
          feedback TEXT,
          FOREIGN KEY(project_id) REFERENCES projects(id)
      )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Login required decorator
def login_required(role):
    def wrapper(func):
        def decorated_view(*args, **kwargs):
            if 'username' not in session or 'role' not in session:
                flash("Login required.")
                return redirect(url_for('login_page'))
            if session['role'] != role:
                flash("Access denied.")
                return redirect(url_for('login_page'))
            return func(*args, **kwargs)
        decorated_view.__name__ = func.__name__
        return decorated_view
    return wrapper

@app.route('/')
def login_page():
    if 'username' in session:
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('student_home'))
    return render_template('login.html', active='login')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = c.fetchone()
    conn.close()
    
    if user:
        session['username'] = user[1]
        session['role'] = user[3]
        flash(f"Welcome, {user[1]}!")
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('student_home'))
    else:
        flash("Invalid username or password.")
        return redirect(url_for('login_page'))

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect(url_for('login_page'))

@app.route('/student_home')
@login_required('student')
def student_home():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT * FROM projects")
    projects = c.fetchall()
    
    # Fetch evaluations for each project
    evaluations = {}
    for project in projects:
        project_id = project[0]
        c.execute("SELECT * FROM evaluation WHERE project_id=?", (project_id,))
        evaluations[project_id] = c.fetchall()  # List of (id, project_id, evaluator, score, feedback)
    
    conn.close()
    return render_template('student_home.html', projects=projects, evaluations=evaluations, active='home')

@app.route('/register_team', methods=['GET', 'POST'])
@login_required('student')
def register_team():
    if request.method == 'POST':
        team_name = request.form.get('team_name')
        members = request.form.get('members')
        supervisor = request.form.get('supervisor')
        project_title = request.form.get('project_title')
        
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("INSERT INTO projects (team_name, members, supervisor, project_title) VALUES (?, ?, ?, ?)",
                  (team_name, members, supervisor, project_title))
        conn.commit()
        conn.close()
        
        flash('Team registered successfully!')
        return redirect(url_for('student_home'))
    return render_template('register_team.html', active='register')

@app.route('/submit_report/<int:project_id>', methods=['GET', 'POST'])
@login_required('student')
def submit_report(project_id):
    if request.method == 'POST':
        if 'report_file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['report_file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            upload_date = request.form.get('upload_date')
            
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute("INSERT INTO reports (project_id, filename, upload_date) VALUES (?, ?, ?)",
                      (project_id, filename, upload_date))
            conn.commit()
            conn.close()
            flash("Report submitted successfully!")
            return redirect(url_for('student_home'))
    return render_template('submit_report.html', project_id=project_id, active='submit')

@app.route('/admin_dashboard')
@login_required('admin')
def admin_dashboard():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT * FROM projects")
    projects = c.fetchall()
    c.execute("SELECT * FROM reports")
    reports = c.fetchall()
    conn.close()
    return render_template('admin_home.html', projects=projects, reports=reports, active='home')

@app.route('/view_reports/<int:project_id>')
@login_required('admin')
def view_reports(project_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT * FROM reports WHERE project_id=?", (project_id,))
    reports = c.fetchall()
    conn.close()
    return render_template('view_reports.html', reports=reports, project_id=project_id, active='view')

@app.route('/evaluate/<int:project_id>', methods=['GET', 'POST'])
@login_required('admin')
def evaluate(project_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    if request.method == 'POST':
        evaluator = session.get('username')
        score = request.form.get('score')
        feedback = request.form.get('feedback')
        c.execute("INSERT INTO evaluation (project_id, evaluator, score, feedback) VALUES (?, ?, ?, ?)",
                  (project_id, evaluator, score, feedback))
        conn.commit()
        conn.close()
        flash("Evaluation submitted successfully!")
        return redirect(url_for('admin_dashboard'))

    c.execute("SELECT * FROM evaluation WHERE project_id=?", (project_id,))
    evaluations = c.fetchall()
    conn.close()
    return render_template('evaluation.html', evaluations=evaluations, project_id=project_id, active='evaluate')

@app.route('/reset_evaluations/<int:project_id>', methods=['POST'])
@login_required('admin')
def reset_evaluations(project_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("DELETE FROM evaluation WHERE project_id=?", (project_id,))
    conn.commit()
    conn.close()
    flash("Evaluations reset successfully!")
    return redirect(url_for('evaluate', project_id=project_id))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/delete_project/<int:project_id>', methods=['POST'])
@login_required('admin')
def delete_project(project_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    # Delete related evaluations first (due to foreign key)
    c.execute("DELETE FROM evaluation WHERE project_id=?", (project_id,))
    # Delete related reports
    c.execute("DELETE FROM reports WHERE project_id=?", (project_id,))
    # Delete the project
    c.execute("DELETE FROM projects WHERE id=?", (project_id,))
    conn.commit()
    conn.close()
    flash("Project and related data deleted successfully!")
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)