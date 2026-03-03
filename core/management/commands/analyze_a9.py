from django.core.management.base import BaseCommand
from core.models import Department, CourseAssignment, CourseSpec, Faculty, Batch, TimetableEntry, Timetable

class Command(BaseCommand):
    help = 'Analyze A9 batch assignments'

    def handle(self, *args, **options):
        # Get the department
        dept = Department.objects.filter(name='SY1_ODD_2025').first()
        if not dept:
            self.stdout.write('Department sy_1_odd_2025 not found')
            return
        
        self.stdout.write(f'Department: {dept.name} (ID: {dept.id})')
        self.stdout.write(f'College: {dept.college.name}')
        self.stdout.write('='*50)
        
        # Get all course assignments for this department
        assignments = CourseAssignment.objects.filter(department=dept).select_related('subject', 'faculty', 'batch')
        self.stdout.write(f'Total Course Assignments: {assignments.count()}')
        self.stdout.write('='*50)
        
        # Group by batch and faculty
        batch_faculty_hours = {}
        for assignment in assignments:
            batch_name = assignment.batch.name
            faculty_name = assignment.faculty.short_name
            subject_name = assignment.subject.subject_name
            hours = assignment.hours
            room_or_lab = assignment.room_or_lab
            
            if batch_name not in batch_faculty_hours:
                batch_faculty_hours[batch_name] = {}
            if faculty_name not in batch_faculty_hours[batch_name]:
                batch_faculty_hours[batch_name][faculty_name] = []
            
            batch_faculty_hours[batch_name][faculty_name].append({
                'subject': subject_name,
                'hours': hours,
                'room_or_lab': room_or_lab
            })
        
        # Print details for each batch
        for batch_name in sorted(batch_faculty_hours.keys()):
            self.stdout.write(f'\nBATCH: {batch_name}')
            self.stdout.write('-' * 30)
            for faculty_name in sorted(batch_faculty_hours[batch_name].keys()):
                assignments_list = batch_faculty_hours[batch_name][faculty_name]
                total_hours = sum(a['hours'] for a in assignments_list)
                self.stdout.write(f'  Faculty: {faculty_name} (Total: {total_hours} hours)')
                for assignment in assignments_list:
                    self.stdout.write(f'    - {assignment["subject"]}: {assignment["hours"]} hours ({assignment["room_or_lab"]})')
        
        # Check A9 batch specifically
        self.stdout.write('\n' + '='*50)
        self.stdout.write('SPECIFIC ANALYSIS FOR A9 BATCH:')
        self.stdout.write('='*50)
        if 'A9' in batch_faculty_hours:
            for faculty_name in sorted(batch_faculty_hours['A9'].keys()):
                assignments_list = batch_faculty_hours['A9'][faculty_name]
                total_hours = sum(a['hours'] for a in assignments_list)
                self.stdout.write(f'Faculty: {faculty_name} (Total: {total_hours} hours)')
                for assignment in assignments_list:
                    self.stdout.write(f'  - {assignment["subject"]}: {assignment["hours"]} hours ({assignment["room_or_lab"]})')
        
        # Get timetable entries for A9 batch
        self.stdout.write('\n' + '='*50)
        self.stdout.write('TIMETABLE ENTRIES FOR A9 BATCH:')
        self.stdout.write('='*50)
        timetable_entries = TimetableEntry.objects.filter(
            department=dept,
            batch__name='A9'
        ).select_related('subject', 'faculty', 'timetable')
        
        self.stdout.write(f'Total timetable entries for A9: {timetable_entries.count()}')
        
        # Group by faculty and count entries
        faculty_entry_count = {}
        for entry in timetable_entries:
            faculty_name = entry.faculty.short_name
            if faculty_name not in faculty_entry_count:
                faculty_entry_count[faculty_name] = 0
            faculty_entry_count[faculty_name] += 1
        
        for faculty_name, count in sorted(faculty_entry_count.items()):
            self.stdout.write(f'  {faculty_name}: {count} timetable entries')
        
        # Check if there are duplicate assignments
        self.stdout.write('\n' + '='*50)
        self.stdout.write('CHECKING FOR DUPLICATE ASSIGNMENTS IN A9:')
        self.stdout.write('='*50)
        a9_assignments = CourseAssignment.objects.filter(
            department=dept,
            batch__name='A9'
        ).select_related('subject', 'faculty')
        
        # Group by faculty and subject to check for duplicates
        faculty_subject_assignments = {}
        for assignment in a9_assignments:
            key = (assignment.faculty.short_name, assignment.subject.subject_name)
            if key not in faculty_subject_assignments:
                faculty_subject_assignments[key] = []
            faculty_subject_assignments[key].append(assignment)
        
        for (faculty, subject), assignments_list in faculty_subject_assignments.items():
            if len(assignments_list) > 1:
                self.stdout.write(f'DUPLICATE FOUND: {faculty} - {subject} has {len(assignments_list)} assignments:')
                for i, assignment in enumerate(assignments_list):
                    self.stdout.write(f'  Assignment {i+1}: ID={assignment.id}, Hours={assignment.hours}, Room/Lab={assignment.room_or_lab}')
