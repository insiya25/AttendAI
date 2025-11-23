# RUN WITH:
# Replace 27 with your actual student user ID
# python manage.py seed_student_attendance 27


import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from attendance_app.models import StudentProfile, Attendance, TeacherProfile, User

class Command(BaseCommand):
    help = 'Seeds attendance data for a specific student for the last 2 months.'

    def add_arguments(self, parser):
        parser.add_argument('user_id', type=int, help='The User ID of the student')

    def handle(self, *args, **options):
        user_id = options['user_id']

        try:
            # 1. Fetch the Student
            student = StudentProfile.objects.get(user_id=user_id)
            self.stdout.write(f"Found Student: {student.full_name} (Roll: {student.roll_number})")

            # 2. Fetch Enrolled Subjects
            enrolled_subjects = student.subjects.all()
            if not enrolled_subjects.exists():
                self.stdout.write(self.style.WARNING("This student is not enrolled in any subjects. Please add subjects to their profile first."))
                return

            # 3. Clear Previous Data
            # We delete ALL attendance for this student to ensure a clean slate/refresh
            deleted_count, _ = Attendance.objects.filter(student=student).delete()
            self.stdout.write(self.style.WARNING(f"Cleared {deleted_count} existing attendance records."))

            # 4. Generate New Data
            today = date.today()
            start_date = today - timedelta(days=60) # Past 2 months
            records_created = 0

            # Get a fallback teacher just in case a subject has no teacher assigned
            # (Needed because the Attendance model requires a teacher field)
            fallback_teacher = TeacherProfile.objects.first()
            
            if not fallback_teacher:
                 self.stdout.write(self.style.ERROR("Error: No teachers exist in the database. Create a teacher account first."))
                 return

            self.stdout.write(f"Generating data from {start_date} to {today}...")

            # Loop through every day in the range
            delta = timedelta(days=1)
            current_date = start_date
            
            while current_date <= today:
                # Skip Sundays (0=Monday, 6=Sunday)
                if current_date.weekday() != 6: 
                    for subject in enrolled_subjects:
                        # Logic: Try to get a teacher teaching this specific subject. 
                        # If none, use the fallback teacher to ensure data is created.
                        teacher = subject.teachers.first() or fallback_teacher

                        # Randomly determine status (80% chance of being present)
                        # You can tweak weights=[0.8, 0.2] to change attendance ratio
                        status = random.choices(['present', 'absent'], weights=[0.8, 0.2], k=1)[0]

                        Attendance.objects.create(
                            student=student,
                            subject=subject,
                            teacher=teacher,
                            date=current_date,
                            status=status
                        )
                        records_created += 1
                
                current_date += delta

            self.stdout.write(self.style.SUCCESS(f"Successfully created {records_created} attendance records for {student.full_name} across {enrolled_subjects.count()} subjects."))

        except StudentProfile.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Student with User ID {user_id} not found."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred: {str(e)}"))