# TO RUN: python manage.py seed_subjects

from django.core.management.base import BaseCommand
from attendance_app.models import Subject

class Command(BaseCommand):
    help = 'Bulk inserts subjects into the database without duplicates.'

    def handle(self, *args, **kwargs):
        # --- EDIT THIS LIST TO ADD NEW SUBJECTS ---
        SUBJECTS_LIST = [
            "Deep learning",
            "Big data analytics & visualisation",
            "Design thinking",
            "Mobile computing",
            "Software testing and quality assurance",
            "Core java",
            "Green computing",
            "DSA",
            "AI ML",
            "Advance web tech",
            "Networking with linux"
        ]
        # ------------------------------------------

        self.stdout.write("Starting bulk subject insert...")
        created_count = 0
        existing_count = 0

        for subject_name in SUBJECTS_LIST:
            # Clean up the name (trim whitespace)
            clean_name = subject_name.strip()
            
            # get_or_create checks if it exists; if not, it creates it.
            obj, created = Subject.objects.get_or_create(name=clean_name)

            if created:
                self.stdout.write(self.style.SUCCESS(f"Created: {clean_name}"))
                created_count += 1
            else:
                self.stdout.write(f"Skipped (Exists): {clean_name}")
                existing_count += 1

        self.stdout.write(self.style.SUCCESS(f"\nProcess Complete."))
        self.stdout.write(f"New Subjects Added: {created_count}")
        self.stdout.write(f"Existing Subjects Skipped: {existing_count}")