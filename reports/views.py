from django.shortcuts import render
from core.models import TimetableEntry, Department, Timetable, Faculty, Batch, College, TimeSettings

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from core.models import TimetableEntry, Department, Timetable, Faculty, College, TimeSettings

@login_required
def faculty_report(request):
    user = request.user
    user_department = getattr(user, 'department', None)

    if not user_department:
        return render(request, 'reports/faculty_report.html', {'error': 'No department assigned to user.'})

    selected_tt = request.GET.get('timetable', '')
    selected_faculty = request.GET.get('faculty', '')

    timetables = Timetable.objects.filter(department=user_department).values_list('name', flat=True)
    faculties = Faculty.objects.filter(department=user_department).values_list('full_name', flat=True)

    # Get day and slot order
    ts = TimeSettings.objects.filter(department=user_department).first()
    days_order = [d.name for d in ts.selected_days.all()] if ts else []
    slots_order = [f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}" for s in ts.selected_slots.all()] if ts else []

    report_grid = {}
    day_batches = {}

    if selected_tt and selected_faculty:
        tt = Timetable.objects.filter(name=selected_tt, department=user_department).first()
        if tt:
            entries = TimetableEntry.objects.filter(timetable=tt, faculty__full_name=selected_faculty)
            for day in days_order:
                report_grid[day] = {}
                day_batches[day] = []
                for slot in slots_order:
                    report_grid[day][slot] = {}
                    slot_entries = entries.filter(day=day, time=slot)
                    for entry in slot_entries:
                        batch = entry.batch.name
                        if batch not in day_batches[day]:
                            day_batches[day].append(batch)
                        report_grid[day][slot][batch] = {
                            'subject': entry.subject.subject_name,
                            'room_lab': entry.room.name if entry.room else (entry.lab.name if entry.lab else "")
                        }

    context = {
        'timetables': timetables,
        'faculties': faculties,
        'selected_tt': selected_tt,
        'selected_faculty': selected_faculty,
        'days_order': days_order,
        'slots_order': slots_order,
        'report_grid': report_grid,
        'day_batches': day_batches,
    }
    return render(request, 'reports/faculty_report.html', context)

from django.shortcuts import render, redirect
from core.models import College, Department, Timetable, Faculty, Batch, Room, Lab, TimeSettings, TimetableEntry
import pandas as pd
import json


def report_dashboard(request):
    colleges = College.objects.values_list('name', flat=True)
    selected_college = request.GET.get('college', '')
    departments = []
    timetables = []
    faculties = []
    batches = []
    context = {}

    if selected_college:
        departments = Department.objects.filter(college__name=selected_college).values_list('name', flat=True)
    selected_dept = request.GET.get('department', '')
    if selected_college and selected_dept:
        timetables = Timetable.objects.filter(
            department__name=selected_dept, department__college__name=selected_college
        ).values_list('name', flat=True)
        faculties = Faculty.objects.filter(
            department__name=selected_dept, department__college__name=selected_college
        ).values_list('full_name', flat=True)
        batches = Batch.objects.filter(
            department__name=selected_dept, department__college__name=selected_college
        ).values_list('name', flat=True)
    
    context.update({
        'colleges': colleges,
        'departments': departments,
        'timetables': timetables,
        'faculties': faculties,
        'batches': batches,
        'selected_college': selected_college,
        'selected_dept': selected_dept,
        'selected_tt': request.GET.get('timetable', ''),
        'selected_faculty': request.GET.get('faculty', ''),
        'selected_batch': request.GET.get('batch', ''),
    })

    return render(request, 'reports/report_dashboard.html', context)


import io
import pandas as pd
from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.models import Timetable, TimetableEntry, Batch, Department
from xhtml2pdf import pisa
from django.template.loader import render_to_string


def entries_to_grid(entries, days_order, slots_order, batch_name):
    """Helper: Build the timetable grid for a batch"""
    grid = []
    for day in days_order:
        row = {"day": day}
        for slot in slots_order:
            # Find entry for this day, slot and batch
            e = next(
                (en for en in entries if en.day == day and en.time == slot and en.batch.name == batch_name),
                None,
            )
            if e:
                subj = e.subject.subject_name if e.subject else ""
                fac = e.faculty.short_name if e.faculty else ""
                room = e.room.name if e.room else (e.lab.name if e.lab else "")
                row[slot] = f"{subj}<br>{fac}<br>{room}"
            else:
                row[slot] = "-"
        grid.append(row)
    return grid


@login_required
def batch_timetable(request):
    user_dept = request.user.department  # Assuming user has department foreign key
    college = user_dept.college.name

    timetables = Timetable.objects.filter(department=user_dept).values_list("name", flat=True).distinct()
    selected_tt = request.GET.get("timetable")
    batch = request.GET.get("batch")

    batches = []
    grid = []
    days_order = []
    slots_order = []
    error = None

    if selected_tt:
        timetable_qs = Timetable.objects.filter(name=selected_tt, department=user_dept)
        if timetable_qs.exists():
            timetable = timetable_qs.first()
            # Get batches related to this timetable
            entry_batches = TimetableEntry.objects.filter(timetable=timetable).values_list("batch__name", flat=True).distinct()
            batches = sorted(set(b for b in entry_batches if b))

            # Get days and slots from TimeSettings for department
            from core.models import TimeSettings

            time_settings = TimeSettings.objects.filter(department=user_dept).first()
            if time_settings:
                days_order = [d.name for d in time_settings.selected_days.all()]
                slots_order = [f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}" for s in time_settings.selected_slots.all()]
            else:
                # fallback: infer from entries
                entries_all = TimetableEntry.objects.filter(timetable=timetable)
                days_order = sorted(list(set(e.day for e in entries_all)))
                slots_order = sorted(list(set(e.time for e in entries_all)))

            if batch:
                if batch not in batches:
                    error = "Invalid batch selected."
                else:
                    entries = TimetableEntry.objects.filter(timetable=timetable, batch__name=batch)
                    grid = entries_to_grid(entries, days_order, slots_order, batch)
        else:
            error = "Selected timetable not found or access denied."

    context = {
        "college": college,
        "department": user_dept.name,
        "timetables": timetables,
        "selected_tt": selected_tt,
        "batches": batches,
        "batch": batch,
        "grid": grid,
        "days": days_order,
        "slots": slots_order,
        "error": error,
    }
    return render(request, "reports/batch_timetable.html", context)


