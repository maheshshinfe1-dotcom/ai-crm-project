import hashlib

def hash_password(plain_text_password):
    password_bytes = plain_text_password.encode('utf-8')
    hash_object = hashlib.sha256(password_bytes)
    return hash_object.hexdigest()

# 1. Simulate what is saved inside our SQLite Database when the account was created
saved_database_hash = hash_password("admin")

# 2. Simulate what a user types into the login box right now
user_login_attempt = "admin"
attempt_hash = hash_password(user_login_attempt)

print("Saved DB Hash :", saved_database_hash)
print("Attempted Hash:", attempt_hash)
print("--------------------------------------------------")

# 3. Compare the two hashes using ==
if attempt_hash == saved_database_hash:
    print("✅ LOGIN SUCCESS: Hashes match! Welcome to the CRM.")
else:
    print("❌ ACCESS DENIED: Hashes do not match! Invalid password.")