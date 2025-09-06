from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from core.models import College, Department, Faculty, Batch, TimetableEntry
from attendance.models import Student
from .models import FacultyAttendance
from .forms import CollegeDepartmentSelectionForm
from django.http import JsonResponse, HttpResponse
from datetime import datetime
from collections import defaultdict
import json
from openpyxl import Workbook
from io import BytesIO

# AJAX view to fetch departments for selected college
def ajax_load_departments(request):
    college_id = request.GET.get('college_id')
    departments = Department.objects.filter(college_id=college_id).order_by('name')
    data = [{'id': d.id, 'name': d.name} for d in departments]
    return JsonResponse(data, safe=False)

# Login page: select college, department, enter username/password
def faculty_login(request):
    if request.method == 'POST':
        college_id = request.POST.get('college')
        department_id = request.POST.get('department')
        username = request.POST.get('username')
        password = request.POST.get('password')

        try:
            department = Department.objects.get(id=department_id)
        except Department.DoesNotExist:
            messages.error(request, 'Invalid department selected')
            department = None

        user = authenticate(request, username=username, password=password)
        if user is not None:
            # Check if user is faculty in that department
            if hasattr(user, 'faculty') and user.faculty.department == department:
                login(request, user)
                return redirect('faculty_attendance:attendance_entry')
            else:
                messages.error(request, 'User is not a faculty of selected department.')
        else:
            messages.error(request, 'Invalid username or password.')

    else:
        college_id = None

    form = CollegeDepartmentSelectionForm(initial={'college': college_id})
    context = {'form': form}
    return render(request, 'faculty_attendance/login.html', context)


# Attendance Entry Page
from collections import defaultdict
from datetime import datetime, timedelta, date

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from core.models import Faculty, Batch, TimetableEntry
from attendance.models import Student, AttendanceSessionWindow
from faculty_attendance.models import FacultyAttendance  # adjust app label as needed

from collections import defaultdict
from datetime import datetime, timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404

from collections import defaultdict
from datetime import datetime, timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404

