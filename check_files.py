import os
import sys
import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()
cursor.execute("SELECT app_id, english_certificate, passport FROM applications LIMIT 1")
result = cursor.fetchone()
if result:
    print(f"App ID: {result[0]}")
    print(f"English Certificate Path: {result[1]}")
    print(f"Passport Path: {result[2]}")
else:
    print("No applications found")
conn.close()
