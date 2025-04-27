import sqlite3
import hashlib


conn = sqlite3.connect('users.db')
c = conn.cursor()


c.execute('''
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL
)
''')


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


users = [
    ('admin', hash_password('admin123'), 'admin'),
    ('user', hash_password('user123'), 'user')
]

for username, password_hash, role in users:
    try:
        c.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)', (username, password_hash, role))
    except sqlite3.IntegrityError:
        print(f"User {username} already exists, skipping.")

conn.commit()
conn.close()

print("Database and users created successfully!")