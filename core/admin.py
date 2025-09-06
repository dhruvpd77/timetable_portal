from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import College, Department,Faculty,Lab,Room,Batch,CourseAssignment,CourseSpec

admin.site.register(College)
admin.site.register(Department)
# core/admin.py

from .models import GlobalDay, GlobalTimeSlot,Faculty,TimeSettings,Timetable,TimetableEntry


admin.site.register(GlobalDay)
admin.site.register(GlobalTimeSlot)
admin.site.register(Faculty)
admin.site.register(TimeSettings)
admin.site.register(Lab)
admin.site.register(Room)
admin.site.register(Batch)
admin.site.register(CourseAssignment)
admin.site.register(CourseSpec)
admin.site.register(TimetableEntry)
admin.site.register(Timetable)

from .models import College, Department, GlobalDay, GlobalTimeSlot, TimeSettings, Faculty, VisitingFacultyBlock, FacultyBlock, Batch, Lab, Room, BatchRoomLabMapping, CourseSpec, CourseAssignment, TimetableEntry, Timetable, RoomBlock, LabBlock, TimetableType

admin.site.register(VisitingFacultyBlock)
admin.site.register(FacultyBlock)
admin.site.register(BatchRoomLabMapping)
admin.site.register(RoomBlock)
admin.site.register(LabBlock)
admin.site.register(TimetableType)

