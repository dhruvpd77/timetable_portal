import pandas as pd

def entries_to_df(entries):
    return pd.DataFrame([{
        "Day": e.day,
        "Time": e.time,
        "Batch": e.batch.name if e.batch else "",
        "Subject": e.subject.subject_name if e.subject else "",
        "Faculty": e.faculty.full_name if e.faculty else "",
        "Room": e.room.name if e.room else (e.lab.name if e.lab else ""),
        "Sub-Batch": e.sub_batch or "",
    } for e in entries])
import re

def clean_html(raw_html):
    # Replace <br> with newline, then remove tags.
    text = re.sub(r'<br\s*/?>', '\n', raw_html)
    text = re.sub(r'<.*?>', '', text)
    return text.strip()

def get_room_lab_availability(grid, days_order, slots_order, resource_type='room'):
    from collections import defaultdict
    resources = set()
    for row in grid:
        for slot in slots_order:
            html = clean_html(row.get(slot, ""))
            lines = [line.strip() for line in html.split("\n") if line.strip()]
            if lines:
                res = lines[2] if len(lines) > 2 else ""
                if res: resources.add(res)
    availability = defaultdict(lambda: defaultdict(str))
    for res in resources:
        for day in days_order:
            for slot in slots_order:
                availability[res][f"{day} {slot}"] = "Free"
    for row in grid:
        day = row["day"]
        for slot in slots_order:
            html = clean_html(row.get(slot, ""))
            lines = [line.strip() for line in html.split("\n") if line.strip()]
            if lines:
                res = lines[2] if len(lines) > 2 else ""
                if res:
                    key = f"{day} {slot}"
                    availability[res][key] = "Occupied"
    return availability, sorted(resources)
def subject_faculty_matrix_per_dept(grid, days_order, slots_order, selected_depts):
    # Map: dept_name: { 'subjects': {subject: {faculty: count, ...}}, 'faculties': [faculty, ...] }
    from collections import defaultdict
    matrix = {}
    for dept in selected_depts + ['ALL']:
        matrix[dept] = {'subjects': defaultdict(dict), 'faculties': set()}

    for row in grid:
        batch = row["batch"]
        dept = next((d for d in selected_depts if d in batch), 'ALL')
        for slot in slots_order:
            html = clean_html(row.get(slot, ""))
            lines = [line.strip() for line in html.split("\n") if line.strip()]
            if len(lines) >= 2:
                subj, faculty = lines[0], lines[1]
                # Per-dept
                matrix[dept]['subjects'][subj][faculty] = matrix[dept]['subjects'][subj].get(faculty, 0) + 1
                matrix[dept]['faculties'].add(faculty)
                # Combined ALL
                matrix['ALL']['subjects'][subj][faculty] = matrix['ALL']['subjects'][subj].get(faculty, 0) + 1
                matrix['ALL']['faculties'].add(faculty)
    # Convert set to list for template
    for dept in matrix:
        matrix[dept]['faculties'] = sorted(matrix[dept]['faculties'])
    return matrix
# reports/utils.py
from core.models import Timetable, TimetableEntry, TimeSettings, CourseSpec, Faculty, Batch, Room, Lab

def get_combined_grid(college, selected_depts, selected_tt_ids):
    # Get all selected Timetables
    entries = TimetableEntry.objects.filter(
        timetable__id__in=selected_tt_ids,
        timetable__department__name__in=selected_depts,
        timetable__department__college__name=college
    ).select_related('subject', 'faculty', 'batch', 'room', 'lab', 'timetable')

    # Get unique Batches
    batches = list({e.batch.name for e in entries if e.batch})

    # Get unique days/times from TimeSettings (use the first available)
    time_settings = TimeSettings.objects.filter(department__college__name=college, department__name__in=selected_depts).first()
    if time_settings:
        days_order = [d.name for d in time_settings.selected_days.all()]
        slots_order = [f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}" for s in time_settings.selected_slots.all()]
    else:
        # fallback: infer from entries
        days_order = sorted(list({e.day for e in entries}))
        slots_order = sorted(list({e.time for e in entries}))

    # Build grid: a list of dicts [{day, batch, slot1, slot2, ...}]
    grid = []
    for day in days_order:
        for batch in batches:
            row = {"day": day, "batch": batch}
            for slot in slots_order:
                entry = next(
                    (e for e in entries if e.day == day and e.batch and e.batch.name == batch and (
                        (hasattr(e, "time") and e.time == slot) or
                        (hasattr(e, "slot") and getattr(e, "slot") == slot)
                    )), 
                    None
                )
                if entry:
                    subj = entry.subject.subject_name if entry.subject else ''
                    fac = entry.faculty.short_name if entry.faculty else ''
                    room = entry.room.name if entry.room else (entry.lab.name if entry.lab else '')
                    row[slot] = f"{subj}<br>{fac}<br>{room}"
                else:
                    row[slot] = ""
            grid.append(row)
    timetable_names = list(Timetable.objects.filter(id__in=selected_tt_ids).values_list('name', flat=True))
    timetable_name = ', '.join(timetable_names)

    return grid, days_order, slots_order, batches, timetable_name
import matplotlib.pyplot as plt
import io
import base64

def chart_to_base64(x, y, title, xlabel, ylabel, color='skyblue'):
    plt.figure(figsize=(8, 4))
    plt.bar(x, y, color=color)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')
