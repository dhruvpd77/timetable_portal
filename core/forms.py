from django import forms
from django.contrib.auth.models import User
from .models import (
    FacultyPreferredSlot, Faculty, Batch, Department, Room, Lab, 
    CourseSpec, CourseAssignment, TimetableType, College, BatchRoomLabMapping
)

class FacultyPreferredSlotForm(forms.ModelForm):
    class Meta:
        model = FacultyPreferredSlot
        fields = ['faculty', 'batch', 'preferred_slots']
        widgets = {
            'preferred_slots': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        department = kwargs.pop('department', None)
        super().__init__(*args, **kwargs)
        
        if department:
            self.fields['faculty'].queryset = Faculty.objects.filter(department=department)
            self.fields['batch'].queryset = Batch.objects.filter(department=department)

class BatchForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ['name']

class LabForm(forms.ModelForm):
    class Meta:
        model = Lab
        fields = ['name', 'capacity']

class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['name', 'capacity']

class CourseSpecForm(forms.ModelForm):
    class Meta:
        model = CourseSpec
        fields = ['subject_name', 'subject_type', 'total_hours']

class CourseAssignmentForm(forms.ModelForm):
    class Meta:
        model = CourseAssignment
        fields = ['subject', 'faculty', 'batch', 'hours', 'room_or_lab']

    def __init__(self, *args, **kwargs):
        department = kwargs.pop('department', None)
        super().__init__(*args, **kwargs)
        
        if department:
            self.fields['subject'].queryset = CourseSpec.objects.filter(department=department)
            self.fields['faculty'].queryset = Faculty.objects.filter(department=department)
            self.fields['batch'].queryset = Batch.objects.filter(department=department)

class TimetableTypeForm(forms.ModelForm):
    class Meta:
        model = TimetableType
        fields = ['slot_type']

class AdminPasswordForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput(), label="Admin Password")

class CollegeForm(forms.ModelForm):
    class Meta:
        model = College
        fields = ['name']

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'college']

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        widgets = {
            'password': forms.PasswordInput(),
        }

class UploadExcelForm(forms.Form):
    excel_file = forms.FileField(label="Upload Excel File")

class BatchRoomLabSimpleMappingForm(forms.ModelForm):
    class Meta:
        model = BatchRoomLabMapping
        fields = ['batch', 'room', 'lab']

    def __init__(self, *args, **kwargs):
        department = kwargs.pop('department', None)
        super().__init__(*args, **kwargs)
        
        if department:
            self.fields['batch'].queryset = Batch.objects.filter(department=department)
            self.fields['room'].queryset = Room.objects.filter(department=department)
            self.fields['lab'].queryset = Lab.objects.filter(department=department)

class UploadExcelTimetableForm(forms.Form):
    name = forms.CharField(max_length=100, label="Timetable Name")
    file = forms.FileField(label="Upload Excel File")