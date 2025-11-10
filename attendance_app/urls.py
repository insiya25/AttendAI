from django.urls import path
from .views import RegisterView, LoginView, ProfileView,SubjectListView,TeacherDashboardView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='token_obtain_pair'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'), # For refreshing tokens
    path('profile/', ProfileView.as_view(), name='profile'),
    path('subjects/', SubjectListView.as_view(), name='subject-list'),
    path('teacher/dashboard/', TeacherDashboardView.as_view(), name='teacher-dashboard'),
]
