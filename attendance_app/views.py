# attendance_app/views.py

from rest_framework import generics, status
from rest_framework.response import Response
from .serializers import RegisterSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import MyTokenObtainPairSerializer
from .models import StudentProfile, TeacherProfile,Subject
from .serializers import StudentProfileSerializer, TeacherProfileSerializer, SubjectSerializer
from rest_framework.permissions import IsAuthenticated

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "user": user.username,
                "message": "User created successfully. Please log in."
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


class ProfileView(generics.RetrieveUpdateAPIView):
    """
    An endpoint for the logged-in user to view and update their profile.
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        # Return the serializer based on the user's role
        if self.request.user.role == 'student':
            return StudentProfileSerializer
        elif self.request.user.role == 'teacher':
            return TeacherProfileSerializer
        # You might want to add a fallback or raise an error here
        return super().get_serializer_class()

    def get_object(self):
        # Return the profile object for the current user
        user = self.request.user
        if user.role == 'student':
            # Use select_related to efficiently fetch the user object
            return StudentProfile.objects.select_related('user').get(user=user)
        elif user.role == 'teacher':
            return TeacherProfile.objects.select_related('user').get(user=user)

    def get_serializer_context(self):
        # Pass request to the serializer context, useful for image URLs
        return {'request': self.request}

class SubjectListView(generics.ListAPIView):
    """
    An endpoint to provide a list of all available subjects.
    """
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [IsAuthenticated] # Only logged-in users can see subjects

