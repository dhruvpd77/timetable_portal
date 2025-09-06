from django.urls import path
from . import views

app_name = 'faculty_attendance'

urlpatterns = [
    path('logout/', views.faculty_logout, name='faculty_logout'),
    path('attendance-entry/', views.attendance_entry, name='attendance_entry'),
    path('faculty-login/', views.faculty_login, name='faculty_login'),
    path('ajax/load-departments/', views.ajax_load_departments, name='ajax_load_departments'),
    
    path('create-faculty-user/', views.create_faculty_user, name='create_faculty_user'),
    path('ajax/load-faculties/', views.load_faculties, name='ajax_load_faculties'),
]
