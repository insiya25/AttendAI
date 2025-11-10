# attendance_app/serializers.py

from rest_framework import serializers
from .models import User, StudentProfile, TeacherProfile

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