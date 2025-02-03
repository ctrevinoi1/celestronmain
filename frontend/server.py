from flask import Flask, send_from_directory, render_template, redirect, url_for, request, session

app = Flask(__name__, static_folder='static')

# Set secret key for session management (use a secure random key in production)
app.secret_key = 'super_secret_key'
ACCESS_PASSWORD = 'password123'  # Change this to your desired access code

# Only allow access to login and static files if not logged in
@app.before_request
def require_login():
    if request.endpoint not in ('login', 'static') and not session.get('authenticated'):
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        password_input = request.form.get('password')
        if password_input == ACCESS_PASSWORD:
            session['authenticated'] = True
            return redirect(url_for('index'))
        else:
            error = "Incorrect access code. Please try again."
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    # Since we already checked authentication, serve the main dashboard page.
    return send_from_directory('static', 'index.html')

if __name__ == '__main__':
    # 0.0.0.0 makes it accessible on the public interface (assuming firewall rules allow it)
    app.run(debug=True, host="0.0.0.0", port=8080)