# attendance_app/serializers.py

from rest_framework import serializers
from .models import User, StudentProfile, TeacherProfile, Subject, Attendance
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.db.models import Count, Q
from datetime import date, timedelta


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
    # CHANGE: Use many=True to handle multiple teachers for one subject
    teachers = TeacherListSerializer(many=True, read_only=True) 
    
    total_classes = serializers.SerializerMethodField()
    present_count = serializers.SerializerMethodField()
    absent_count = serializers.SerializerMethodField()
    attendance_percentage = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        # CHANGE: 'teacher' field is now 'teachers'
        fields = ['id', 'name', 'teachers', 'total_classes', 'present_count', 'absent_count', 'attendance_percentage']

    # ... (the get_* methods remain the same) ...
    def get_attendance_records(self, obj):
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
    subjects = SubjectWithStatsSerializer(many=True, read_only=True)
    
    # NEW: Add fields for the KPI cards
    overall_stats = serializers.SerializerMethodField()
    # NEW: Add field for the line chart data
    attendance_trend = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = ['full_name', 'roll_number', 'subjects', 'overall_stats', 'attendance_trend']

    def get_overall_stats(self, obj):
        # 'obj' is the StudentProfile instance
        student_attendance = Attendance.objects.filter(student=obj)
        
        present_count = student_attendance.filter(status='present').count()
        absent_count = student_attendance.filter(status='absent').count()
        total_classes = present_count + absent_count
        
        return {
            'total_subjects': obj.subjects.count(),
            'total_present': present_count,
            'total_absent': absent_count,
            'overall_percentage': round((present_count / total_classes) * 100, 2) if total_classes > 0 else 0
        }

    def get_attendance_trend(self, obj):
        # Provide data for a 30-day attendance trend line chart
        today = date.today()
        thirty_days_ago = today - timedelta(days=29)
        
        # Get all attendance records for the student in the last 30 days
        trend_data = Attendance.objects.filter(
            student=obj,
            date__gte=thirty_days_ago,
            date__lte=today
        ).values('date').annotate(
            presents=Count('id', filter=Q(status='present'))
        ).order_by('date')
        
        # Create a dictionary for quick lookups
        data_map = {item['date'].strftime('%Y-%m-%d'): item['presents'] for item in trend_data}
        
        # Format for the frontend chart
        chart_data = []
        for i in range(30):
            day = thirty_days_ago + timedelta(days=i)
            day_str = day.strftime('%Y-%m-%d')
            chart_data.append({
                'date': day_str,
                'presents': data_map.get(day_str, 0) # Default to 0 if no record for that day
            })
            
        return chart_data
