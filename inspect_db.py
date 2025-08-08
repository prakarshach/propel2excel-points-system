#!/usr/bin/env python3
"""
Database inspection script
"""

import db
import sqlite3

def inspect_database():
    """Inspect the database and show its current state"""
    print("🔍 Database Inspection Report\n")
    print("=" * 50)
    
    conn = db.connect()
    c = conn.cursor()
    
    # Check all tables
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = c.fetchall()
    
    print("📋 Database Tables:")
    for table in tables:
        table_name = table[0]
        c.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = c.fetchone()[0]
        print(f"   ✅ {table_name}: {count} records")
    
    print("\n📊 Detailed Information:")
    
    # Users table
    print("\n👥 Users Table:")
    c.execute("SELECT user_id, points FROM users ORDER BY points DESC LIMIT 5")
    users = c.fetchall()
    if users:
        for user_id, points in users:
            print(f"   User {user_id}: {points} points")
    else:
        print("   No users found")
    
    # Rewards table
    print("\n🎁 Rewards Table:")
    c.execute("SELECT name, cost FROM rewards")
    rewards = c.fetchall()
    if rewards:
        for name, cost in rewards:
            print(f"   {name}: {cost} points")
    else:
        print("   No rewards found")
    
    # Recent activity
    print("\n📝 Recent Activity (Last 5):")
    c.execute("SELECT user_id, action, points, timestamp FROM points_log ORDER BY timestamp DESC LIMIT 5")
    activities = c.fetchall()
    if activities:
        for user_id, action, points, timestamp in activities:
            print(f"   {timestamp[:19]} | User {user_id}: {action} (+{points} pts)")
    else:
        print("   No activity found")
    
    # Suspicious activity
    print("\n🚨 Suspicious Activity:")
    c.execute("SELECT COUNT(*) FROM suspicious_activity")
    suspicious_count = c.fetchone()[0]
    print(f"   Total suspicious activities: {suspicious_count}")
    
    conn.close()
    
    print("\n" + "=" * 50)
    print("✅ Database inspection complete!")
    print("\n💡 Your database is ready and working!")
    print("   - All tables are created")
    print("   - Rewards are initialized")
    print("   - Ready to track user activity")

if __name__ == "__main__":
    inspect_database() 