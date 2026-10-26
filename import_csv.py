import csv
import sqlite3
import random

# Reuse our scoring logic from main.py
def calculate_lead_score(phone, source, course):
    score = 20
    if len(phone) >= 10: score += 25
    if 'referral' in source.lower() or 'google' in source.lower(): score += 25
    elif 'instagram' in source.lower(): score += 15
    else: score += 10
    if course: score += 20
    return score

def get_lead_grade(score):
    if score >= 65: return "HOT 🔥"
    elif score >= 40: return "WARM ☀️"
    else: return "COLD ❄"

def import_leads_from_csv(filename):
    print(f"📂 Opening {filename}...")
    
    # 1. Connect to our database
    conn = sqlite3.connect('crm_enterprise.db')
    cursor = conn.cursor()
    
    success_count = 0
    duplicate_count = 0

    # 2. Open and read the CSV file
    with open(filename, mode='r', encoding='utf-8') as file:
        csv_reader = csv.DictReader(file) # This automatically reads row 1 as column names!
        
        for row in csv_reader:
            name = row['name']
            phone = row['phone']
            course = row['course']
            source = row['source']
            
            # Generate ID and calculate AI scores
            lead_id = f"L-{random.randint(10000, 99999)}"
            score = calculate_lead_score(phone, source, course)
            grade = get_lead_grade(score)
            
            try:
                # 3. Insert into the database
                cursor.execute('''
                    INSERT INTO leads (lead_id, name, phone, course, source, assigned_to, status, score, grade) 
                    VALUES (?,?,?,?,?,?,?,?,?)
                ''', (lead_id, name, phone, course, source, 'admin', 'NEW', score, grade))
                success_count += 1
                print(f"✅ Imported: {name} ({grade})")
            except sqlite3.IntegrityError:
                duplicate_count += 1
                print(f"⚠️ Skipped: {name} (Phone {phone} already exists)")

    # Save changes and close
    conn.commit()
    conn.close()
    
    print("\n📊 --- IMPORT SUMMARY ---")
    print(f"Successfully added : {success_count} leads")
    print(f"Skipped duplicates : {duplicate_count} leads")

# Run the function
import_leads_from_csv('bulk_leads.csv')