# attendance_app/management/commands/seed_attendance.py
import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from attendance_app.models import StudentProfile, Subject, Attendance, TeacherProfile

class Command(BaseCommand):
    help = 'Seeds the database with dummy attendance data for all students and subjects.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Deleting old attendance data...")
        Attendance.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("Old data deleted."))

        students = StudentProfile.objects.all()
        today = date.today()
        
        if not students:
            self.stdout.write(self.style.WARNING("No students found. Please create student profiles first."))
            return

        self.stdout.write(f"Found {len(students)} students. Seeding attendance for the last 30 days...")

        for student in students:
            # A student is only linked to subjects they are enrolled in
            enrolled_subjects = student.subjects.all()
            if not enrolled_subjects:
                continue

            for day in range(30): # Generate data for the past 30 days
                current_date = today - timedelta(days=day)
                
                for subject in enrolled_subjects:
                    # Find a teacher for this subject to associate the record with
                    teacher = subject.teachers.first()
                    if not teacher:
                        continue # Skip if no teacher is assigned to this subject
                    
                    # Randomly decide if the student was present or absent
                    status = random.choice(['present', 'present', 'present', 'absent']) # 3:1 ratio

                    # Create the attendance record
                    Attendance.objects.create(
                        student=student,
                        subject=subject,
                        teacher=teacher,
                        date=current_date,
                        status=status
                    )

        self.stdout.write(self.style.SUCCESS('Successfully seeded dummy attendance data.'))