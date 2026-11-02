import json
import sqlite3

# --- AI EDU-CRM: Phase 3.1 (Database Migration Engine) ---

print("\n>> SYSTEM: Initiating Enterprise SQL Migration...")

# 1. Connect to new SQL database (This creates a .db file automatically)
conn = sqlite3.connect('crm_enterprise.db')
cursor = conn.cursor()

# 2. Execute SQL commands to create strict, structured Tables
print(">> SYSTEM: Building relational SQL tables...")
cursor.execute('''
CREATE TABLE IF NOT EXISTS leads (
    lead_id TEXT PRIMARY KEY,
    name TEXT,
    phone TEXT UNIQUE,
    course TEXT,
    source TEXT,
    assigned_to TEXT,
    status TEXT,
    score INTEGER,
    grade TEXT
)
''')

# 3. Extract data from the old JSON architecture
try:
    with open('crm_database.json', 'r') as file:
        old_data = json.load(file)
        leads = old_data.get('leads', [])
        
        # 4. Inject (Migrate) the data into the new SQL table
        print(">> SYSTEM: Migrating lead records to SQL...")
        migrated_count = 0
        
        for lead in leads:
            try:
                # The SQL INSERT statement
                cursor.execute('''
                INSERT INTO leads (lead_id, name, phone, course, source, assigned_to, status, score, grade)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    lead.get('lead_id'), 
                    lead.get('name'), 
                    lead.get('phone'),
                    lead.get('course'), 
                    lead.get('source'), 
                    lead.get('assigned_to'),
                    lead.get('status'), 
                    lead.get('score', 0), 
                    lead.get('grade', 'COLD')
                ))
                migrated_count += 1
            except sqlite3.IntegrityError:
                # If a duplicate phone number exists, SQL's "UNIQUE" rule blocks it instantly!
                print(f"   [!] Skipped {lead.get('name')} (Duplicate primary key detected)")
                
        print(f"✅ Success! {migrated_count} leads permanently migrated into SQL.")
        
except FileNotFoundError:
    print("❌ Old JSON database not found. Starting with a blank SQL database.")

# 5. Commit the transaction and close the vault
conn.commit()
conn.close()
print(">> SYSTEM: Migration Complete. 'crm_enterprise.db' is ready for production.\n")