from django.core.management.base import BaseCommand
from attendance_app.models import User, StudentProfile, Subject

class Command(BaseCommand):
    help = 'Seeds the database with real students from the image'

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding Real Students...")

        # Data derived from your image
        real_students = [
            ("25MCA-31", "Khan Mohammad Adnan Salahuddin"),
            ("25MCA-32", "Khan Ahsan Mohammad Shakeel"),
            ("25MCA-33", "Khan Tabish Mujeeb"),
            ("25MCA-34", "Khandagale Parth Rajendra"),
            ("25MCA-35", "Mall Roshni Hemant"),
            ("25MCA-36", "Meher Jinyasa Shyam"),
            ("25MCA-37", "Mehra Gursevak Singh"),
            ("25MCA-38", "Mudaliar Pratik Sugukumar"),
            ("25MCA-39", "Musale Yashraj Dilip"),
            ("25MCA-40", "Niwate Aryan Atish"),
            ("25MCA-41", "Pandya Heet Shailesh"),
            ("25MCA-42", "Patel Nilesh Prem"),
            ("25MCA-43", "Patil Atharva Avinash"),
            ("25MCA-44", "Patil Kalyani Jitendra"),
            ("25MCA-45", "Patil Sahil Kishor"),
            ("25MCA-46", "Patil Shiv Mangesh"),
            ("25MCA-47", "Patil Veer Manish"),
            ("25MCA-48", "Singh Shivesh Pramodkumar"),
            ("25MCA-49", "Raul Debasis Vijaykumar"),
            ("25MCA-50", "Sakpal Soham Sudhir"),
            # Add more if needed...
        ]

        # Ensure a subject exists
        subject, _ = Subject.objects.get_or_create(name="Computer Science")

        for roll, name in real_students:
            # Create or Get User
            username = roll.lower()
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'role': 'student'}
            )
            if created:
                user.set_password('password123')
                user.save()

            # Create or Update Profile
            profile, _ = StudentProfile.objects.update_or_create(
                user=user,
                defaults={
                    'full_name': name,
                    'roll_number': roll, # Exact format 25MCA-31
                    'class_name': 'MCA-1'
                }
            )
            
            # Enroll in subject
            profile.subjects.add(subject)
            
            self.stdout.write(f"Processed: {roll} - {name}")

        self.stdout.write(self.style.SUCCESS('Successfully seeded students matching the physical sheet!'))