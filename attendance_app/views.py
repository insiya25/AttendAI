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
from .serializers import TeacherDashboardSerializer, StudentDashboardSerializer, ApprovalReadSerializer, ApprovalWriteSerializer, TeacherSelectSerializer, AIEnhanceSerializer
from rest_framework.views import APIView
from .serializers import UserSkillWriteSerializer, UserProjectWriteSerializer, PerformanceWriteSerializer
from .models import UserSkill, UserProject, Performance,Approval, Attendance, StudentFace
from .services import gemini_service
from django.db import models

import calendar
from datetime import datetime
from django.db import transaction

import PIL.Image
from .services import gemini_service

from django.core.exceptions import ObjectDoesNotExist

import numpy as np
import json
import cv2
from PIL import Image
from deepface import DeepFace
from django.core.files.uploadedfile import InMemoryUploadedFile



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


# --- Helper to get list of teachers for dropdown ---
class TeacherListView(generics.ListAPIView):
    queryset = TeacherProfile.objects.all()
    serializer_class = TeacherSelectSerializer
    permission_classes = [IsAuthenticated]

# --- AI Enhancement Endpoint ---
class AIEnhanceView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AIEnhanceSerializer(data=request.data)
        if serializer.is_valid():
            text = serializer.validated_data['text']
            type = serializer.validated_data['type']
            
            task = 'ENHANCE_SUBJECT' if type == 'subject' else 'ENHANCE_MESSAGE'
            result = gemini_service.call_gemini_api(task, {'text': text})
            
            return Response(result)
        return Response(serializer.errors, status=400)

# --- Student: List & Create Approvals ---
class StudentApprovalView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsStudent]
    
    def get_queryset(self):
        return Approval.objects.filter(student=self.request.user.studentprofile).order_by('-created_at')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ApprovalWriteSerializer
        return ApprovalReadSerializer

    def perform_create(self, serializer):
        serializer.save(student=self.request.user.studentprofile)

# --- Teacher: List & Update Approvals ---
class TeacherApprovalListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsTeacher]
    serializer_class = ApprovalReadSerializer

    def get_queryset(self):
        # Show approvals where teacher is main recipient OR in CC
        return Approval.objects.filter(
            models.Q(teacher=self.request.user.teacherprofile) | 
            models.Q(cc_teachers=self.request.user.teacherprofile)
        ).distinct().order_by('-created_at')

class TeacherApprovalUpdateView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated, IsTeacher]
    serializer_class = ApprovalReadSerializer
    queryset = Approval.objects.all()
    
    def update(self, request, *args, **kwargs):
        # Custom update to only allow status change
        instance = self.get_object()
        status_val = request.data.get('status')
        if status_val in ['approved', 'rejected']:
            instance.status = status_val
            instance.save()
            return Response(ApprovalReadSerializer(instance).data)
        return Response({'error': 'Invalid status'}, status=400)


class GetAttendanceSheetView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]

    def get(self, request):
        subject_id = request.query_params.get('subject_id')
        month = int(request.query_params.get('month')) # 1-12
        year = int(request.query_params.get('year'))

        if not all([subject_id, month, year]):
            return Response({'error': 'Subject, Month, and Year are required.'}, status=400)

        try:
            subject = Subject.objects.get(id=subject_id)
            # Security check: Ensure teacher teaches this subject
            if subject not in request.user.teacherprofile.subjects.all():
                return Response({'error': 'You do not teach this subject.'}, status=403)

            # Get all enrolled students
            students = subject.students.all().order_by('roll_number')
            
            # Get existing attendance records for this month
            attendance_records = Attendance.objects.filter(
                subject=subject,
                date__year=year,
                date__month=month
            )

            # Create a lookup dictionary: {student_id: {day: status}}
            attendance_map = {}
            for record in attendance_records:
                sid = record.student.user_id
                if sid not in attendance_map:
                    attendance_map[sid] = {}
                attendance_map[sid][record.date.day] = record.status

            # Build response data
            student_data = []
            for student in students:
                student_data.append({
                    'id': student.user_id,
                    'full_name': student.full_name,
                    'roll_number': student.roll_number,
                    'attendance': attendance_map.get(student.user_id, {})
                })

            # Get number of days in the month
            num_days = calendar.monthrange(year, month)[1]

            return Response({
                'students': student_data,
                'days_in_month': num_days
            })

        except Subject.DoesNotExist:
            return Response({'error': 'Subject not found'}, status=404)

class BulkAttendanceUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]

    def post(self, request):
        # Now accepts a LIST of subject IDs or a single ID
        subject_ids = request.data.get('subject_ids') 
        # Backwards compatibility if frontend sends single 'subject_id'
        if not subject_ids and request.data.get('subject_id'):
            subject_ids = [request.data.get('subject_id')]

        if not subject_ids:
            return Response({'error': 'Please select at least one subject.'}, status=400)

        is_ocr = request.data.get('is_ocr', False)
        teacher = request.user.teacherprofile

        try:
            subjects = Subject.objects.filter(id__in=subject_ids)

            with transaction.atomic():
                if is_ocr:
                    ocr_data = request.data.get('ocr_data')
                    for student_rec in ocr_data:
                        # Skip if we already know they don't exist (frontend shouldn't send them, but safety check)
                        if not student_rec.get('db_exists', True): 
                            continue

                        roll_no = student_rec.get('roll_number')
                        
                        # Find Student
                        try:
                            student = StudentProfile.objects.get(roll_number__iexact=roll_no)
                        except StudentProfile.DoesNotExist:
                            try:
                                student = StudentProfile.objects.get(roll_number__iexact=roll_no.replace(" ", ""))
                            except StudentProfile.DoesNotExist:
                                continue 

                        # Loop through Dates
                        for att in student_rec.get('attendance', []):
                            try:
                                date_str = att['date'].replace('/', '-')
                                date_obj = datetime.strptime(date_str, '%d-%m-%Y').date()
                                
                                # Loop through Selected Subjects (Apply to ALL)
                                for subject in subjects:
                                    Attendance.objects.update_or_create(
                                        student=student,
                                        subject=subject,
                                        date=date_obj,
                                        defaults={'status': att['status'], 'teacher': teacher}
                                    )
                            except ValueError:
                                continue
                else:
                    # Manual Mode Logic (Usually single subject, but let's support multi if needed)
                    updates = request.data.get('updates')
                    for update in updates:
                        student = StudentProfile.objects.get(user_id=update['student_id'])
                        for subject in subjects:
                            Attendance.objects.update_or_create(
                                student=student,
                                subject=subject,
                                date=update['date'],
                                defaults={'status': update['status'], 'teacher': teacher}
                            )
            
            return Response({'message': 'Attendance updated successfully.'})

        except Exception as e:
            print(f"Error: {e}")
            return Response({'error': str(e)}, status=500)



class ProcessAttendanceSheetView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]

    def post(self, request):
        if 'image' not in request.FILES:
            return Response({'error': 'No image provided'}, status=400)

        uploaded_file = request.FILES['image']
        
        try:
            img = PIL.Image.open(uploaded_file)
            
            # 1. Get raw data from Gemini
            result = gemini_service.call_gemini_api('ANALYZE_ATTENDANCE_SHEET', context={}, image=img)
            
            if "error" in result:
                return Response(result, status=500)

            # 2. VALIDATION LOGIC: Check which students exist in DB
            enriched_records = []
            unknown_students = []

            for record in result.get('records', []):
                roll_raw = record.get('roll_number', '').strip()
                
                # Try to find student (Case insensitive)
                # We check if a profile exists with this roll number
                exists = StudentProfile.objects.filter(roll_number__iexact=roll_raw).exists()
                
                # Fallback: try removing spaces
                if not exists:
                    exists = StudentProfile.objects.filter(roll_number__iexact=roll_raw.replace(" ", "")).exists()

                record['db_exists'] = exists # Add flag to response
                
                enriched_records.append(record)
                
                if not exists:
                    unknown_students.append({
                        'roll_number': roll_raw,
                        'name': record.get('name')
                    })

            return Response({
                'records': enriched_records,
                'unknown_students': unknown_students
            })

        except Exception as e:
            return Response({'error': f'Processing failed: {str(e)}'}, status=500)


# --- HELPER: Convert Django File to Numpy Array for DeepFace ---
def convert_image_to_numpy(uploaded_file):
    # Open image using Pillow
    img = Image.open(uploaded_file)
    # Convert to RGB (DeepFace expects RGB)
    img = img.convert('RGB')
    # Convert to numpy array
    return np.array(img)

