# attendance_app/serializers.py

from rest_framework import serializers
from .models import User, StudentProfile, TeacherProfile, Subject
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
