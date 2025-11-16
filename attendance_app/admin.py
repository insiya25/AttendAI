# attendance_app/admin.py

from django.contrib import admin
from .models import User, Subject, StudentProfile, TeacherProfile, Attendance, UserSkill, UserProject, Performance

# Register your models here to make them accessible in the admin panel.
admin.site.register(User)
admin.site.register(Subject)
admin.site.register(StudentProfile)
admin.site.register(TeacherProfile)
admin.site.register(Attendance)
admin.site.register(UserSkill)
admin.site.register(UserProject)
admin.site.register(Performance)