@login_required
def attendance_entry(request):
    user_faculty = getattr(request.user, 'faculty', None)
    if not user_faculty:
        messages.error(request, "You are not authorized.")
        return redirect('faculty_attendance:faculty_login')

    # Get all faculties of this user's department, ordered by id
    faculty_list = Faculty.objects.filter(department=user_faculty.department).order_by('id')

    # Get faculty id from GET param or select first faculty in department by default
    selected_faculty_id = request.GET.get('faculty')
    if selected_faculty_id:
        selected_faculty = Faculty.objects.filter(id=selected_faculty_id, department=user_faculty.department).first()
    else:
        selected_faculty = faculty_list.first()

    if not selected_faculty:
        messages.error(request, "No faculty found in your department.")
        return redirect('faculty_attendance:faculty_login')

    # Fetch session window for the user's department
    session_window = AttendanceSessionWindow.objects.filter(department=user_faculty.department).first()

    def get_dates_for_faculty(faculty, session_window):
        if not faculty or not session_window:
            return []

        # Restrict timetable entries to the faculty and department
        entries = TimetableEntry.objects.filter(
            faculty=faculty,
            batch__department=user_faculty.department
        )
        days = {['monday','tuesday','wednesday','thursday','friday','saturday','sunday'].index(e.day.lower()) for e in entries if e.day}

        def dates_in_range(start, end):
            if not start or not end:
                return []
            result = []
            d = start
            while d <= end:
                if d.weekday() in days:
                    result.append(d)
                d += timedelta(days=1)
            return result

        all_dates = []
        for start, end in [
            (session_window.t1_start, session_window.t1_end),
            (session_window.t2_start, session_window.t2_end),
            (session_window.t3_start, session_window.t3_end),
            (session_window.t4_start, session_window.t4_end)
        ]:
            if start and end:
                all_dates.extend(dates_in_range(start, end))

        return sorted(set(all_dates))

    available_dates = get_dates_for_faculty(selected_faculty, session_window)

    selected_date_str = request.GET.get('date')
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            if selected_date not in available_dates:
                selected_date = available_dates[0] if available_dates else None
        except Exception:
            selected_date = available_dates[0] if available_dates else None
    else:
        selected_date = available_dates[0] if available_dates else None

    batches_with_lectures = []
    lecture_map = defaultdict(list)  # batch_id -> list of TimetableEntry

    selected_batch_id = request.GET.get('batch')
    selected_batch = None
    selected_lecture_number = request.GET.get('lecture_number')

    if selected_date:
        weekday_name = selected_date.strftime('%A')

        lectures = TimetableEntry.objects.filter(
            faculty=selected_faculty,
            day__iexact=weekday_name,
            batch__department=user_faculty.department,
        ).select_related('batch').order_by('time')

        for lec in lectures:
            lecture_map[lec.batch.id].append(lec)

        batches_with_lectures = list({lec.batch.id: lec.batch for lec in lectures}.values())
    else:
        lectures = []

    # Find selected batch from batches_with_lectures
    if selected_batch_id:
        try:
            selected_batch = next(b for b in batches_with_lectures if b.id == int(selected_batch_id))
        except (StopIteration, ValueError):
            selected_batch = None

    lectures_for_batch = lecture_map.get(selected_batch.id, []) if selected_batch else []

    # Students in selected batch
    if selected_batch:
        students = Student.objects.filter(department=user_faculty.department, batch=selected_batch.name)
    else:
        students = []

    # Attendance records to show summary and pre-fill absent students
    attendance_qs = FacultyAttendance.objects.filter(
        faculty=selected_faculty,
        date=selected_date,
    ).order_by('batch__name', 'lecture_number')

    attendance_dict = defaultdict(lambda: defaultdict(list))
    for att in attendance_qs:
        attendance_dict[att.batch.id][att.lecture_number] = att.absent_roll_numbers.split(',') if att.absent_roll_numbers else []

    if request.method == 'POST':
        # Delete attendance record
        if 'delete_attendance_id' in request.POST:
            delete_id = request.POST.get('delete_attendance_id')
            attendance_record = get_object_or_404(FacultyAttendance, id=delete_id)
            if attendance_record.faculty.department != user_faculty.department:
                messages.error(request, "You are not authorized to delete this attendance record.")
            else:
                attendance_record.delete()
                messages.success(request, "Attendance record deleted successfully.")
            redirect_url = f"{request.path}?faculty={selected_faculty.id}&date={selected_date}"
            if selected_batch:
                redirect_url += f"&batch={selected_batch.id}"
            if selected_lecture_number:
                redirect_url += f"&lecture_number={selected_lecture_number}"
            return redirect(redirect_url)

        # Save attendance
        batch_id = request.POST.get('batch')
        lecture_number = request.POST.get('lecture_number')
        absent_rolls = request.POST.getlist('absent_roll_numbers')
        if batch_id and lecture_number:
            batch_obj = Batch.objects.get(id=batch_id)
            all_rolls = list(Student.objects.filter(department=user_faculty.department, batch=batch_obj.name).values_list('roll_no', flat=True))
            present_rolls = [r for r in all_rolls if r not in absent_rolls]
            FacultyAttendance.objects.update_or_create(
                faculty=selected_faculty,
                date=selected_date,
                batch=batch_obj,
                lecture_number=lecture_number,
                defaults={
                    'absent_roll_numbers': ",".join(absent_rolls),
                    'present_roll_numbers': ",".join(present_rolls),
                }
            )
            messages.success(request, "Attendance saved successfully.")
            return redirect(f"{request.path}?faculty={selected_faculty.id}&date={selected_date}&batch={batch_id}&lecture_number={lecture_number}")
        else:
            messages.error(request, "Please select batch and lecture.")

    return render(request, "faculty_attendance/attendance_entry.html", {
        'faculty_list': faculty_list,
        'selected_faculty': selected_faculty,
        'available_dates': available_dates,
        'selected_date': selected_date,
        'batches_with_lectures': batches_with_lectures,
        'selected_batch': selected_batch,
        'lectures_for_batch': lectures_for_batch,
        'selected_lecture_number': selected_lecture_number,
        'students': students,
        'attendance_dict': attendance_dict,
        'attendance_qs': attendance_qs,
    })


@login_required
def faculty_logout(request):
    if request.method == "POST":
        logout(request)
        messages.info(request, "Logged out successfully.")
        return redirect('faculty_attendance:faculty_login')  # Change if your login URL name differs
     
