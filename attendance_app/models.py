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

    email = models.EmailField(max_length=255, blank=True, null=True)

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

    email = models.EmailField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return self.full_name

class UserSkill(models.Model):
    student_profile = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="skills")
    skill_name = models.CharField(max_length=100)
    verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.student_profile.full_name} - {self.skill_name}"
    
class UserProject(models.Model):
    SEMESTER_CHOICES = [(i, f'Semester {i}') for i in range(1, 9)]

    student_profile = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="projects")
    project_name = models.CharField(max_length=200)
    semester = models.IntegerField(choices=SEMESTER_CHOICES)
    description = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.student_profile.full_name} - {self.project_name}"
    

class Performance(models.Model):
    SEMESTER_CHOICES = [(i, f'Semester {i}') for i in range(1, 9)]

    student_profile = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="performance_records")
    semester = models.IntegerField(choices=SEMESTER_CHOICES)
    cgpi = models.DecimalField(max_digits=4, decimal_places=2)
    status = models.CharField(max_length=10, choices=[('pass', 'Pass'), ('fail', 'Fail')])
    
    class Meta:
        unique_together = ('student_profile', 'semester') # A student can only have one record per semester
        ordering = ['semester']

    def __str__(self):
        return f"{self.student_profile.full_name} - Sem {self.semester}: {self.cgpi}"

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


class Approval(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='approval_requests')
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='approvals_received') # Primary recipient
    cc_teachers = models.ManyToManyField(TeacherProfile, related_name='approvals_cced', blank=True)
    subject = models.CharField(max_length=255)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.subject} - {self.student.full_name}"

class StudentFace(models.Model):
    student = models.OneToOneField(StudentProfile, on_delete=models.CASCADE, related_name='face_data')
    # We store the 128-dimension encoding as a JSON text string
    face_encoding = models.TextField() 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Face Data: {self.student.full_name}"