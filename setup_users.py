import sqlite3
import hashlib

# 1. Our SHA-256 Password Hashing Function
def hash_password(plain_text_password):
    password_bytes = plain_text_password.encode('utf-8')
    return hashlib.sha256(password_bytes).hexdigest()

# 2. Connect to our existing CRM SQLite Database
conn = sqlite3.connect('crm_enterprise.db')
cursor = conn.cursor()

# 3. Create the 'users' table if it doesn't exist yet
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL
    )
''')

# 4. Helper function to safely create a user account
def create_user(username, plain_password, role):
    hashed_pw = hash_password(plain_password)
    try:
        # Using (?, ?, ?) parameterized query to prevent SQL Injection
        cursor.execute('''
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
        ''', (username, hashed_pw, role))
        conn.commit()
        print(f"✅ Created user '{username}' with role [{role}]")
    except sqlite3.IntegrityError:
        print(f"⚠️ User '{username}' already exists in the database! Skipping.")

# 5. Create our initial CRM staff accounts
print("--- Setting up CRM Users ---")
create_user("admin", "admin123", "ADMIN")
create_user("counselor1", "pass123", "COUNSELOR")
create_user("rahul", "welcome123", "COUNSELOR")

# 6. Verify by reading all users back from the database
print("\n--- Current Users in Database (crm_enterprise.db) ---")
cursor.execute("SELECT user_id, username, role, password_hash FROM users")
all_users = cursor.fetchall()

for user in all_users:
    # Print user_id, username, role, and the first 15 characters of the hash
    print(f"ID: {user[0]} | Username: {user[1]} | Role: {user[2]} | Hash: {user[3][:15]}...")

conn.close()