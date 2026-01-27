#!/usr/bin/env python3
"""
Migration script to add volume and volume_impact columns to the alert table.
Run this if you have an existing database and want to add the new columns.
"""
import sqlite3
import sys
import os

DB_PATH = "polymarket_tracker.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found. No migration needed.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(alert)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'volume' in columns and 'volume_impact' in columns:
            print("Migration already applied. Columns 'volume' and 'volume_impact' already exist.")
            return
        
        # Add new columns
        print("Adding 'volume' column...")
        cursor.execute("ALTER TABLE alert ADD COLUMN volume REAL")
        
        print("Adding 'volume_impact' column...")
        cursor.execute("ALTER TABLE alert ADD COLUMN volume_impact REAL")
        
        conn.commit()
        print("Migration completed successfully!")
        
    except sqlite3.Error as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
