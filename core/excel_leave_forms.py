from django import forms
from django.core.exceptions import ValidationError
import pandas as pd
import io

class ExcelTimetableUploadForm(forms.Form):
    excel_file = forms.FileField(
        label='Upload Timetable Excel File',
        help_text='Upload an Excel file containing the timetable data',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx,.xls'
        })
    )
    
    def clean_excel_file(self):
        excel_file = self.cleaned_data.get('excel_file')
        if not excel_file:
            raise ValidationError('Please select an Excel file to upload.')
        
        # Check file extension
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            raise ValidationError('Please upload a valid Excel file (.xlsx or .xls)')
        
        try:
            # Try to read the Excel file
            if excel_file.name.endswith('.xlsx'):
                df = pd.read_excel(excel_file, engine='openpyxl')
            else:
                df = pd.read_excel(excel_file, engine='xlrd')
            
            # Basic validation - check if it has the expected structure
            if df.empty:
                raise ValidationError('The Excel file appears to be empty.')
            
            # Store the dataframe for later use
            self.excel_data = df
            return excel_file
            
        except Exception as e:
            raise ValidationError(f'Error reading Excel file: {str(e)}')

class FacultyDaySelectionForm(forms.Form):
    faculty = forms.ChoiceField(
        label='Select Faculty',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    day = forms.ChoiceField(
        label='Select Day',
        choices=[
            ('Monday', 'Monday'),
            ('Tuesday', 'Tuesday'),
            ('Wednesday', 'Wednesday'),
            ('Thursday', 'Thursday'),
            ('Friday', 'Friday'),
            ('Saturday', 'Saturday'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, faculty_choices=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if faculty_choices:
            self.fields['faculty'].choices = faculty_choices

class LeaveReassignmentForm(forms.Form):
    replacement_faculty = forms.ChoiceField(
        label='Select Replacement Faculty',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, available_faculty=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if available_faculty:
            self.fields['replacement_faculty'].choices = available_faculty
