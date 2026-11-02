# 1. THE DATA: Our lists of students and available courses
courses = ["Python", "JavaScript", "SQL"]
crm_students = ["Satyam", "Amit", "Priya", "Rahul"]

# 2. THE AUTOMATION: Looping through the list to take action
print("--- CRM Automated Course Assignment ---")

for student in crm_students:
    print(f"Sending enrollment email to: {student}")
    print(f"Assigned course: {courses[1]}") # This grabs "JavaScript"
    print("---------------------------------")