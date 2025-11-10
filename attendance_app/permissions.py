# attendance_app/permissions.py
from rest_framework.permissions import BasePermission

class IsTeacher(BasePermission):
    """
    Allows access only to users with the 'teacher' role.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'teacher'