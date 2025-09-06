# attendance/forms.py
from django import forms

class StudentUploadForm(forms.Form):
    batch = forms.ModelChoiceField(queryset=None)
    csv_file = forms.FileField(label="Upload Student CSV")

    def __init__(self, department, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from core.models import Batch
        self.fields['batch'].queryset = Batch.objects.filter(department=department)
