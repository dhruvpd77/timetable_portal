from django.urls import path
from . import views

urlpatterns = [
    path('', views.welcome_view, name='welcome'),

    # Admin
    path('admin-setup/', views.admin_setup_view, name='admin_setup'),
    path('global-time-settings/', views.global_time_settings_view, name='global_time_settings'),
    path("upload_excel_timetable/", views.upload_excel_timetable_view, name="upload_excel_timetable"),
    path('department-time-settings/', views.department_time_settings_view, name='department_time_settings'),
    path('faculty-management/', views.faculty_management_view, name='faculty_management'),
    path('manage-visiting-blocks/', views.manage_visiting_blocks, name='manage_visiting_blocks'),
    path('edit-faculty/<int:faculty_id>/', views.edit_faculty_view, name='edit_faculty'),  
    path('batch-management/', views.batch_management_view, name='batch_management'),
    path('edit-batch/<int:batch_id>/', views.edit_batch_view, name='edit_batch'),
    path('lab-management/', views.lab_management_view, name='lab_management'),
    path('edit-lab/<int:lab_id>/', views.edit_lab_view, name='edit_lab'),
    path('rooms/', views.room_management_view, name='room_management'),
    path('rooms/edit/<int:room_id>/', views.edit_room_view, name='edit_room'),
    path("manage-faculty-blocks/", views.manage_faculty_blocks, name="manage_faculty_blocks"),
    path("manage-room-blocks/", views.manage_room_blocks, name="manage_room_blocks"),
    path("manage-lab-blocks/", views.manage_lab_blocks, name="manage_lab_blocks"),
    
    # Faculty Preferred Slots
    path("manage-faculty-preferred-slots/", views.manage_faculty_preferred_slots, name="manage_faculty_preferred_slots"),
    path("faculty-preferred-slots/", views.faculty_preferred_slots_list, name="faculty_preferred_slots_list"),
    path("faculty-preferred-slots/add/", views.add_faculty_preferred_slots, name="add_faculty_preferred_slots"),
    path("faculty-preferred-slots/edit/<int:pk>/", views.edit_faculty_preferred_slots, name="edit_faculty_preferred_slots"),
    path("faculty-preferred-slots/delete/<int:pk>/", views.delete_faculty_preferred_slots, name="delete_faculty_preferred_slots"),







  
 # Course Spec
    path('course-specification/', views.course_specification_view, name='course_specification'),
    path('course-specification/edit/<int:spec_id>/', views.edit_course_specification, name='edit_course_specification'),
    path('course-specification/delete/<int:spec_id>/', views.delete_course_specification, name='delete_course_specification'),




    path("assign-course/", views.assign_course_view, name="assign_course"),
    path("delete-assignment/<int:pk>/", views.delete_assignment_view, name="delete_assignment"),
    path("edit-assignment/<int:pk>/", views.edit_assignment_view, name="edit_assignment"),
    path("generate-timetable/", views.generate_timetable_view, name="generate_timetable"),


   
   path('view-past-timetable/', views.view_past_timetable, name='view_past_timetable'),
   path('edit-timetable/<int:timetable_id>/', views.edit_timetable, name='edit_timetable'),
   
   path("logout/",views.logout_view,name="logout"),
   


    
    path('excel-upload/', views.excel_upload, name='excel_upload'),

    


    path('batch-mapping/', views.batch_room_lab_simple_mapping_view, name='batch_room_lab_simple_mapping'),

    path('timetable-type/', views.manage_timetable_type, name='manage_timetable_type'),





    # Admin Module URLs
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/login/', views.admin_login, name='admin_login'),
    path('admin/logout/', views.admin_logout, name='admin_logout'),
    path('admin/create-college/', views.create_college, name='create_college'),
    path('admin/create-department/', views.create_department, name='create_department'),
    path('admin/create-user/', views.create_user, name='create_user'),
    path('admin/edit-college/<int:college_id>/', views.edit_college, name='edit_college'),
    path('admin/edit-department/<int:department_id>/', views.edit_department, name='edit_department'),
    path('admin/delete-college/<int:college_id>/', views.delete_college, name='delete_college'),
    path('admin/delete-department/<int:department_id>/', views.delete_department, name='delete_department'),
    path('admin/delete-user/<int:user_id>/', views.delete_user, name='delete_user'),

]


