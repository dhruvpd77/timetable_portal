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
            'faculty': forms.Select(attrs={'class': 'form-select'}),
            'batch': forms.Select(attrs={'class': 'form-select'}),
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
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. CE-A 2024'}),
        }

class LabForm(forms.ModelForm):
    class Meta:
        model = Lab
        fields = ['name', 'capacity']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Computer Lab 1'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 30', 'min': '1'}),
        }

class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['name', 'capacity']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Room 101'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 60', 'min': '1'}),
        }

class CourseSpecForm(forms.ModelForm):
    class Meta:
        model = CourseSpec
        fields = ['subject_name', 'subject_type', 'total_hours']
        widgets = {
            'subject_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. DM'}),
            'subject_type': forms.Select(attrs={'class': 'form-select'}),
            'total_hours': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': 'e.g. 5'}),
        }

class CourseAssignmentForm(forms.ModelForm):
    class Meta:
        model = CourseAssignment
        fields = ['subject', 'faculty', 'batch', 'hours', 'room_or_lab']
        widgets = {
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'faculty': forms.Select(attrs={'class': 'form-select'}),
            'batch': forms.Select(attrs={'class': 'form-select'}),
            'hours': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'room_or_lab': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 301 or Lab-A'}),
        }

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
        widgets = {
            'slot_type': forms.Select(attrs={'class': 'form-select'}),
        }

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
    excel_file = forms.FileField(label="Upload Excel File", widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx,.xls'}))

class BatchRoomLabSimpleMappingForm(forms.ModelForm):
    class Meta:
        model = BatchRoomLabMapping
        fields = ['batch', 'room', 'lab']
        widgets = {
            'batch': forms.Select(attrs={'class': 'form-select'}),
            'room': forms.Select(attrs={'class': 'form-select'}),
            'lab': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        department = kwargs.pop('department', None)
        super().__init__(*args, **kwargs)
        
        if department:
            self.fields['batch'].queryset = Batch.objects.filter(department=department)
            self.fields['room'].queryset = Room.objects.filter(department=department)
            self.fields['lab'].queryset = Lab.objects.filter(department=department)

class UploadExcelTimetableForm(forms.Form):
    name = forms.CharField(max_length=100, label="Timetable Name", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Fall 2024'}))
    file = forms.FileField(label="Upload Excel File", widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx,.xls'}))