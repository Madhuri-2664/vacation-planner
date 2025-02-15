from flask import Flask, request, jsonify, render_template, send_file
import io
import qrcode
import pg8000
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from contextlib import closing

# Flask Application Setup
app = Flask(__name__)
CORS(app)
SECRET_KEY = 'this is secret key jwt creation and validation'

# Database Configuration
DB_HOST = 'localhost'
DB_NAME = 'postgres'
DB_USER = 'postgres'
DB_PASSWORD = 'postgres'

# Utility: Database Connection
def get_db_connection():
    return pg8000.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

# Utility: Ensure Database Tables Exist
def create_tables():
    connection = get_db_connection()
    with closing(connection.cursor()) as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                destination TEXT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                activities TEXT,
                notes TEXT,
                reminder TEXT
            );
        """)
        connection.commit()

create_tables()

# Utility: Decode Token
def decode_token(token):
    try:
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return decoded_token['user_id'], None
    except jwt.ExpiredSignatureError:
        return None, {"error": "Token has expired"}, 401
    except jwt.InvalidTokenError:
        return None, {"error": "Invalid token"}, 401

# 1. User Authentication Routes

# Register User
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required."}), 400

    hashed_password = generate_password_hash(password)
    try:
        connection = get_db_connection()
        with closing(connection.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO users (username, email, password) VALUES (%s, %s, %s);
            """, (username, email, hashed_password))
            connection.commit()
        return jsonify({"message": "User registered successfully."}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Signin User
@app.route('/signin', methods=['POST'])
def signin():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    connection = get_db_connection()
    with closing(connection.cursor()) as cursor:
        cursor.execute("""
            SELECT id, password FROM users WHERE username = %s;
        """, (username,))
        user = cursor.fetchone()

    if not user or not check_password_hash(user[1], password):
        return jsonify({"error": "Invalid credentials"}), 401

    expiration_time = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    token = jwt.encode(
        {'user_id': user[0], 'username': username, 'exp': expiration_time},
        SECRET_KEY,
        algorithm='HS256'
    )
    return jsonify({"message": "Signin successful", "token": token})

# 2. Vacation Plan Routes

# Add Plan
@app.route('/destinations/add', methods=['POST'])
def add_plan():
    data = request.json
    destination = data.get('destination')
    dates = data.get('dates')
    activities = data.get('activities')
    notes = data.get('notes')
    reminder = data.get('reminder')

    token = request.headers.get('Authorization')
    if not token:
        return jsonify({"error": "Token is required to create a plan"}), 400

    if token.startswith("Bearer "):
        token = token[7:]

    user_id, error = decode_token(token)
    if error:
        return jsonify(error), error[1]

    if not destination or not dates or not activities or not notes:
        return jsonify({"error": "All required fields must be filled"}), 400

    try:
        start_date, end_date = dates.split(' to ')

        connection = get_db_connection()
        with closing(connection.cursor()) as cursor:
            cursor.execute("""
                INSERT INTO plans (user_id, destination, start_date, end_date, activities, notes, reminder)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
            """, (user_id, destination, start_date, end_date, activities, notes, reminder))
            connection.commit()
        return jsonify({"message": "Vacation plan created successfully!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# View Plans
@app.route('/view/plans', methods=['GET'])
def view_plans():
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({"error": "Token is required to view plans"}), 400

    if token.startswith("Bearer "):
        token = token[7:]

    user_id, error = decode_token(token)
    if error:
        return jsonify(error), error[1]

    connection = get_db_connection()
    with closing(connection.cursor()) as cursor:
        cursor.execute("""
            SELECT id, destination, start_date, end_date, activities, notes, reminder
            FROM plans
            WHERE user_id = %s;
        """, (user_id,))
        plans = cursor.fetchall()

    if not plans:
        return jsonify({"message": "No plans found"}), 404

    plans_list = [
        {
            'id': plan[0],
            'destination': plan[1],
            'start_date': plan[2],
            'end_date': plan[3],
            'activities': plan[4],
            'notes': plan[5],
            'reminder': plan[6]
        }
        for plan in plans
    ]
    return jsonify(plans_list), 200

# Update Plan
@app.route('/update/plan/<int:plan_id>', methods=['PUT'])
def update_plan(plan_id):
    data = request.json
    destination = data.get('destination')
    dates = data.get('dates')
    activities = data.get('activities')
    notes = data.get('notes')
    reminder = data.get('reminder')

    token = request.headers.get('Authorization')
    if not token:
        return jsonify({"error": "Token is required to update a plan"}), 400

    if token.startswith("Bearer "):
        token = token[7:]

    user_id, error = decode_token(token)
    if error:
        return jsonify(error), error[1]

    if not destination or not dates or not activities or not notes:
        return jsonify({"error": "All required fields must be filled"}), 400

    try:
        start_date, end_date = dates.split(' to ')

        connection = get_db_connection()
        with closing(connection.cursor()) as cursor:
            cursor.execute("""
                UPDATE plans
                SET destination = %s, start_date = %s, end_date = %s, activities = %s, notes = %s, reminder = %s
                WHERE id = %s AND user_id = %s;
            """, (destination, start_date, end_date, activities, notes, reminder, plan_id, user_id))
            connection.commit()

            # Check if any row was updated
            if cursor.rowcount == 0:
                return jsonify({"error": "Plan not found or not owned by user"}), 404

        return jsonify({"message": "Vacation plan updated successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Delete Plan
@app.route('/delete/plan/<int:plan_id>', methods=['DELETE'])
def delete_plan(plan_id):
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({"error": "Token is required"}), 400

    if token.startswith("Bearer "):
        token = token[7:]

    user_id, error = decode_token(token)
    if error:
        return jsonify(error), error[1]

    try:
        connection = get_db_connection()
        with closing(connection.cursor()) as cursor:
            cursor.execute("""
                DELETE FROM plans WHERE id = %s AND user_id = %s;
            """, (plan_id, user_id))
            connection.commit()
        return jsonify({"message": "Plan deleted successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 3. QR Code Route
# 3. QR Code Route
@app.route('/generate/qr', methods=['POST'])
def generate_qr():
    data = request.json
    content = data.get('content')

    if not content:
        return jsonify({"error": "No content provided for QR code"}), 400

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(content)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')

    img_io = io.BytesIO()
    img.save(img_io, format="PNG")
    img_io.seek(0)

    return send_file(
        img_io,
        mimetype='image/png',
        as_attachment=True,  # This makes the file downloadable
        download_name="qrcode.png"  # Sets the file name when downloading
    )


# 4. Template Routes
@app.route('/create')
def create_page():
    return render_template('create_plan.html')

@app.route('/view')
def view_page():
    return render_template('view.html')

@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/signin')
def signin_page():
    return render_template('signin.html')

@app.route('/home')
def home_page():
    return render_template('home.html')

@app.route('/')
def open_page():
    return render_template('index.html')

# Run the Application
if __name__ == '__main__':
    app.run(debug=True)
