from django.urls import path
from . import views

urlpatterns = [
    path('', views.report_dashboard, name='report_dashboard'),  # Dashboard is the default reports/ route
    path('faculty/', views.faculty_report, name='faculty_report'),
    path('faculty/download/', views.faculty_report_download, name='faculty_report_download'),
    
    path('batch/', views.batch_timetable, name='batch_timetable'),
    path('batch/download/', views.batch_timetable_download, name='batch_timetable_download'),
    path('faculty_availability/', views.faculty_availability, name='faculty_availability'),
    path('faculty_availability/download/', views.faculty_availability_download, name='faculty_availability_download'),
    path('room_lab_availability/', views.room_lab_availability, name='room_lab_availability'),
    path('room_lab_availability/download/', views.room_lab_availability_download, name='room_lab_availability_download'),
    path('combined/', views.combined_timetable, name='combined_timetable'),
    path('combined/download/', views.combined_timetable_download, name='combined_timetable_download'),

    # Combined Room & Lab Availability
    path('combined_room_lab_availability/', views.combined_room_lab_availability, name='combined_room_lab_availability'),
    path('combined_room_lab_availability/download/', views.combined_room_lab_availability_download, name='combined_room_lab_availability_download'),

    # Combined Faculty Availability
    path('combined_faculty_availability/', views.combined_faculty_availability, name='combined_faculty_availability'),
    path('combined_faculty_availability/download/', views.combined_faculty_availability_download, name='combined_faculty_availability_download'),

    path('combined-analytics/', views.combined_analytics, name='combined_analytics'),
    path('combined-analytics/download/', views.combined_analytics_download, name='combined_analytics_download'),

    path('analytics-report/', views.analytics_report, name='analytics_report'),
    path('analytics-report/download/', views.analytics_report_download, name='analytics_report_download'),

    path('spin-wheel/', views.spin_wheel, name='spin_wheel'),


]
