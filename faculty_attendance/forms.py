from django import forms
from core.models import College, Department

class CollegeDepartmentSelectionForm(forms.Form):
    college = forms.ModelChoiceField(queryset=College.objects.all(), label="Select College")
    department = forms.ModelChoiceField(queryset=Department.objects.none(), label="Select Department")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'college' in self.data:
            try:
                college_id = int(self.data.get('college'))
                self.fields['department'].queryset = Department.objects.filter(college_id=college_id)
            except (ValueError, TypeError):
                pass
        elif self.initial.get('college'):
            self.fields['department'].queryset = Department.objects.filter(college=self.initial['college'])
# faculty_attendance/forms.py
from django import forms
from core.models import Department, Faculty

class FacultyUserCreationForm(forms.Form):
    department = forms.ModelChoiceField(queryset=Department.objects.all(), label="Select Department")
    faculty = forms.ModelChoiceField(queryset=Faculty.objects.none(), label="Select Faculty (No user created yet)")
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)
    
    def __init__(self, *args, **kwargs):
        super(FacultyUserCreationForm, self).__init__(*args, **kwargs)
        if 'department' in self.data:
            try:
                department_id = int(self.data.get('department'))
                self.fields['faculty'].queryset = Faculty.objects.filter(department_id=department_id, user__isnull=True)
            except (ValueError, TypeError):
                pass  # invalid input, leave faculty queryset empty
        else:
            self.fields['faculty'].queryset = Faculty.objects.none()
