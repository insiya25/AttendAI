# attendance_app/serializers.py

from rest_framework import serializers
from .models import User, StudentProfile, TeacherProfile, Subject, Attendance, UserSkill, UserProject, Performance
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.db.models import Count, Q
from datetime import date, timedelta


class AllStudentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = ['user_id', 'full_name', 'roll_number']

class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name']

class UserSkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSkill
        fields = ['id', 'skill_name', 'verified']

class UserProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProject
        fields = ['id', 'project_name', 'semester', 'description', 'created', 'updated']

class PerformanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Performance
        fields = ['id', 'semester', 'cgpi', 'status']

class UserSkillWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSkill
        fields = ['skill_name'] # Student profile will be added automatically from the request user

class UserProjectWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProject
        fields = ['project_name', 'semester', 'description']

class PerformanceWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Performance
        fields = ['semester', 'cgpi', 'status']

class StudentProfileSerializer(serializers.ModelSerializer):
    subjects = SubjectSerializer(many=True, read_only=True)
    subject_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    username = serializers.CharField(source='user.username', read_only=True)
    
    # Add the new related fields
    skills = UserSkillSerializer(many=True, read_only=True)
    projects = UserProjectSerializer(many=True, read_only=True)
    performance_records = PerformanceSerializer(many=True, read_only=True)

    class Meta:
        model = StudentProfile
        # Add new fields to the list
        fields = [
            'username', 'full_name', 'photo', 'age', 'class_name', 
            'roll_number', 'email', 'phone_number', 'subjects', 
            'subject_ids', 'skills', 'projects', 'performance_records'
        ]
        read_only_fields = ['roll_number', 'username']

    def update(self, instance, validated_data):
        if 'subject_ids' in validated_data:
            subject_ids = validated_data.pop('subject_ids')
            instance.subjects.set(subject_ids)

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
    subjects = serializers.SerializerMethodField()

    class Meta:
        model = TeacherProfile
        fields = ['full_name', 'subjects']

    def get_subjects(self, obj):
        # 'obj' is the TeacherProfile instance
        teacher_subjects = obj.subjects.prefetch_related('students').all()
        result = []

        for subject in teacher_subjects:
            attendance_records = Attendance.objects.filter(subject=subject)
            total_records = attendance_records.count()
            present_records = attendance_records.filter(status='present').count()

            # --- Monthly Trend Data for Bar Chart ---
            today = date.today()
            start_of_month = today.replace(day=1)
            days_in_month = (today.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1)).day if today.month != 12 else 31
            
            monthly_trend_data = attendance_records.filter(
                date__gte=start_of_month
            ).values('date').annotate(
                presents=Count('id', filter=Q(status='present')),
                absents=Count('id', filter=Q(status='absent'))
            ).order_by('date')
            
            # Map data for easy lookup
            trend_map = {item['date'].strftime('%d'): {'presents': item['presents'], 'absents': item['absents']} for item in monthly_trend_data}
            
            # Format for the frontend chart
            monthly_trend = []
            for day_num in range(1, days_in_month + 1):
                day_str = f"{day_num:02d}"
                monthly_trend.append({
                    'day': day_str,
                    'presents': trend_map.get(day_str, {}).get('presents', 0),
                    'absents': trend_map.get(day_str, {}).get('absents', 0),
                })
            # --- End Monthly Trend ---

            result.append({
                'id': subject.id,
                'name': subject.name,
                'total_students': subject.students.count(),
                'present_percentage': round((present_records / total_records) * 100, 1) if total_records > 0 else 0,
                'absent_percentage': round(((total_records - present_records) / total_records) * 100, 1) if total_records > 0 else 0,
                'students': StudentListSerializer(subject.students.all(), many=True).data, # For the students tab
                'monthly_trend': monthly_trend,
            })
        return result

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
