# attendance_app/serializers.py

from rest_framework import serializers
from .models import User, StudentProfile, TeacherProfile, Subject, Attendance
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name']

class StudentProfileSerializer(serializers.ModelSerializer):
    # We use the SubjectSerializer to show the full subject details, not just the ID
    subjects = SubjectSerializer(many=True, read_only=True)
    # We'll handle subject updates using a list of IDs from the frontend
    subject_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = StudentProfile
        # 'user' is excluded because it's linked automatically
        fields = ['username', 'full_name', 'photo', 'age', 'class_name', 'roll_number', 'subjects', 'subject_ids']
        read_only_fields = ['roll_number', 'username'] # Roll number is usually assigned, not changed

    def update(self, instance, validated_data):
        # Handle the subject_ids to update the many-to-many relationship
        if 'subject_ids' in validated_data:
            subject_ids = validated_data.pop('subject_ids')
            instance.subjects.set(subject_ids)

        # Standard update for other fields
        return super().update(instance, validated_data)


class TeacherProfileSerializer(serializers.ModelSerializer):
    subjects = SubjectSerializer(many=True, read_only=True)
    subject_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = TeacherProfile
        fields = ['username', 'full_name', 'photo', 'age', 'subjects', 'subject_ids']
        read_only_fields = ['username']

    def update(self, instance, validated_data):
        if 'subject_ids' in validated_data:
            subject_ids = validated_data.pop('subject_ids')
            instance.subjects.set(subject_ids)
        return super().update(instance, validated_data)

class RegisterSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, write_only=True)
    full_name = serializers.CharField(write_only=True)
    # Student-specific fields
    class_name = serializers.CharField(required=False, allow_blank=True, write_only=True)
    roll_number = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = User
        fields = ['username', 'password', 'role', 'full_name', 'class_name', 'roll_number']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        role = validated_data.pop('role')
        full_name = validated_data.pop('full_name')
        class_name = validated_data.pop('class_name', None)
        roll_number = validated_data.pop('roll_number', None)

        # Create the user instance
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            role=role
        )

        # Create the corresponding profile
        if role == 'student':
            if not roll_number:
                 raise serializers.ValidationError({'roll_number': 'This field is required for students.'})
            StudentProfile.objects.create(
                user=user,
                full_name=full_name,
                class_name=class_name,
                roll_number=roll_number
            )
        elif role == 'teacher':
            TeacherProfile.objects.create(user=user, full_name=full_name)

        return user  

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims
        token['username'] = user.username
        token['role'] = user.role
        # ...

        return token


# A simplified serializer for listing students in the dashboard
class StudentListSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = ['full_name', 'roll_number', 'photo']


# A serializer for subjects that includes the list of enrolled students
class SubjectWithStudentsSerializer(serializers.ModelSerializer):
    # 'students' is the related_name we set in the StudentProfile model
    students = StudentListSerializer(many=True, read_only=True)

    class Meta:
        model = Subject
        fields = ['id', 'name', 'students']


# The main serializer for the teacher's dashboard
class TeacherDashboardSerializer(serializers.ModelSerializer):
    # 'subjects' is the M2M field in the TeacherProfile model
    # We use our new custom serializer to represent the subjects
    subjects = SubjectWithStudentsSerializer(many=True, read_only=True)

    class Meta:
        model = TeacherProfile
        fields = ['full_name', 'subjects']

# A simple serializer to show teacher details
class TeacherListSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherProfile
        fields = ['full_name']

# A serializer for a subject that includes attendance stats
class SubjectWithStatsSerializer(serializers.ModelSerializer):
    # Use our new serializer for the teacher
    teacher = TeacherListSerializer(source='teachers.first', read_only=True)
    
    # Use SerializerMethodField to compute values dynamically
    total_classes = serializers.SerializerMethodField()
    present_count = serializers.SerializerMethodField()
    absent_count = serializers.SerializerMethodField()
    attendance_percentage = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = ['id', 'name', 'teacher', 'total_classes', 'present_count', 'absent_count', 'attendance_percentage']

    def get_attendance_records(self, obj):
        # This is a helper method to avoid redundant queries
        # 'obj' is the Subject instance.
        student = self.context['student']
        return Attendance.objects.filter(subject=obj, student=student)

    def get_total_classes(self, obj):
        return self.get_attendance_records(obj).count()

    def get_present_count(self, obj):
        return self.get_attendance_records(obj).filter(status='present').count()

    def get_absent_count(self, obj):
        return self.get_attendance_records(obj).filter(status='absent').count()

    def get_attendance_percentage(self, obj):
        present = self.get_present_count(obj)
        total = self.get_total_classes(obj)
        return round((present / total) * 100, 2) if total > 0 else 0


# The main serializer for the student's dashboard
class StudentDashboardSerializer(serializers.ModelSerializer):
    # We use our custom serializer for the subjects
    subjects = SubjectWithStatsSerializer(many=True, read_only=True)

    class Meta:
        model = StudentProfile
        fields = ['full_name', 'roll_number', 'subjects']