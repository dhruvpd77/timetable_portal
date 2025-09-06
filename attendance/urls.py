# attendance/urls.py

from django.urls import path
from attendance import views

urlpatterns = [
    path("manage/",views.manage_students,name="manage_students"),
  

    path('attendance-sheet/', views.attendance_sheet_generator, name='attendance_sheet_generator'),

     path('daily-absent/', views.daily_absent, name="daily_absent_single_page"),
    path('attendance-sheet-manager/', views.attendance_sheet_manager, name='attendance_sheet_manager'),
    
]