@login_required
def batch_timetable_download(request):
    """
    Download the batch timetable as Excel or PDF.
    Expects GET parameters:
     - timetable (name)
     - batch (name)
     - format (pdf or excel)
    """
    user_dept = request.user.department
    selected_tt = request.GET.get("timetable")
    batch = request.GET.get("batch")
    file_format = request.GET.get("format", "pdf").lower()

    # Validate inputs
    if not selected_tt or not batch:
        return HttpResponse("Please select both timetable and batch.", status=400)

    timetable_qs = Timetable.objects.filter(name=selected_tt, department=user_dept)
    if not timetable_qs.exists():
        return HttpResponse("Timetable not found or access denied.", status=404)

    timetable = timetable_qs.first()
    entry_batches = TimetableEntry.objects.filter(timetable=timetable).values_list("batch__name", flat=True).distinct()
    if batch not in entry_batches:
        return HttpResponse(f"Batch '{batch}' is not part of selected timetable.", status=404)

    # Get entries and build grid
    entries = TimetableEntry.objects.filter(timetable=timetable, batch__name=batch)

    # Fetch days and slots similar to above
    from core.models import TimeSettings

    time_settings = TimeSettings.objects.filter(department=user_dept).first()
    if time_settings:
        days_order = [d.name for d in time_settings.selected_days.all()]
        slots_order = [f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}" for s in time_settings.selected_slots.all()]
    else:
        days_order = sorted(list(set(e.day for e in entries)))
        slots_order = sorted(list(set(e.time for e in entries)))

    grid = entries_to_grid(entries, days_order, slots_order, batch)

    if file_format == "excel":
        # Create Excel file in memory
        output = io.BytesIO()

        # Prepare DataFrame similar to grid but tabular with rows and columns
        # Rows by Day, columns by slots

        data = []
        for row in grid:
            rowdata = {"Day": row["day"]}
            for slot in slots_order:
                cell = row.get(slot, "-")
                # Strip html <br> to newline for Excel
                cell_text = cell.replace("<br>", "\n") if cell else "-"
                rowdata[slot] = cell_text
            data.append(rowdata)

        df = pd.DataFrame(data)

        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Batch Timetable")
            workbook = writer.book
            worksheet = writer.sheets["Batch Timetable"]

            # Format header
            header_format = workbook.add_format({
                "bold": True,
                "text_wrap": True,
                "valign": "top",
                "fg_color": "#4F81BD",
                "font_color": "white",
                "border": 1,
            })
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)

            # Format wrapping text for timetable cells
            cell_format = workbook.add_format({"text_wrap": True, "valign": "top"})
            worksheet.set_column(0, len(df.columns) - 1, 25, cell_format)

        output.seek(0)
        filename = f"{selected_tt}_{batch}_timetable.xlsx"
        response = HttpResponse(output, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    elif file_format == "pdf":
        # Render HTML template for PDF
        context = {
            "college": user_dept.college.name,
            "department": user_dept.name,
            "timetable": selected_tt,
            "batch": batch,
            "grid": grid,
            "slots": slots_order,
        }
        html = render_to_string("reports/batch_timetable_pdf.html", context)

        result = io.BytesIO()
        pdf_status = pisa.CreatePDF(io.StringIO(html), dest=result)
        if pdf_status.err:
            return HttpResponse("Error generating PDF", status=500)

        result.seek(0)
        filename = f"{selected_tt}_{batch}_timetable.pdf"

        response = HttpResponse(result, content_type="application/pdf")
        response["Content-Disposition"] = f"attachment; filename={filename}"
        return response

    else:
        return HttpResponse("Invalid format requested. Use 'pdf' or 'excel'.", status=400)
import io
import pandas as pd
from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.models import Timetable, TimetableEntry, Faculty, Department
from xhtml2pdf import pisa
from django.template.loader import render_to_string

@login_required
def faculty_availability(request):
    user_dept = request.user.department
    college = user_dept.college.name

    timetables = Timetable.objects.filter(department=user_dept).values_list("name", flat=True).distinct()
    selected_tt = request.GET.get("timetable")
    error = None
    grid = []
    days_order = []
    slots_order = []

    if selected_tt:
        timetable_qs = Timetable.objects.filter(name=selected_tt, department=user_dept)
        if not timetable_qs.exists():
            error = "Selected timetable not found or access denied."
        else:
            timetable = timetable_qs.first()

            # Get days and slots from TimeSettings for department
            from core.models import TimeSettings

            time_settings = TimeSettings.objects.filter(department=user_dept).first()
            if time_settings:
                days_order = [d.name for d in time_settings.selected_days.all()]
                slots_order = [f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}" for s in time_settings.selected_slots.all()]
            else:
                entries_all = TimetableEntry.objects.filter(timetable=timetable)
                days_order = sorted(list(set(e.day for e in entries_all)))
                slots_order = sorted(list(set(e.time for e in entries_all)))

            # Get all faculty in department
            all_faculties = list(Faculty.objects.filter(department=user_dept).values_list("short_name", flat=True))

            # For each day and slot, find faculties who are free in that slot (no TimetableEntry)
            grid = []
            for day in days_order:
                row = {"day": day}
                for slot in slots_order:
                    # Find faculties busy in this slot
                    busy_faculties_qs = TimetableEntry.objects.filter(
                        timetable=timetable,
                        day=day,
                        time=slot,
                        faculty__isnull=False,
                        faculty__department=user_dept
                    ).values_list("faculty__short_name", flat=True)

                    busy_faculties = set(busy_faculties_qs)
                    free_faculties = [f for f in all_faculties if f not in busy_faculties]
                    if free_faculties:
                        # Join free faculties with commas
                        row[slot] = ", ".join(free_faculties)
                    else:
                        row[slot] = "-"
                grid.append(row)

    context = {
        "college": college,
        "department": user_dept.name,
        "timetables": timetables,
        "selected_tt": selected_tt,
        "grid": grid,
        "days": days_order,
        "slots": slots_order,
        "error": error,
    }
    return render(request, "reports/faculty_availability.html", context)


@login_required
def faculty_availability_download(request):
    """
    Download the faculty availability as Excel or PDF.
    GET params:
    - timetable
    - format (pdf or excel)
    """
    user_dept = request.user.department
    selected_tt = request.GET.get("timetable")
    file_format = request.GET.get("format", "pdf").lower()

    if not selected_tt:
        return HttpResponse("Please select timetable.", status=400)

    timetable_qs = Timetable.objects.filter(name=selected_tt, department=user_dept)

    if not timetable_qs.exists():
        return HttpResponse("Timetable not found or access denied.", status=404)

    timetable = timetable_qs.first()

    from core.models import TimeSettings

    time_settings = TimeSettings.objects.filter(department=user_dept).first()
    if time_settings:
        days_order = [d.name for d in time_settings.selected_days.all()]
        slots_order = [f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}" for s in time_settings.selected_slots.all()]
    else:
        entries_all = TimetableEntry.objects.filter(timetable=timetable)
        days_order = sorted(list(set(e.day for e in entries_all)))
        slots_order = sorted(list(set(e.time for e in entries_all)))

    all_faculties = list(Faculty.objects.filter(department=user_dept).values_list("short_name", flat=True))

    grid = []
    for day in days_order:
        row = {"day": day}
        for slot in slots_order:
            busy_faculties_qs = TimetableEntry.objects.filter(
                timetable=timetable,
                day=day,
                time=slot,
                faculty__isnull=False,
                faculty__department=user_dept,
            ).values_list("faculty__short_name", flat=True)

            busy_faculties = set(busy_faculties_qs)
            free_faculties = [f for f in all_faculties if f not in busy_faculties]
            if free_faculties:
                row[slot] = ", ".join(free_faculties)
            else:
                row[slot] = "-"
        grid.append(row)

    if file_format == "excel":
        output = io.BytesIO()
        data = []
        for row in grid:
            rowdata = {"Day": row["day"]}
            for slot in slots_order:
                rowdata[slot] = row.get(slot, "-")
            data.append(rowdata)

        df = pd.DataFrame(data)

        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Faculty Availability")
            workbook = writer.book
            worksheet = writer.sheets["Faculty Availability"]

            header_format = workbook.add_format({
                "bold": True,
                "text_wrap": True,
                "valign": "top",
                "fg_color": "#4F81BD",
                "font_color": "white",
                "border": 1,
            })
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)

            cell_format = workbook.add_format({"text_wrap": True, "valign": "top"})
            worksheet.set_column(0, len(df.columns) - 1, 30, cell_format)

        output.seek(0)
        filename = f"{selected_tt}_faculty_availability.xlsx"
        response = HttpResponse(output, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    elif file_format == "pdf":
        context = {
            "college": user_dept.college.name,
            "department": user_dept.name,
            "timetable": selected_tt,
            "grid": grid,
            "slots": slots_order,
        }
        html = render_to_string("reports/faculty_availability_pdf.html", context)
        result = io.BytesIO()
        pdf_status = pisa.CreatePDF(io.StringIO(html), dest=result)
        if pdf_status.err:
            return HttpResponse("Error generating PDF", status=500)

        result.seek(0)
        filename = f"{selected_tt}_faculty_availability.pdf"
        response = HttpResponse(result, content_type="application/pdf")
        response["Content-Disposition"] = f"attachment; filename={filename}"
        return response

    else:
        return HttpResponse("Invalid format requested. Use 'pdf' or 'excel'.", status=400)
import io
import pandas as pd
from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.models import Timetable, TimetableEntry, Room, Lab
from xhtml2pdf import pisa
from django.template.loader import render_to_string

def build_combined_availability_grid(timetable, days_order, slots_order, user_dept):
    """Builds a grid showing free rooms and labs for each slot."""
    all_rooms = list(Room.objects.filter(department=user_dept).values_list("name", flat=True))
    all_labs = list(Lab.objects.filter(department=user_dept).values_list("name", flat=True))
    grid = []
    for day in days_order:
        row = {"day": day}
        for slot in slots_order:
            busy_rooms = set(TimetableEntry.objects.filter(
                timetable=timetable, day=day, time=slot, room__isnull=False, room__department=user_dept
            ).values_list("room__name", flat=True))
            busy_labs = set(TimetableEntry.objects.filter(
                timetable=timetable, day=day, time=slot, lab__isnull=False, lab__department=user_dept
            ).values_list("lab__name", flat=True))
            free_rooms = [r for r in all_rooms if r not in busy_rooms]
            free_labs = [l for l in all_labs if l not in busy_labs]
            room_str = ", ".join(free_rooms) if free_rooms else "-"
            lab_str = ", ".join(free_labs) if free_labs else "-"
            cell = f"<b>Rooms:</b> {room_str}<br><b>Labs:</b> {lab_str}"
            row[slot] = cell
        grid.append(row)
    return grid

@login_required
def room_lab_availability(request):
    user_dept = request.user.department
    college = user_dept.college.name
    timetables = Timetable.objects.filter(department=user_dept).values_list("name", flat=True).distinct()
    selected_tt = request.GET.get("timetable")
    error = None
    grid = []
    days_order = []
    slots_order = []
    if selected_tt:
        timetable_qs = Timetable.objects.filter(name=selected_tt, department=user_dept)
        if not timetable_qs.exists():
            error = "Selected timetable not found or access denied."
        else:
            timetable = timetable_qs.first()
            from core.models import TimeSettings
            time_settings = TimeSettings.objects.filter(department=user_dept).first()
            if time_settings:
                days_order = [d.name for d in time_settings.selected_days.all()]
                slots_order = [f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}" for s in time_settings.selected_slots.all()]
            else:
                entries_all = TimetableEntry.objects.filter(timetable=timetable)
                days_order = sorted(list(set(e.day for e in entries_all)))
                slots_order = sorted(list(set(e.time for e in entries_all)))
            grid = build_combined_availability_grid(timetable, days_order, slots_order, user_dept)
    context = {
        "college": college,
        "department": user_dept.name,
        "timetables": timetables,
        "selected_tt": selected_tt,
        "grid": grid,
        "days": days_order,
        "slots": slots_order,
        "error": error,
    }
    return render(request, "reports/room_lab_availability.html", context)

@login_required
def room_lab_availability_download(request):
    user_dept = request.user.department
    selected_tt = request.GET.get("timetable")
    file_format = request.GET.get("format", "pdf").lower()
    if not selected_tt:
        return HttpResponse("Please select timetable.", status=400)
    timetable_qs = Timetable.objects.filter(name=selected_tt, department=user_dept)
    if not timetable_qs.exists():
        return HttpResponse("Timetable not found or access denied.", status=404)
    timetable = timetable_qs.first()
    from core.models import TimeSettings
    time_settings = TimeSettings.objects.filter(department=user_dept).first()
    if time_settings:
        days_order = [d.name for d in time_settings.selected_days.all()]
        slots_order = [f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}" for s in time_settings.selected_slots.all()]
    else:
        entries_all = TimetableEntry.objects.filter(timetable=timetable)
        days_order = sorted(list(set(e.day for e in entries_all)))
        slots_order = sorted(list(set(e.time for e in entries_all)))
    grid = build_combined_availability_grid(timetable, days_order, slots_order, user_dept)

    if file_format == "excel":
        output = io.BytesIO()
        data = []
        for row in grid:
            rowdata = {"Day": row["day"]}
            for slot in slots_order:
                # Remove HTML tags for Excel output
                import re
                room_str = re.sub(r"<.*?>", "", row[slot]).replace("Rooms: ", "Rooms:").replace("Labs: ", "Labs:")
                rowdata[slot] = room_str.strip()
            data.append(rowdata)
        df = pd.DataFrame(data)
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Room-Lab Availability")
            workbook = writer.book
            worksheet = writer.sheets["Room-Lab Availability"]
            header_format = workbook.add_format({
                "bold": True, "text_wrap": True, "valign": "top",
                "fg_color": "#4F81BD", "font_color": "white", "border": 1
            })
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            cell_format = workbook.add_format({"text_wrap": True, "valign": "top"})
            worksheet.set_column(0, len(df.columns) - 1, 35, cell_format)
        output.seek(0)
        filename = f"{selected_tt}_room_lab_availability.xlsx"
        response = HttpResponse(output, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    elif file_format == "pdf":
        context = {
            "college": user_dept.college.name, "department": user_dept.name, "timetable": selected_tt,
            "grid": grid, "slots": slots_order,
        }
        html = render_to_string("reports/room_lab_availability_pdf.html", context)
        result = io.BytesIO()
        pdf_status = pisa.CreatePDF(io.StringIO(html), dest=result)
        if pdf_status.err:
            return HttpResponse("Error generating PDF", status=500)
        result.seek(0)
        filename = f"{selected_tt}_room_lab_availability.pdf"
        response = HttpResponse(result, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    else:
        return HttpResponse("Invalid format requested. Use 'pdf' or 'excel'.", status=400)
import io
import pandas as pd
from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.models import (
    College, Department, Timetable, TimetableEntry,
    TimeSettings, Room, Lab, Faculty
)
from xhtml2pdf import pisa
from django.template.loader import render_to_string


# Utility function to get time settings (days and slots) for departments (use first dept)
def get_time_settings(department_names, college):
    first_dept = Department.objects.filter(name=department_names[0], college=college).first()
    if not first_dept:
        return [], []
    ts = TimeSettings.objects.filter(department=first_dept).first()
    if ts:
        days_order = [d.name for d in ts.selected_days.all()]
        slots_order = [f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}" for s in ts.selected_slots.all()]
    else:
        days_order, slots_order = [], []
    return days_order, slots_order


# Helper to fetch combined entries
def get_combined_entries(selected_departments, selected_timetables, college):
    return TimetableEntry.objects.filter(
        timetable__name__in=selected_timetables,
        timetable__department__name__in=selected_departments,
        timetable__department__college=college
    ).select_related("subject", "faculty", "batch", "room", "lab", "timetable")


# Helper: build timetable grid for combined timetable
def build_combined_timetable_grid(entries, days_order, slots_order, batches):
    grid = []
    sorted_batches = sorted(batches)
    for day in days_order:
        for batch in sorted_batches:
            row = {"day": day, "batch": batch}
            for slot in slots_order:
                e = next(
                    (en for en in entries if en.day == day and en.time == slot and en.batch and en.batch.name == batch),
                    None,
                )
                if e:
                    subj = e.subject.subject_name if e.subject else ""
                    fac = e.faculty.short_name if e.faculty else ""
                    room = e.room.name if e.room else (e.lab.name if e.lab else "")
                    row[slot] = f"{subj}<br>{fac}<br>{room}"
                else:
                    row[slot] = "-"
            grid.append(row)
    return grid


# Helper for combined availability grids (room_lab or faculty)
def build_combined_availability_grid(entries, days_order, slots_order, resource_type, user_dept):
    """
    resource_type: one of 'room_lab', 'faculty'
    For 'room_lab', show free rooms and labs.
    For 'faculty', show free faculties.
    """
    grid = []

    if resource_type == "faculty":
        all_faculties = list(Faculty.objects.filter(department__college=user_dept.college).values_list("short_name", flat=True))
        for day in days_order:
            row = {"day": day}
            for slot in slots_order:
                busy_qs = entries.filter(day=day, time=slot).exclude(faculty__isnull=True)
                busy_faculties = set(busy_qs.values_list("faculty__short_name", flat=True))
                free_faculties = [f for f in all_faculties if f not in busy_faculties]
                row[slot] = ", ".join(free_faculties) if free_faculties else "-"
            grid.append(row)
    elif resource_type == "room_lab":
        all_rooms = list(Room.objects.filter(department__college=user_dept.college).values_list("name", flat=True))
        all_labs = list(Lab.objects.filter(department__college=user_dept.college).values_list("name", flat=True))
        for day in days_order:
            row = {"day": day}
            for slot in slots_order:
                busy_rooms = set(entries.filter(day=day, time=slot, room__isnull=False).values_list("room__name", flat=True))
                busy_labs = set(entries.filter(day=day, time=slot, lab__isnull=False).values_list("lab__name", flat=True))
                free_rooms = [r for r in all_rooms if r not in busy_rooms]
                free_labs = [l for l in all_labs if l not in busy_labs]
                rooms_str = ", ".join(free_rooms) if free_rooms else "-"
                labs_str = ", ".join(free_labs) if free_labs else "-"
                row[slot] = f"<b>Rooms:</b> {rooms_str}<br><b>Labs:</b> {labs_str}"
            grid.append(row)
    else:
        grid = []

    return grid


# --- Combined Timetable View --- #
@login_required
def combined_timetable(request):
    user_college = request.user.department.college
    college = user_college.name

    departments_qs = Department.objects.filter(college=user_college).order_by("name")
    department_names = [d.name for d in departments_qs]

    selected_departments = request.GET.getlist("departments")
    selected_timetables = request.GET.getlist("timetables")

    # Get timetables for selected departments (or empty)
    if selected_departments:
        timetables_qs = Timetable.objects.filter(department__name__in=selected_departments)
        timetable_names_for_departments = list(timetables_qs.values_list("name", flat=True).distinct())
    else:
        timetable_names_for_departments = []

    error = None
    grid = []
    batches = set()
    days_order = []
    slots_order = []
    timetable_names = []

    if selected_departments and selected_timetables:
        entries = get_combined_entries(selected_departments, selected_timetables, user_college)
        batches = sorted(set(e.batch.name for e in entries if e.batch))

        days_order, slots_order = get_time_settings(selected_departments, user_college)

        if not days_order or not slots_order:
            # fallback
            days_order = sorted(set(e.day for e in entries))
            slots_order = sorted(set(e.time for e in entries))

        grid = build_combined_timetable_grid(entries, days_order, slots_order, batches)

        timetable_names = list(Timetable.objects.filter(name__in=selected_timetables).values_list("name", flat=True))

    context = {
        "college": college,
        "departments": department_names,
        "selected_departments": selected_departments,
        "timetables_for_departments": timetable_names_for_departments,
        "selected_timetables": selected_timetables,
        "grid": grid,
        "days": days_order,
        "slots": slots_order,
        "batches": batches,
        "timetable_names": timetable_names,
        "error": error,
    }
    return render(request, "reports/combined_timetable.html", context)


@login_required
def combined_timetable_download(request):
    user_college = request.user.department.college
    selected_departments = request.GET.getlist("departments")
    selected_timetables = request.GET.getlist("timetables")
    file_format = request.GET.get("format", "pdf").lower()

    if not selected_departments or not selected_timetables:
        return HttpResponse("Select departments and timetables.", status=400)

    entries = get_combined_entries(selected_departments, selected_timetables, user_college)
    batches = sorted(set(e.batch.name for e in entries if e.batch))
    days_order, slots_order = get_time_settings(selected_departments, user_college)

    if not days_order or not slots_order:
        days_order = sorted(set(e.day for e in entries))
        slots_order = sorted(set(e.time for e in entries))

    grid = build_combined_timetable_grid(entries, days_order, slots_order, batches)
    timetable_names = list(Timetable.objects.filter(name__in=selected_timetables).values_list("name", flat=True))

    if file_format == "excel":
        output = io.BytesIO()
        data = []
        for row in grid:
            rowdata = {"Day / Batch": f"{row['day']} / {row['batch']}"}
            for slot in slots_order:
                cell = row.get(slot, "-")
                cell_text = cell.replace("<br>", "\n") if cell else "-"
                rowdata[slot] = cell_text
            data.append(rowdata)

        df = pd.DataFrame(data)

        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Combined Timetable")
            workbook = writer.book
            worksheet = writer.sheets["Combined Timetable"]

            header_format = workbook.add_format({
                "bold": True,
                "text_wrap": True,
                "valign": "top",
                "fg_color": "#4F81BD",
                "font_color": "white",
                "border": 1,
            })
            for col_num, _ in enumerate(df.columns):
                worksheet.write(0, col_num, df.columns[col_num], header_format)

            cell_format = workbook.add_format({"text_wrap": True, "valign": "top"})
            worksheet.set_column(0, len(df.columns) - 1, 30, cell_format)

        output.seek(0)
        filename = f"Combined_Timetable_{'_'.join(selected_departments)}.xlsx"
        response = HttpResponse(
            output,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    elif file_format == "pdf":
        context = {
            "college": user_college.name,
            "department": ", ".join(selected_departments),
            "timetable_names": timetable_names,
            "grid": grid,
            "slots": slots_order,
        }
        html = render_to_string("reports/combined_timetable_pdf.html", context)
        result = io.BytesIO()
        pdf_status = pisa.CreatePDF(io.StringIO(html), dest=result)
        if pdf_status.err:
            return HttpResponse("Error generating PDF", status=500)

        result.seek(0)
        filename = f"Combined_Timetable_{'_'.join(selected_departments)}.pdf"
        response = HttpResponse(result, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    else:
        return HttpResponse("Invalid format requested (use pdf or excel)", status=400)


# --- Combined Room & Lab Availability --- #
@login_required
def combined_room_lab_availability(request):
    user_college = request.user.department.college
    college = user_college.name

    departments_qs = Department.objects.filter(college=user_college).order_by("name")
    department_names = [d.name for d in departments_qs]

    selected_departments = request.GET.getlist("departments")
    selected_timetables = request.GET.getlist("timetables")
    error = None
    grid = []
    days_order = []
    slots_order = []

    if selected_departments:
        timetables_qs = Timetable.objects.filter(department__name__in=selected_departments)
        timetable_names_for_departments = list(timetables_qs.values_list("name", flat=True).distinct())
    else:
        timetable_names_for_departments = []

    if selected_departments and selected_timetables:
        entries = get_combined_entries(selected_departments, selected_timetables, user_college)
        days_order, slots_order = get_time_settings(selected_departments, user_college)
        if not days_order or not slots_order:
            days_order = sorted(set(e.day for e in entries))
            slots_order = sorted(set(e.time for e in entries))
        grid = build_combined_availability_grid(entries, days_order, slots_order, "room_lab", request.user.department)

    context = {
        "college": college,
        "department": user_college.name,
        "departments": department_names,
        "selected_departments": selected_departments,
        "timetables_for_departments": timetable_names_for_departments,
        "selected_timetables": selected_timetables,
        "grid": grid,
        "days": days_order,
        "slots": slots_order,
        "error": error,
    }
    return render(request, "reports/combined_room_lab_availability.html", context)


@login_required
def combined_room_lab_availability_download(request):
    user_college = request.user.department.college
    selected_departments = request.GET.getlist("departments")
    selected_timetables = request.GET.getlist("timetables")
    file_format = request.GET.get("format", "pdf").lower()

    if not selected_departments or not selected_timetables:
        return HttpResponse("Select departments and timetables.", status=400)

    entries = get_combined_entries(selected_departments, selected_timetables, user_college)
    days_order, slots_order = get_time_settings(selected_departments, user_college)
    if not days_order or not slots_order:
        days_order = sorted(set(e.day for e in entries))
        slots_order = sorted(set(e.time for e in entries))

    grid = build_combined_availability_grid(entries, days_order, slots_order, "room_lab", request.user.department)

    if file_format == "excel":
        output = io.BytesIO()
        data = []
        import re
        for row in grid:
            rowdata = {"Day": row["day"]}
            for slot in slots_order:
                cell_html = row.get(slot, "-")
                text = re.sub(r"<.*?>", "", cell_html)
                rowdata[slot] = text.strip()
            data.append(rowdata)

        df = pd.DataFrame(data)
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Room_Lab Availability")
            workbook = writer.book
            worksheet = writer.sheets["Room_Lab Availability"]
            header_format = workbook.add_format({
                "bold": True, "text_wrap": True, "valign": "top",
                "fg_color": "#4F81BD", "font_color": "white", "border": 1,
            })
            for col_num, _ in enumerate(df.columns):
                worksheet.write(0, col_num, df.columns[col_num], header_format)

            cell_format = workbook.add_format({"text_wrap": True, "valign": "top"})
            worksheet.set_column(0, len(df.columns) - 1, 30, cell_format)

        output.seek(0)
        filename = f"Combined_Room_Lab_Availability_{'_'.join(selected_departments)}.xlsx"
        response = HttpResponse(
            output,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    elif file_format == "pdf":
        context = {
            "college": user_college.name,
            "department": ", ".join(selected_departments),
            "timetable_names": selected_timetables,
            "grid": grid,
            "slots": slots_order,
        }
        html = render_to_string("reports/combined_room_lab_availability_pdf.html", context)
        result = io.BytesIO()
        pdf_status = pisa.CreatePDF(io.StringIO(html), dest=result)
        if pdf_status.err:
            return HttpResponse("Error generating PDF", status=500)

        result.seek(0)
        filename = f"Combined_Room_Lab_Availability_{'_'.join(selected_departments)}.pdf"
        response = HttpResponse(result, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    else:
        return HttpResponse("Invalid format requested (use pdf or excel)", status=400)


# --- Combined Faculty Availability --- #
@login_required
def combined_faculty_availability(request):
    user_college = request.user.department.college
    college = user_college.name

    departments_qs = Department.objects.filter(college=user_college).order_by("name")
    department_names = [d.name for d in departments_qs]

    selected_departments = request.GET.getlist("departments")
    selected_timetables = request.GET.getlist("timetables")
    error = None
    grid = []
    days_order = []
    slots_order = []

    if selected_departments:
        timetables_qs = Timetable.objects.filter(department__name__in=selected_departments)
        timetable_names_for_departments = list(timetables_qs.values_list("name", flat=True).distinct())
    else:
        timetable_names_for_departments = []

    if selected_departments and selected_timetables:
        entries = get_combined_entries(selected_departments, selected_timetables, user_college)
        days_order, slots_order = get_time_settings(selected_departments, user_college)
        if not days_order or not slots_order:
            days_order = sorted(set(e.day for e in entries))
            slots_order = sorted(set(e.time for e in entries))
        grid = build_combined_availability_grid(entries, days_order, slots_order, "faculty", request.user.department)

    context = {
        "college": college,
        "department": user_college.name,
        "departments": department_names,
        "selected_departments": selected_departments,
        "timetables_for_departments": timetable_names_for_departments,
        "selected_timetables": selected_timetables,
        "grid": grid,
        "days": days_order,
        "slots": slots_order,
        "error": error,
    }
    return render(request, "reports/combined_faculty_availability.html", context)


@login_required
def combined_faculty_availability_download(request):
    user_college = request.user.department.college
    selected_departments = request.GET.getlist("departments")
    selected_timetables = request.GET.getlist("timetables")
    file_format = request.GET.get("format", "pdf").lower()

    if not selected_departments or not selected_timetables:
        return HttpResponse("Select departments and timetables.", status=400)

    entries = get_combined_entries(selected_departments, selected_timetables, user_college)
    days_order, slots_order = get_time_settings(selected_departments, user_college)
    if not days_order or not slots_order:
        days_order = sorted(set(e.day for e in entries))
        slots_order = sorted(set(e.time for e in entries))

    grid = build_combined_availability_grid(entries, days_order, slots_order, "faculty", request.user.department)

    if file_format == "excel":
        output = io.BytesIO()
        data = []
        for row in grid:
            rowdata = {"Day": row["day"]}
            for slot in slots_order:
                rowdata[slot] = row.get(slot, "-")
            data.append(rowdata)

        df = pd.DataFrame(data)

        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Faculty Availability")
            workbook = writer.book
            worksheet = writer.sheets["Faculty Availability"]

            header_format = workbook.add_format({
                "bold": True, "text_wrap": True, "valign": "top",
                "fg_color": "#4F81BD", "font_color": "white", "border": 1,
            })
            for col_num, _ in enumerate(df.columns):
                worksheet.write(0, col_num, df.columns[col_num], header_format)

            cell_format = workbook.add_format({"text_wrap": True, "valign": "top"})
            worksheet.set_column(0, len(df.columns) - 1, 30, cell_format)

        output.seek(0)
        filename = f"Combined_Faculty_Availability_{'_'.join(selected_departments)}.xlsx"
        response = HttpResponse(
            output,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    elif file_format == "pdf":
        context = {
            "college": user_college.name,
            "department": ", ".join(selected_departments),
            "timetable_names": selected_timetables,
            "grid": grid,
            "slots": slots_order,
        }
        html = render_to_string("reports/combined_faculty_availability_pdf.html", context)
        result = io.BytesIO()
        pdf_status = pisa.CreatePDF(io.StringIO(html), dest=result)
        if pdf_status.err:
            return HttpResponse("Error generating PDF", status=500)

        result.seek(0)
        filename = f"Combined_Faculty_Availability_{'_'.join(selected_departments)}.pdf"
        response = HttpResponse(result, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    else:
        return HttpResponse("Invalid format requested (use pdf or excel)", status=400)
from collections import defaultdict

def faculty_subject_matrix(entries, selected_depts):
    """
    Build matrix mapping: dept -> subject -> {faculty: lecture_count}
    and faculty list per dept.

    entries: queryset of TimetableEntry filtered to selected departments/timetables.
    selected_depts: list of department names.

    Returns:
      {
          dept1: {
              "subjects": {
                 subject1: {faculty1: count, faculty2: count, ...},
                 subject2: {...},
              },
              "faculties": set([...])
          },
          "ALL": {... combined overall ...}
      }
    """
    matrix = {dept: {"subjects": defaultdict(lambda: defaultdict(int)), "faculties": set()} for dept in selected_depts}
    matrix['ALL'] = {"subjects": defaultdict(lambda: defaultdict(int)), "faculties": set()}

    for e in entries:
        dept_name = e.timetable.department.name
        subj_name = e.subject.subject_name if e.subject else "Unknown"
        fac_name = e.faculty.short_name if e.faculty else "Unknown"

        # Update per department if in selected
        if dept_name in selected_depts:
            matrix[dept_name]["subjects"][subj_name][fac_name] += 1
            matrix[dept_name]["faculties"].add(fac_name)

        # Always update combined
        matrix['ALL']["subjects"][subj_name][fac_name] += 1
        matrix['ALL']["faculties"].add(fac_name)

    # Convert faculties sets to sorted lists for templates/JSON serialization
    for dept in matrix:
        matrix[dept]["faculties"] = sorted(matrix[dept]["faculties"])

    return matrix


def faculty_total_lectures(entries):
    """
    Returns: dict {faculty: total_lectures_count}
    """
    faculty_count = defaultdict(int)
    for e in entries:
        fac_name = e.faculty.short_name if e.faculty else "Unknown"
        faculty_count[fac_name] += 1
    return dict(sorted(faculty_count.items(), key=lambda x: x[1], reverse=True))


def slot_occupancy(entries, days_order, slots_order):
    """
    Returns occupancy counts per slot and day to visualize timetable fullness.
    Output: list of dicts {day, slot, count}
    """
    occupancy = defaultdict(lambda: defaultdict(int))
    for e in entries:
        if e.day and e.time:
            occupancy[e.day][e.time] += 1

    data = []
    for day in days_order:
        for slot in slots_order:
            count = occupancy.get(day, {}).get(slot, 0)
            data.append({"day": day, "slot": slot, "count": count})
    return data
import json
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.models import Department, Timetable, TimetableEntry, TimeSettings, Faculty

from xhtml2pdf import pisa
from django.template.loader import render_to_string
import io

@login_required
def combined_analytics(request):
    user_college = request.user.department.college
    college = user_college.name

    departments_qs = Department.objects.filter(college=user_college).order_by("name")
    department_names = [d.name for d in departments_qs]

    selected_departments = request.GET.getlist("departments") or []
    selected_timetables = request.GET.getlist("timetables") or []

    timetables_for_departments = []
    if selected_departments:
        timetables_qs = Timetable.objects.filter(department__name__in=selected_departments)
        timetables_for_departments = list(timetables_qs.values_list("name", flat=True).distinct())

    grid = None
    matrix = None
    total_lectures = None
    slot_data = None
    days_order = []
    slots_order = []
    error = None

    if selected_departments and selected_timetables:
        entries = TimetableEntry.objects.filter(
            timetable__name__in=selected_timetables,
            timetable__department__name__in=selected_departments,
            timetable__department__college=user_college
        ).select_related("subject", "faculty", "timetable")

        # Get time settings from first selected department
        first_dept = Department.objects.filter(name=selected_departments[0]).first()
        time_settings = TimeSettings.objects.filter(department=first_dept).first()
        if time_settings:
            days_order = [d.name for d in time_settings.selected_days.all()]
            slots_order = [f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}" for s in time_settings.selected_slots.all()]
        else:
            days_order = sorted(set(e.day for e in entries))
            slots_order = sorted(set(e.time for e in entries))

        # Analytics computations
        matrix = faculty_subject_matrix(entries, selected_departments)  # dept-wise faculty-subject map
        total_lectures = faculty_total_lectures(entries)
        slot_data = slot_occupancy(entries, days_order, slots_order)

    context = {
        "college": college,
        "departments": department_names,
        "selected_departments": selected_departments,
        "timetables_for_departments": timetables_for_departments,
        "selected_timetables": selected_timetables,
        "matrix": matrix,
        "total_lectures": total_lectures,
        "slot_data": json.dumps(slot_data),  # pass JSON string for JS chart
        "days": days_order,
        "slots": slots_order,
        "error": error,
    }

    return render(request, "reports/combined_analytics.html", context)

# Download combined analytics PDF (example for faculty-subject matrix + total lectures)

@login_required
def combined_analytics_download(request):
    user_college = request.user.department.college
    selected_departments = request.GET.getlist("departments")
    selected_timetables = request.GET.getlist("timetables")
    file_format = request.GET.get("format", "pdf").lower()

    if not selected_departments or not selected_timetables:
        return HttpResponse("Select departments and timetables to export analytics.", status=400)

    entries = TimetableEntry.objects.filter(
        timetable__name__in=selected_timetables,
        timetable__department__name__in=selected_departments,
        timetable__department__college=user_college
    ).select_related("subject", "faculty", "timetable")

    matrix = faculty_subject_matrix(entries, selected_departments)
    total_lectures = faculty_total_lectures(entries)

    if file_format == "pdf":
        context = {
            "college": user_college.name,
            "selected_departments": ", ".join(selected_departments),
            "matrix": matrix,
            "total_lectures": total_lectures,
        }
        html = render_to_string("reports/combined_analytics_pdf.html", context)
        result = io.BytesIO()
        pdf_status = pisa.CreatePDF(io.StringIO(html), dest=result)
        if pdf_status.err:
            return HttpResponse("Error generating PDF", status=500)

        result.seek(0)
        filename = f"Combined_Analytics_{'_'.join(selected_departments)}.pdf"
        response = HttpResponse(result, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    elif file_format == "excel":
        import pandas as pd
        output = io.BytesIO()

        # Example: Flatten matrix to DataFrame for Excel
        rows = []
        for dept, info in matrix.items():
            for subj, fac_dict in info['subjects'].items():
                for fac, count in fac_dict.items():
                    rows.append({
                        "Department": dept,
                        "Subject": subj,
                        "Faculty": fac,
                        "Lectures": count,
                    })
        df = pd.DataFrame(rows)
        # Total lectures summary DataFrame
        df_faculty = pd.DataFrame(
            [{"Faculty": fac, "Total Lectures": cnt} for fac, cnt in total_lectures.items()]
        )

        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="Faculty Subject Lectures")
            df_faculty.to_excel(writer, index=False, sheet_name="Faculty Total Lectures")

            workbook = writer.book
            # Format header and columns here if needed

        output.seek(0)
        filename = f"Combined_Analytics_{'_'.join(selected_departments)}.xlsx"
        response = HttpResponse(
            output,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    else:
        return HttpResponse("Unsupported format. Use pdf or excel.", status=400)


from core.models import CourseSpec, Faculty, Department

@login_required
def spin_wheel(request):
    user_college = request.user.department.college
    college = user_college.name

    departments_qs = Department.objects.filter(college=user_college).order_by("name")
    department_names = [d.name for d in departments_qs]

    selected_departments = request.GET.getlist("departments") or []
    selected_subject = request.GET.get("subject", "")

    subjects_for_departments = []
    faculties = []

    if selected_departments:
        subjects_qs = CourseSpec.objects.filter(department__name__in=selected_departments)
        subjects_for_departments = list(subjects_qs.values_list("subject_name", flat=True).distinct())

    if selected_subject and selected_departments:
        faculties_qs = Faculty.objects.filter(
            department__name__in=selected_departments,
            course__subject_name=selected_subject    # Adjust if your model relation differs
        ).distinct()
        faculties = list(faculties_qs.values_list("full_name", flat=True))

    context = {
        "college": college,
        "departments": department_names,
        "selected_departments": selected_departments,
        "selected_subject": selected_subject,
        "subjects": subjects_for_departments,
        "faculties": faculties,
    }
    return render(request, "reports/spin_wheel.html", context)
