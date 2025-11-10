from django.db import models
from django.contrib.auth.models import AbstractUser

# We extend the default Django User model to include a role.
class User(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, null=True, blank=True)

class Subject(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    full_name = models.CharField(max_length=255)
    photo = models.ImageField(upload_to='teacher_photos/', null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    subjects = models.ManyToManyField(Subject, related_name='teachers')

    def __str__(self):
        return self.full_name

class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    full_name = models.CharField(max_length=255)
    photo = models.ImageField(upload_to='student_photos/', null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    class_name = models.CharField(max_length=255, blank=True) # "class" is a reserved keyword
    roll_number = models.CharField(max_length=255, unique=True)
    subjects = models.ManyToManyField(Subject, related_name='students')

    def __str__(self):
        return self.full_name

class Attendance(models.Model):
    STATUS_CHOICES = (
        ('present', 'Present'),
        ('absent', 'Absent'),
    )
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE)
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # A student can only have one attendance record per subject per day
        unique_together = ('student', 'subject', 'date')