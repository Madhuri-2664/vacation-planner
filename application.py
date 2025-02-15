from flask import Flask, request, make_response, jsonify, render_template, send_file
import io
import cv2
import numpy as np
import qrcode
import pg8000
from PIL import Image
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime

app = Flask(__name__)
CORS(app)  # Enable CORS for cross-origin requests
SECRET_KEY = 'this is secret key jwt creation and validation'

# Database Configuration
DB_HOST = 'localhost'
DB_NAME = 'postgres'
DB_USER = 'postgres'
DB_PASSWORD = 'postgres'

# Database Connection
def get_db_connection():
    connection = pg8000.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return connection

# Ensure Database Tables Exist
def create_users_table_if_not_exists():
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        );
    """)
    connection.commit()
    cursor.close()
    connection.close()

def create_plans_table_if_not_exists():
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            destination TEXT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            activities TEXT,
            notes TEXT,
            reminder TEXT  -- Add this line to include the reminder column
        );
    """)
    connection.commit()
    cursor.close()
    connection.close()

create_users_table_if_not_exists()
create_plans_table_if_not_exists()

# Routes
@app.route('/register', methods=['POST'])
def register():
    username = request.json.get('username')
    email = request.json.get('email')
    password = request.json.get('password')

    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required."}), 400

    hashed_password = generate_password_hash(password)
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO users (username, email, password) VALUES (%s, %s, %s);
        """, (username, email, hashed_password))
        connection.commit()
        cursor.close()
        connection.close()
        return jsonify({"message": "User registered successfully."}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/signin', methods=['POST'])
def signin():
    username = request.json.get('username')
    password = request.json.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    connection = get_db_connection()
    cursor = connection.cursor()
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

    cursor.close()
    connection.close()
    return jsonify({"message": "Signin successful", "token": token})

@app.route('/generate/qr', methods=['POST'])
def generate_qr():
    # Get the data from the request
    data = request.get_json()
    content = data.get('content')

    if not content:
        return jsonify({"error": "No content provided for QR code"}), 400

    # Generate the QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(content)
    qr.make(fit=True)

    img = qr.make_image(fill='black', back_color='white')

    # Save to a bytes buffer
    img_io = io.BytesIO()
    img.save(img_io)
    img_io.seek(0)

    # Return the image as a response
    return send_file(img_io, mimetype='image/png')

@app.route('/destinations/add', methods=['POST'])
def add_plan():
    # Get the data from the incoming JSON request
    data = request.get_json()

    destination = data.get('destination')
    dates = data.get('dates')  # You might need to parse this into start_date and end_date
    activities = data.get('activities')
    notes = data.get('notes')
    reminder = data.get('reminder')

    # Assuming we have the user ID available from the JWT token (authentication needed)
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({"error": "Token is required to create a plan"}), 400

    # Remove "Bearer " if it's present
    if token and token.startswith("Bearer "):
        token = token[7:]  # Remove "Bearer " part

    try:
        # Decode the token to extract the user information (e.g., user_id)
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        user_id = decoded_token['user_id']  # Ensure user_id is in the token
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token has expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401

    if not destination or not dates or not activities or not notes:
        return jsonify({"error": "All required fields must be filled"}), 400

    try:
        # Parse dates if necessary, assuming 'dates' contains both start_date and end_date
        start_date, end_date = dates.split(' to ')  # Adjust as needed

        # Save the plan details to the database
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO plans (user_id, destination, start_date, end_date, activities, notes, reminder)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """, (user_id, destination, start_date, end_date, activities, notes, reminder))
        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({"message": "Vacation plan created successfully!"}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/view/plans', methods=['GET'])
def view_plans():
    token = request.headers.get('Authorization')
    
    if not token:
        return jsonify({"error": "Token is required to view plans"}), 400

    if token.startswith("Bearer "):
        token = token[7:]  # Remove "Bearer " part

    try:
        # Decode the token to extract the user information
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        user_id = decoded_token['user_id']
        print(f"Decoded Token: {decoded_token}")  # Debug line to check decoded token
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token has expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401

    # Query the plans for the user
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT destination, start_date, end_date, activities, notes, reminder
        FROM plans
        WHERE user_id = %s;
    """, (user_id,))
    plans = cursor.fetchall()
    print(f"Plans fetched: {plans}")  # Debug line to check the fetched plans
    cursor.close()
    connection.close()

    # If no plans are found, return a message
    if not plans:
        return jsonify({"message": "No plans found"}), 404

    # Convert the plans to a list of dictionaries
    plans_list = []
    for plan in plans:
        plans_list.append({
            'destination': plan[0],
            'start_date': plan[1],
            'end_date': plan[2],
            'activities': plan[3],
            'notes': plan[4],
            'reminder': plan[5] if plan[5] else None
        })

    # Return the plans as a JSON response
    return jsonify(plans_list), 200



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

if __name__ == '__main__':
    app.run(debug=True)
