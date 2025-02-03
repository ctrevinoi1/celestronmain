from flask import Flask, send_from_directory

app = Flask(__name__, static_folder='static')

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=8080)