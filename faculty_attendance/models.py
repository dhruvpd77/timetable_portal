from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from core.models import College, Department, Faculty, Batch, TimetableEntry
from attendance.models import Student   # Adjust if your Student model is in another app


class FacultyAttendance(models.Model):
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE)
    date = models.DateField()
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE)
    lecture_number = models.CharField(max_length=20)
    absent_roll_numbers = models.TextField(blank=True)  # comma-separated roll numbers
    present_roll_numbers = models.TextField(blank=True)  # comma-separated roll numbers
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('faculty', 'date', 'batch', 'lecture_number')

    def __str__(self):
        return f"Attendance - {self.faculty.short_name} {self.date} {self.batch.name} Lec {self.lecture_number}"
