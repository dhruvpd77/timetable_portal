from django.db import models
from core.models import Department, Timetable

# attendance/models.py

from django.db import models
from core.models import Department




class Student(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    batch = models.CharField(max_length=100)
    roll_no = models.CharField(max_length=20)
    enrollment_no = models.CharField(max_length=30)
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.roll_no} - {self.name}"

from django.db import models
from core.models import Department

class AttendanceSessionWindow(models.Model):
    department = models.OneToOneField(Department, on_delete=models.CASCADE)
    t1_start = models.DateField(null=True, blank=True)
    t1_end = models.DateField(null=True, blank=True)
    t2_start = models.DateField(null=True, blank=True)
    t2_end = models.DateField(null=True, blank=True)
    t3_start = models.DateField(null=True, blank=True)
    t3_end = models.DateField(null=True, blank=True)
    t4_start = models.DateField(null=True, blank=True)
    t4_end = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Attendance Windows for {self.department}"