# --- HELPER: Calculate Cosine Similarity ---
def find_cosine_distance(source_representation, test_representation):
    a = np.matmul(np.transpose(source_representation), test_representation)
    b = np.sum(np.multiply(source_representation, source_representation))
    c = np.sum(np.multiply(test_representation, test_representation))
    return 1 - (a / (np.sqrt(b) * np.sqrt(c)))

# --- 1. REGISTER FACE VIEW ---
class RegisterFaceView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]

    def post(self, request):
        student_id = request.data.get('student_id')
        image_file = request.FILES.get('image')

        if not student_id or not image_file:
            return Response({'error': 'Student ID and Image are required.'}, status=400)

        try:
            student = StudentProfile.objects.get(user_id=student_id)
            
            # Convert image to numpy array
            img_array = convert_image_to_numpy(image_file)

            # Generate Embedding (Using "Facenet" model for balance of speed/accuracy)
            # enforce_detection=True ensures we actually have a face
            embedding_objs = DeepFace.represent(
                img_path=img_array, 
                model_name="Facenet", 
                enforce_detection=True
            )

            if not embedding_objs:
                return Response({'error': 'No face detected.'}, status=400)

            # Get the embedding vector
            embedding = embedding_objs[0]["embedding"]
            
            # Save as JSON
            encoding_json = json.dumps(embedding)

            StudentFace.objects.update_or_create(
                student=student,
                defaults={'face_encoding': encoding_json}
            )

            return Response({'message': f'Face registered for {student.full_name}'})

        except ValueError as e:
            return Response({'error': 'No face detected in the image. Please try again.'}, status=400)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student not found.'}, status=404)
        except Exception as e:
            print(f"Register Error: {e}")
            return Response({'error': str(e)}, status=500)


# --- 2. RECOGNIZE FACE VIEW ---
class RecognizeFaceView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]

    def post(self, request):
        subject_id = request.data.get('subject_id')
        image_file = request.FILES.get('image')

        if not subject_id or not image_file:
            return Response({'error': 'Subject and Image are required.'}, status=400)

        try:
            # 1. Process Uploaded Image
            img_array = convert_image_to_numpy(image_file)
            
            # Get embedding of the uploaded face
            target_embedding_objs = DeepFace.represent(
                img_path=img_array, 
                model_name="Facenet", 
                enforce_detection=True
            )
            
            if not target_embedding_objs:
                return Response({'status': 'no_face', 'message': 'No face detected'})

            target_embedding = target_embedding_objs[0]["embedding"]

            # 2. Fetch ALL known faces
            known_faces = StudentFace.objects.all().select_related('student')
            
            best_match = None
            lowest_distance = 1.0 # Start high
            threshold = 0.40 # Facenet threshold (lower is stricter)

            for face_obj in known_faces:
                db_embedding = json.loads(face_obj.face_encoding)
                
                # Calculate Distance
                distance = find_cosine_distance(target_embedding, db_embedding)
                
                if distance < lowest_distance:
                    lowest_distance = distance
                    best_match = face_obj.student

            # 3. Check Threshold
            if best_match and lowest_distance < threshold:
                # --- NEW: Check Enrollment ---
                subject = Subject.objects.get(id=subject_id)
                
                # Check if student is enrolled in this subject
                if not best_match.subjects.filter(id=subject.id).exists():
                    return Response({
                        'status': 'warning', # New status type
                        'student_name': best_match.full_name,
                        'message': f'Not enrolled in {subject.name}'
                    })
                # -----------------------------

                teacher = request.user.teacherprofile
                today = datetime.now().date()

                Attendance.objects.update_or_create(
                    student=best_match,
                    subject=subject,
                    date=today,
                    defaults={'status': 'present', 'teacher': teacher}
                )

                return Response({
                    'status': 'success',
                    'student_name': best_match.full_name,
                    'roll_number': best_match.roll_number,
                    'message': 'Marked Present',
                    'confidence': round((1 - lowest_distance) * 100, 2)
                })
            else:
                return Response({'status': 'unknown', 'message': 'Face not recognized'})

        except ValueError:
            return Response({'status': 'no_face', 'message': 'No face detected'})
        except Exception as e:
            print(f"Recognition Error: {e}")
            return Response({'error': str(e)}, status=500)

