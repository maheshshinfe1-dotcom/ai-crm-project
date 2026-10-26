import json
import sqlite3

# --- AI EDU-CRM: Phase 3.3 (Full Relational Schema Migration) ---

print("\n>> SYSTEM: Initiating Full Enterprise SQL Migration...")
conn = sqlite3.connect('crm_enterprise.db')
cursor = conn.cursor()

# 1. Define the Relational Database Schema
print(">> SYSTEM: Building full database schema...")
tables = {
    "students": '''CREATE TABLE IF NOT EXISTS students (
        student_id TEXT PRIMARY KEY, name TEXT, phone TEXT, enrolled_course TEXT, 
        sales_owner TEXT, total_fee INTEGER, amount_paid INTEGER, payment_status TEXT)''',
        
    "tasks": '''CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY, client_name TEXT, description TEXT, 
        due_date TEXT, assigned_to TEXT, status TEXT)''',
        
    "opportunities": '''CREATE TABLE IF NOT EXISTS opportunities (
        opp_id TEXT PRIMARY KEY, client_name TEXT, course TEXT, deal_value INTEGER, 
        probability INTEGER, stage TEXT, owner TEXT)''',
        
    "activities": '''CREATE TABLE IF NOT EXISTS activities (
        activity_id TEXT PRIMARY KEY, client_name TEXT, activity_type TEXT, 
        notes TEXT, timestamp TEXT)''',
        
    "tickets": '''CREATE TABLE IF NOT EXISTS tickets (
        ticket_id TEXT PRIMARY KEY, student_name TEXT, issue TEXT, 
        priority TEXT, assigned_to TEXT, status TEXT)'''
}

for table_name, sql_command in tables.items():
    cursor.execute(sql_command)

# 2. Extract and Inject the Data
try:
    with open('crm_database.json', 'r') as file:
        old_data = json.load(file)
        
        print("\n>> SYSTEM: Injecting legacy data into SQL tables...")
        for table_name in tables.keys():
            records = old_data.get(table_name, [])
            migrated = 0
            
            for r in records:
                try:
                    if table_name == "students":
                        cursor.execute("INSERT INTO students VALUES (?,?,?,?,?,?,?,?)", 
                            (r['student_id'], r['name'], r['phone'], r['enrolled_course'], r['sales_owner'], r.get('total_fee', 60000), r.get('amount_paid', 0), r.get('payment_status', 'PENDING')))
                    elif table_name == "tasks":
                        cursor.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?)", 
                            (r['task_id'], r['client_name'], r['description'], r['due_date'], r['assigned_to'], r['status']))
                    elif table_name == "opportunities":
                        cursor.execute("INSERT INTO opportunities VALUES (?,?,?,?,?,?,?)", 
                            (r['opp_id'], r['client_name'], r['course'], r['deal_value'], r['probability'], r['stage'], r['owner']))
                    elif table_name == "activities":
                        cursor.execute("INSERT INTO activities VALUES (?,?,?,?,?)", 
                            (r['activity_id'], r['client_name'], r['activity_type'], r['notes'], r['timestamp']))
                    elif table_name == "tickets":
                        cursor.execute("INSERT INTO tickets VALUES (?,?,?,?,?,?)", 
                            (r['ticket_id'], r['student_name'], r['issue'], r['priority'], r['assigned_to'], r['status']))
                    migrated += 1
                except sqlite3.IntegrityError:
                    pass # Ignore if already migrated
                    
            print(f"✅ {migrated} records migrated into -> {table_name.upper()}")
            
except FileNotFoundError:
    print("❌ Old JSON database not found. Tables created empty.")

conn.commit()
conn.close()
print("\n>> SYSTEM: Full SQL Migration Complete. Vault is secured.\n")