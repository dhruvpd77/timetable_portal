from django.db import models

# Create your models here.
from django.db import models

class College(models.Model):
    name = models.CharField(max_length=200, unique=True)
    
    def __str__(self):
        return self.name


# core/models.py

class GlobalDay(models.Model):
    name = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.name

class GlobalTimeSlot(models.Model):
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        unique_together = ('start_time', 'end_time')

    def __str__(self):
        return f"{self.start_time.strftime('%H:%M')} – {self.end_time.strftime('%H:%M')}"
from django.contrib.auth.models import User

class Department(models.Model):
    college = models.ForeignKey(College, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = ('college', 'name')

    def __str__(self):
        return f"{self.name} ({self.college.name})"

class TimeSettings(models.Model):
    department = models.OneToOneField(Department, on_delete=models.CASCADE)
    selected_days = models.ManyToManyField(GlobalDay)
    selected_slots = models.ManyToManyField(GlobalTimeSlot)
    break_slots = models.ManyToManyField(GlobalTimeSlot, related_name="breaks")

    def __str__(self):
        return f"Time Settings for {self.department.name}"
# core/models.py

class Faculty(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=20)
    default_load = models.IntegerField(default=0)
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.full_name} ({self.short_name})"
    
from django.db import models

import json
from django.db import models
import json
from django.db import models

class VisitingFacultyBlock(models.Model):
    faculty = models.ForeignKey("Faculty", on_delete=models.CASCADE)
    main_department = models.ForeignKey("Department", on_delete=models.CASCADE)
    blocked_slots = models.TextField()  # JSON string: [("Monday", "09:45–10:45"), ...]

    def get_blocked_slots(self):
        try:
            return json.loads(self.blocked_slots)
        except Exception:
            return []

    def __str__(self):
        return f"{self.faculty} - {self.main_department}"


from django.db import models
from core.models import Faculty, Department

class FacultyBlock(models.Model):
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    blocked_slots = models.JSONField()  # Format: [{"day": "Monday", "slot": "10:45–11:45"}, ...]
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.faculty.short_name} Blocked Slots"


class Batch(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('department', 'name')

    def __str__(self):
        return self.name


class FacultyPreferredSlot(models.Model):
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    preferred_slots = models.JSONField()  # Format: [{"day": "Monday", "slot": "10:45–11:45"}, ...]
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.faculty.short_name} - {self.batch.name} Preferred Slots"


class Lab(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    capacity = models.IntegerField(default=1)

    class Meta:
        unique_together = ('department', 'name')

    def __str__(self):
        return f"{self.name} (Capacity: {self.capacity})"
class Room(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    capacity = models.IntegerField(default=0)

    class Meta:
        unique_together = ('department', 'name')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.capacity})"
from django.db import models

# core/models.py
from django.db import models

class BatchRoomLabMapping(models.Model):
    department = models.ForeignKey('Department', on_delete=models.CASCADE)
    batch = models.ForeignKey('Batch', on_delete=models.CASCADE)
    lab = models.ForeignKey('Lab', on_delete=models.SET_NULL, blank=True, null=True)
    room = models.ForeignKey('Room', on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        unique_together = ('department', 'batch', 'lab', 'room')

    def __str__(self):
        assigned_space = self.lab if self.lab else self.room
        return f"{self.batch.name} - {assigned_space}"

from django.db import models

class CourseSpec(models.Model):
    department = models.ForeignKey('Department', on_delete=models.CASCADE)
    subject_name = models.CharField(max_length=100)
    subject_type = models.CharField(max_length=10, choices=[('Theory', 'Theory'), ('Practical', 'Practical')])
    total_hours = models.IntegerField()

    class Meta:
        unique_together = ('department', 'subject_name')

    def __str__(self):
        return self.subject_name

class CourseAssignment(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    subject = models.ForeignKey(CourseSpec, on_delete=models.CASCADE)
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE)
    hours = models.IntegerField(default=0)
    room_or_lab = models.CharField(max_length=10)  # 'Room' or 'Lab'

    def __str__(self):
        return f"{self.subject.subject_name} - {self.batch.name} - {self.faculty.short_name}"

class TimetableEntry(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    subject = models.ForeignKey(CourseSpec, on_delete=models.CASCADE)
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, null=True, blank=True, on_delete=models.SET_NULL)
    lab = models.ForeignKey(Lab, null=True, blank=True, on_delete=models.SET_NULL)
    day = models.CharField(max_length=20)
    time = models.CharField(max_length=20)
    timetable = models.ForeignKey('Timetable', on_delete=models.CASCADE, null=True, blank=True)
    def __str__(self):
        return f"({self.batch})"

class Timetable(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.department})"


class RoomBlock(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    blocked_slots = models.JSONField()  # Format: [{"day": "Monday", "slot": "10:45–11:45"}, ...]
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.room.name} Blocked Slots"


class LabBlock(models.Model):
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    blocked_slots = models.JSONField()  # Format: [{"day": "Monday", "slot": "10:45–11:45"}, ...]
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.lab.name} Blocked Slots"


class TimetableType(models.Model):
    department = models.OneToOneField(Department, on_delete=models.CASCADE)
    slot_type = models.CharField(
        max_length=10,
        choices=[
            ('1_hour', '1 Hour Slot'),
            ('2_hour', '2 Hour Pair Slot')
        ],
        default='1_hour'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Timetable Type'
        verbose_name_plural = 'Timetable Types'

    def __str__(self):
        return f"{self.department.name} - {self.get_slot_type_display()}"



