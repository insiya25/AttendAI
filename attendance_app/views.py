# attendance_app/views.py

from rest_framework import generics, status
from rest_framework.response import Response
from .serializers import RegisterSerializer,AllStudentsSerializer 
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import MyTokenObtainPairSerializer
from .models import StudentProfile, TeacherProfile,Subject
from .serializers import StudentProfileSerializer, TeacherProfileSerializer, SubjectSerializer
from rest_framework.permissions import IsAuthenticated
from .permissions import IsTeacher,IsStudent
from .serializers import TeacherDashboardSerializer, StudentDashboardSerializer
from rest_framework.views import APIView
from .serializers import UserSkillWriteSerializer, UserProjectWriteSerializer, PerformanceWriteSerializer
from .models import UserSkill, UserProject, Performance
from .services import gemini_service



class AssessmentStartView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, *args, **kwargs):
        skill_name = request.data.get('skill_name')
        if not skill_name:
            return Response({'error': 'skill_name is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        context = {'skill_name': skill_name}
        questions_data = gemini_service.call_gemini_api('GENERATE_QUESTIONS', context)

        if "error" in questions_data:
            return Response(questions_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(questions_data, status=status.HTTP_200_OK)


class AssessmentSubmitView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, *args, **kwargs):
        skill_id = request.data.get('skillId')
        qa_pairs = request.data.get('qa_pairs') # Expected format: [{"question": "...", "answer": "..."}, ...]

        if not all([skill_id, qa_pairs]):
            return Response({'error': 'skillId and qa_pairs are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            skill_instance = UserSkill.objects.get(id=skill_id, student_profile=request.user.studentprofile)
        except UserSkill.DoesNotExist:
            return Response({'error': 'Skill not found for this user.'}, status=status.HTTP_404_NOT_FOUND)

        detailed_results = []
        total_score = 0
        performance_details_text = ""

        for i, pair in enumerate(qa_pairs):
            context = {'question': pair['question'], 'answer': pair['answer']}
            evaluation = gemini_service.call_gemini_api('EVALUATE_SINGLE_ANSWER', context)
            
            if "error" in evaluation: return Response(evaluation, status=500)
            
            rating = evaluation.get('rating', 0)
            marks = 2 if rating > 4 else 0
            total_score += marks
            
            detailed_results.append({
                'question': pair['question'],
                'answer': pair['answer'],
                'rating': rating,
                'suggestion': evaluation.get('suggestion', 'No suggestion provided.'),
                'marks': marks
            })
            performance_details_text += f"Q{i+1}: {pair['question']}\nRating: {rating}/10\n\n"

        # Get overall review
        review_context = {'skill_name': skill_instance.skill_name, 'performance_details': performance_details_text}
        overall_review_data = gemini_service.call_gemini_api('GENERATE_OVERALL_REVIEW', review_context)

        # Update skill verification status if criteria met
        if total_score >= 6:
            skill_instance.verified = True
            skill_instance.save()
        
        final_response = {
            'total_score': total_score,
            'max_score': len(qa_pairs) * 2,
            'verified': skill_instance.verified,
            'overall_review': overall_review_data.get('overall_review', 'Could not generate an overall review.'),
            'detailed_results': detailed_results
        }

        return Response(final_response, status=status.HTTP_200_OK)


class AllStudentsListView(generics.ListAPIView):
    queryset = StudentProfile.objects.all().order_by('full_name')
    serializer_class = AllStudentsSerializer
    permission_classes = [IsAuthenticated, IsTeacher]


# View to handle the logic of assigning students to subjects
class AssignStudentsView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]

    def post(self, request, *args, **kwargs):
        student_ids = request.data.get('student_ids', [])
        subject_ids = request.data.get('subject_ids', [])
        
        if not student_ids or not subject_ids:
            return Response({'error': 'Student and subject IDs are required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Security Check: Ensure the teacher is only assigning to their own subjects
        teacher_subjects = request.user.teacherprofile.subjects.all()
        teacher_subject_ids = set(teacher_subjects.values_list('id', flat=True))
        
        for subject_id in subject_ids:
            if subject_id not in teacher_subject_ids:
                return Response({'error': 'You can only assign students to your own subjects.'}, status=status.HTTP_403_FORBIDDEN)

        # Assign students to subjects
        students = StudentProfile.objects.filter(user_id__in=student_ids)
        subjects = Subject.objects.filter(id__in=subject_ids)

        for student in students:
            student.subjects.add(*subjects)
            
        return Response({'message': 'Students assigned successfully.'}, status=status.HTTP_200_OK)


# View for a teacher to see a specific student's dashboard
class StudentDashboardForTeacherView(generics.RetrieveAPIView):
    serializer_class = StudentDashboardSerializer
    permission_classes = [IsAuthenticated, IsTeacher]
    lookup_field = 'roll_number' # We'll fetch the student by their roll number from the URL
    queryset = StudentProfile.objects.all()

    def get_serializer_context(self):
        # This is the same logic as the student's own dashboard view
        context = super().get_serializer_context()
        context['student'] = self.get_object()
        return context

# --- Skill Management Views ---
class SkillCreateView(generics.CreateAPIView):
    serializer_class = UserSkillWriteSerializer
    permission_classes = [IsAuthenticated, IsStudent]

    def perform_create(self, serializer):
        # Automatically associate the new skill with the logged-in student's profile
        serializer.save(student_profile=self.request.user.studentprofile)

class SkillDeleteView(generics.DestroyAPIView):
    queryset = UserSkill.objects.all()
    permission_classes = [IsAuthenticated, IsStudent]

    def get_queryset(self):
        # Ensure a student can only delete their OWN skills
        return self.queryset.filter(student_profile=self.request.user.studentprofile)
    
# --- Project Management Views ---
class ProjectCreateView(generics.CreateAPIView):
    serializer_class = UserProjectWriteSerializer
    permission_classes = [IsAuthenticated, IsStudent]
    def perform_create(self, serializer):
        serializer.save(student_profile=self.request.user.studentprofile)

class ProjectUpdateView(generics.UpdateAPIView):
    queryset = UserProject.objects.all()
    serializer_class = UserProjectWriteSerializer
    permission_classes = [IsAuthenticated, IsStudent]
    def get_queryset(self):
        return self.queryset.filter(student_profile=self.request.user.studentprofile)

class ProjectDeleteView(generics.DestroyAPIView):
    queryset = UserProject.objects.all()
    permission_classes = [IsAuthenticated, IsStudent]
    def get_queryset(self):
        return self.queryset.filter(student_profile=self.request.user.studentprofile)


# --- Performance Management Views ---
class PerformanceCreateView(generics.CreateAPIView):
    serializer_class = PerformanceWriteSerializer
    permission_classes = [IsAuthenticated, IsStudent]
    def perform_create(self, serializer):
        serializer.save(student_profile=self.request.user.studentprofile)

class PerformanceUpdateView(generics.UpdateAPIView):
    queryset = Performance.objects.all()
    serializer_class = PerformanceWriteSerializer
    permission_classes = [IsAuthenticated, IsStudent]
    def get_queryset(self):
        return self.queryset.filter(student_profile=self.request.user.studentprofile)

class PerformanceDeleteView(generics.DestroyAPIView):
    queryset = Performance.objects.all()
    permission_classes = [IsAuthenticated, IsStudent]
    def get_queryset(self):
        return self.queryset.filter(student_profile=self.request.user.studentprofile)
    

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


class TeacherDashboardView(generics.RetrieveAPIView):
    """
    An endpoint for the teacher's dashboard.
    Returns the teacher's profile and their subjects, with enrolled students for each subject.
    """
    serializer_class = TeacherDashboardSerializer
    permission_classes = [IsAuthenticated, IsTeacher] # Protect with our custom permission

    def get_object(self):
        # The object we are retrieving is the profile of the logged-in teacher.
        # We use prefetch_related to efficiently query the nested students.
        # This is a major performance optimization.
        return TeacherProfile.objects.prefetch_related('subjects__students').get(user=self.request.user)


class StudentDashboardView(generics.RetrieveAPIView):
    """
    An endpoint for the student's dashboard.
    Returns the student's profile and their subjects, with attendance stats for each subject.
    """
    serializer_class = StudentDashboardSerializer
    permission_classes = [IsAuthenticated, IsStudent]

    def get_object(self):
        # The object is the profile of the logged-in student
        return StudentProfile.objects.prefetch_related('subjects__teachers').get(user=self.request.user)
    
    def get_serializer_context(self):
        # We need to pass the student object to the serializer context
        # so our custom methods in SubjectWithStatsSerializer can access it
        context = super().get_serializer_context()
        context['student'] = self.get_object()
        return context