@login_required
def download_attendance_excel(request):
    user_faculty = getattr(request.user, 'faculty', None)
    if not user_faculty:
        messages.error(request, "Not authorized")
        return redirect('faculty_attendance:faculty_login')

    faculty_id = request.GET.get('faculty', user_faculty.id)
    date_str = request.GET.get('date')
    batch_id = request.GET.get('batch')
    att_type = request.GET.get('type', 'absent')  # or 'present'

    if not date_str or not batch_id:
        messages.error(request, "Please select date and batch.")
        return redirect('faculty_attendance:attendance_entry')

    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    faculty = Faculty.objects.filter(id=faculty_id).first()
    batch = Batch.objects.filter(id=batch_id).first()

    attendances = FacultyAttendance.objects.filter(faculty=faculty, date=date_obj, batch=batch).order_by('lecture_number')
    students = Student.objects.filter(department=faculty.department, batch=batch.name).order_by('roll_no')

    wb = Workbook()
    ws = wb.active
    ws.title = f"{batch.name} Attendance {date_str}"

    ws.append(['Roll No', 'Name'])
    lecture_numbers = [att.lecture_number for att in attendances]
    ws.append([""] + [f'Lecture {ln}' for ln in lecture_numbers])

    # Map attendance by lecture number for quick lookup
    att_map = {att.lecture_number: att for att in attendances}

    for stu in students:
        row = [stu.roll_no, stu.name]
        for ln in lecture_numbers:
            att = att_map.get(ln)
            if att:
                if att_type == 'absent':
                    val = 'Absent' if stu.roll_no in (att.absent_roll_numbers or '') else 'Present'
                else:
                    val = 'Present' if stu.roll_no in (att.present_roll_numbers or '') else 'Absent'
            else:
                val = 'N/A'
            row.append(val)
        ws.append(row)

    # Adjust column widths
    for i, col_width in enumerate([15, 25] + [12]*len(lecture_numbers), 1):
        ws.column_dimensions[get_column_letter(i)].width = col_width

    memfile = BytesIO()
    wb.save(memfile)
    memfile.seek(0)
    filename = f"{batch.name}_{date_str}_attendance_{att_type}.xlsx"

    response = HttpResponse(
        memfile,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    return response

# faculty_attendance/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from core.models import Faculty
from .forms import FacultyUserCreationForm

def create_faculty_user(request):
    if request.method == 'POST':
        form = FacultyUserCreationForm(request.POST)
        if form.is_valid():
            faculty = form.cleaned_data['faculty']
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            # Check if username already exists
            if User.objects.filter(username=username).exists():
                messages.error(request, "Username already exists. Choose another.")
            else:
                # Create User and link to Faculty
                user = User.objects.create_user(username=username, password=password)
                faculty.user = user
                faculty.save()
                messages.success(request, f"User '{username}' created and linked to faculty '{faculty.full_name}'.")
                return redirect('faculty_attendance:faculty_login')
    else:
        form = FacultyUserCreationForm()
    return render(request, 'faculty_attendance/create_user.html', {'form': form})

def load_faculties(request):
    department_id = request.GET.get('department')
    faculties = Faculty.objects.filter(department_id=department_id, user__isnull=True).order_by('full_name')
    data = [{'id': f.id, 'name': f.full_name} for f in faculties]
    return JsonResponse(data, safe=False)
from datetime import timedelta, datetime

def get_dates_for_faculty(faculty, session_window):
    """
    Get all possible lecture dates for this faculty based on their TimetableEntries
    and the session windows (T1-T4).
    Returns a sorted list of dates.
    """
    if not session_window:
        return []

    # 1. Find all distinct week days (0=Monday..6=Sunday) of TimetableEntry for faculty
    entries = TimetableEntry.objects.filter(faculty=faculty)

    weekday_set = set()
    for entry in entries:
        try:
            day_idx = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'].index(entry.day.lower())
            weekday_set.add(day_idx)
        except:
            pass

    # 2. For each session window (T1..T4), build all dates that fall on those weekdays
    term_windows = [
        (session_window.t1_start, session_window.t1_end),
        (session_window.t2_start, session_window.t2_end),
        (session_window.t3_start, session_window.t3_end),
        (session_window.t4_start, session_window.t4_end),
    ]

    all_dates = []
    for start_date, end_date in term_windows:
        if not start_date or not end_date:
            continue
        current = start_date
        while current <= end_date:
            if current.weekday() in weekday_set:
                all_dates.append(current)
            current += timedelta(days=1)

    # Sort and remove duplicates just in case
    all_dates = sorted(list(set(all_dates)))
    return all_dates
