from django.urls import path
from .views import RegisterView, LoginView, ProfileView,SubjectListView,TeacherDashboardView, StudentDashboardView,AllStudentsListView, AssignStudentsView, StudentDashboardForTeacherView
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    SkillCreateView, SkillDeleteView, 
    ProjectCreateView, ProjectUpdateView, ProjectDeleteView,
    PerformanceCreateView, PerformanceUpdateView, PerformanceDeleteView
)
from .views import AssessmentStartView, AssessmentSubmitView, TeacherApprovalListView, TeacherListView,AIEnhanceView, StudentApprovalView, TeacherApprovalUpdateView,GetAttendanceSheetView, BulkAttendanceUpdateView, ProcessAttendanceSheetView
from .views import RegisterFaceView, RecognizeFaceView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='token_obtain_pair'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'), # For refreshing tokens
    path('profile/', ProfileView.as_view(), name='profile'),
    path('subjects/', SubjectListView.as_view(), name='subject-list'),
    path('teacher/dashboard/', TeacherDashboardView.as_view(), name='teacher-dashboard'),
    path('student/dashboard/', StudentDashboardView.as_view(), name='student-dashboard'),
    path('students/all/', AllStudentsListView.as_view(), name='all-students-list'),
    path('teacher/assign-students/', AssignStudentsView.as_view(), name='assign-students'),
    path('teacher/view-student/<str:roll_number>/', StudentDashboardForTeacherView.as_view(), name='view-student-dashboard'),

     # NEW: URLs for granular profile editing
    path('profile/skills/', SkillCreateView.as_view(), name='skill-create'),
    path('profile/skills/<int:pk>/', SkillDeleteView.as_view(), name='skill-delete'),
    
    path('profile/projects/', ProjectCreateView.as_view(), name='project-create'),
    path('profile/projects/<int:pk>/', ProjectUpdateView.as_view(), name='project-update'),
    path('profile/projects/<int:pk>/delete/', ProjectDeleteView.as_view(), name='project-delete'),

    path('profile/performance/', PerformanceCreateView.as_view(), name='performance-create'),
    path('profile/performance/<int:pk>/', PerformanceUpdateView.as_view(), name='performance-update'),
    path('profile/performance/<int:pk>/delete/', PerformanceDeleteView.as_view(), name='performance-delete'),

    path('assessment/start/', AssessmentStartView.as_view(), name='assessment-start'),
    path('assessment/submit/', AssessmentSubmitView.as_view(), name='assessment-submit'),


    path('teachers/list/', TeacherListView.as_view()),
    path('ai/enhance/', AIEnhanceView.as_view()),
    
    path('student/approvals/', StudentApprovalView.as_view()),
    
    path('teacher/approvals/', TeacherApprovalListView.as_view()),
    path('teacher/approvals/<int:pk>/update/', TeacherApprovalUpdateView.as_view()),

    path('teacher/attendance/sheet/', GetAttendanceSheetView.as_view()),
    path('teacher/attendance/update/', BulkAttendanceUpdateView.as_view()),

    path('teacher/attendance/ocr/', ProcessAttendanceSheetView.as_view()),

    path('face/register/', RegisterFaceView.as_view()),
    path('face/recognize/', RecognizeFaceView.as_view()),
]
