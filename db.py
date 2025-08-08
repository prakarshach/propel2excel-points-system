import sqlite3

def connect():
    return sqlite3.connect('p2e.db')

def setup():
    conn = connect()
    c = conn.cursor()
    # Users points table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        points INTEGER DEFAULT 0
    )''')
    # Log each point-earning action
    c.execute('''CREATE TABLE IF NOT EXISTS points_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        action TEXT,
        points INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    # Rewards shop items
    c.execute('''CREATE TABLE IF NOT EXISTS rewards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        cost INTEGER
    )''')
    # Reward redemptions log
    c.execute('''CREATE TABLE IF NOT EXISTS redemptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        reward_id INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    # Suspicious activity tracking
    c.execute('''CREATE TABLE IF NOT EXISTS suspicious_activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        activity_type TEXT,
        details TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    # User warnings and status
    c.execute('''CREATE TABLE IF NOT EXISTS user_status (
        user_id TEXT PRIMARY KEY,
        warnings INTEGER DEFAULT 0,
        points_suspended BOOLEAN DEFAULT FALSE,
        suspension_end DATETIME,
        last_activity DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

# Initialize rewards catalog with sample items if empty
def initialize_rewards():
    conn = connect()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM rewards')
    if c.fetchone()[0] == 0:
        rewards = [
            ("Resume Review", 300),
            ("Mentorship Call", 500),
            ("Exclusive Career Webinar Access", 400),
            ("P2E Hat", 800)
        ]
        c.executemany('INSERT INTO rewards(name, cost) VALUES (?,?)', rewards)
    conn.commit()
    conn.close()
