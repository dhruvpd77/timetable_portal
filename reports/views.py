from django.shortcuts import render
from core.models import TimetableEntry, Department, Timetable, Faculty, Batch, College, TimeSettings

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from core.models import TimetableEntry, Department, Timetable, Faculty, College, TimeSettings

def normalize_slot(slot):
    """Normalize time slot format for comparison"""
    return slot.replace(' ', '').replace('–', '-').replace('—', '-')

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
                    # Use normalized comparison for time slots
                    slot_entries = [e for e in entries if e.day == day and normalize_slot(e.time) == normalize_slot(slot)]
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


@login_required
def faculty_report_download(request):
    """Download faculty timetable report as PDF or Excel."""
    import io
    from django.http import HttpResponse
    from xhtml2pdf import pisa
    from django.template.loader import render_to_string

    user = request.user
    user_department = getattr(user, 'department', None)
    if not user_department:
        return HttpResponse("No department assigned to user.", status=400)

    selected_tt = request.GET.get('timetable', '')
    selected_faculty = request.GET.get('faculty', '')
    file_format = request.GET.get('format', 'pdf').lower()

    if not selected_tt or not selected_faculty:
        return HttpResponse("Please select timetable and faculty.", status=400)

    ts = TimeSettings.objects.filter(department=user_department).first()
    days_order = [d.name for d in ts.selected_days.all()] if ts else []
    slots_order = [f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}" for s in ts.selected_slots.all()] if ts else []

    report_grid = {}
    day_batches = {}

    tt = Timetable.objects.filter(name=selected_tt, department=user_department).first()
    if not tt:
        return HttpResponse("Timetable not found.", status=404)

    entries = TimetableEntry.objects.filter(timetable=tt, faculty__full_name=selected_faculty)
    for day in days_order:
        report_grid[day] = {}
        day_batches[day] = []
        for slot in slots_order:
            report_grid[day][slot] = {}
            slot_entries = [e for e in entries if e.day == day and normalize_slot(e.time) == normalize_slot(slot)]
            for entry in slot_entries:
                batch = entry.batch.name
                if batch not in day_batches[day]:
                    day_batches[day].append(batch)
                report_grid[day][slot][batch] = {
                    'subject': entry.subject.subject_name,
                    'room_lab': entry.room.name if entry.room else (entry.lab.name if entry.lab else "")
                }

    if file_format == 'excel':
        output = io.BytesIO()
        data = []
        for day in days_order:
            if day_batches.get(day):
                for batch in day_batches[day]:
                    row = {'Day': day, 'Batch': batch}
                    for slot in slots_order:
                        cell = report_grid.get(day, {}).get(slot, {}).get(batch, {})
                        if cell and cell.get('subject'):
                            row[slot] = f"{cell['subject']}\n{cell.get('room_lab', '')}"
                        else:
                            row[slot] = '-'
                    data.append(row)

        df = pd.DataFrame(data)
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Faculty Timetable')
            workbook = writer.book
            worksheet = writer.sheets['Faculty Timetable']
            header_format = workbook.add_format({
                'bold': True, 'text_wrap': True, 'valign': 'top',
                'fg_color': '#2563eb', 'font_color': 'white', 'border': 1
            })
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            cell_format = workbook.add_format({'text_wrap': True, 'valign': 'top'})
            worksheet.set_column(0, len(df.columns) - 1, 18, cell_format)

        output.seek(0)
        filename = f"Faculty_Timetable_{selected_faculty.replace(' ', '_')}.xlsx"
        response = HttpResponse(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    elif file_format == 'pdf':
        context = {
            'college': user_department.college.name,
            'department': user_department.name,
            'timetable': selected_tt,
            'faculty': selected_faculty,
            'days_order': days_order,
            'slots_order': slots_order,
            'report_grid': report_grid,
            'day_batches': day_batches,
        }
        html = render_to_string('reports/faculty_report_pdf.html', context)
        result = io.BytesIO()
        pdf_status = pisa.CreatePDF(io.StringIO(html), dest=result)
        if pdf_status.err:
            return HttpResponse("Error generating PDF", status=500)
        result.seek(0)
        filename = f"Faculty_Timetable_{selected_faculty.replace(' ', '_')}.pdf"
        response = HttpResponse(result, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    return HttpResponse("Invalid format. Use pdf or excel.", status=400)


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
def build_combined_availability_grid_with_entries(entries, days_order, slots_order, resource_type, user_dept):
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
        grid = build_combined_availability_grid_with_entries(entries, days_order, slots_order, "room_lab", request.user.department)

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

    grid = build_combined_availability_grid_with_entries(entries, days_order, slots_order, "room_lab", request.user.department)

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
        grid = build_combined_availability_grid_with_entries(entries, days_order, slots_order, "faculty", request.user.department)

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

    grid = build_combined_availability_grid_with_entries(entries, days_order, slots_order, "faculty", request.user.department)

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


# Enhanced Analytics Helper Functions
def get_faculty_workload_analytics(entries):
    """Analyze faculty workload distribution and patterns"""
    faculty_stats = defaultdict(lambda: {
        'total_lectures': 0,
        'subjects': set(),
        'batches': set(),
        'days': set(),
        'rooms': set(),
        'labs': set(),
        'workload_by_day': defaultdict(int),
        'workload_by_subject': defaultdict(int)
    })
    
    for entry in entries:
        if entry.faculty:
            fac_name = entry.faculty.short_name
            faculty_stats[fac_name]['total_lectures'] += 1
            faculty_stats[fac_name]['subjects'].add(entry.subject.subject_name if entry.subject else 'Unknown')
            faculty_stats[fac_name]['batches'].add(entry.batch.name if entry.batch else 'Unknown')
            faculty_stats[fac_name]['days'].add(entry.day)
            if entry.room:
                faculty_stats[fac_name]['rooms'].add(entry.room.name)
            if entry.lab:
                faculty_stats[fac_name]['labs'].add(entry.lab.name)
            faculty_stats[fac_name]['workload_by_day'][entry.day] += 1
            faculty_stats[fac_name]['workload_by_subject'][entry.subject.subject_name if entry.subject else 'Unknown'] += 1
    
    # Convert sets to lists for JSON serialization
    result = {}
    for fac, stats in faculty_stats.items():
        result[fac] = {
            'total_lectures': stats['total_lectures'],
            'subject_count': len(stats['subjects']),
            'batch_count': len(stats['batches']),
            'day_count': len(stats['days']),
            'room_count': len(stats['rooms']),
            'lab_count': len(stats['labs']),
            'subjects': list(stats['subjects']),
            'batches': list(stats['batches']),
            'days': list(stats['days']),
            'rooms': list(stats['rooms']),
            'labs': list(stats['labs']),
            'workload_by_day': dict(stats['workload_by_day']),
            'workload_by_subject': dict(stats['workload_by_subject']),
            'avg_lectures_per_day': stats['total_lectures'] / len(stats['days']) if stats['days'] else 0
        }
    
    return result


def get_subject_distribution_analytics(entries):
    """Analyze subject distribution across faculty and batches"""
    subject_stats = defaultdict(lambda: {
        'total_lectures': 0,
        'faculties': set(),
        'batches': set(),
        'rooms': set(),
        'labs': set(),
        'lectures_by_faculty': defaultdict(int),
        'lectures_by_batch': defaultdict(int)
    })
    
    for entry in entries:
        if entry.subject:
            subj_name = entry.subject.subject_name
            subject_stats[subj_name]['total_lectures'] += 1
            if entry.faculty:
                subject_stats[subj_name]['faculties'].add(entry.faculty.short_name)
                subject_stats[subj_name]['lectures_by_faculty'][entry.faculty.short_name] += 1
            if entry.batch:
                subject_stats[subj_name]['batches'].add(entry.batch.name)
                subject_stats[subj_name]['lectures_by_batch'][entry.batch.name] += 1
            if entry.room:
                subject_stats[subj_name]['rooms'].add(entry.room.name)
            if entry.lab:
                subject_stats[subj_name]['labs'].add(entry.lab.name)
    
    result = {}
    for subj, stats in subject_stats.items():
        result[subj] = {
            'total_lectures': stats['total_lectures'],
            'faculty_count': len(stats['faculties']),
            'batch_count': len(stats['batches']),
            'room_count': len(stats['rooms']),
            'lab_count': len(stats['labs']),
            'faculties': list(stats['faculties']),
            'batches': list(stats['batches']),
            'rooms': list(stats['rooms']),
            'labs': list(stats['labs']),
            'lectures_by_faculty': dict(stats['lectures_by_faculty']),
            'lectures_by_batch': dict(stats['lectures_by_batch'])
        }
    
    return result


def get_room_lab_utilization_analytics(entries):
    """Analyze room and lab utilization patterns"""
    room_stats = defaultdict(lambda: {
        'total_usage': 0,
        'subjects': set(),
        'faculties': set(),
        'batches': set(),
        'days': set(),
        'usage_by_day': defaultdict(int),
        'usage_by_subject': defaultdict(int)
    })
    
    lab_stats = defaultdict(lambda: {
        'total_usage': 0,
        'subjects': set(),
        'faculties': set(),
        'batches': set(),
        'days': set(),
        'usage_by_day': defaultdict(int),
        'usage_by_subject': defaultdict(int)
    })
    
    for entry in entries:
        if entry.room:
            room_name = entry.room.name
            room_stats[room_name]['total_usage'] += 1
            room_stats[room_name]['subjects'].add(entry.subject.subject_name if entry.subject else 'Unknown')
            room_stats[room_name]['faculties'].add(entry.faculty.short_name if entry.faculty else 'Unknown')
            room_stats[room_name]['batches'].add(entry.batch.name if entry.batch else 'Unknown')
            room_stats[room_name]['days'].add(entry.day)
            room_stats[room_name]['usage_by_day'][entry.day] += 1
            room_stats[room_name]['usage_by_subject'][entry.subject.subject_name if entry.subject else 'Unknown'] += 1
        
        if entry.lab:
            lab_name = entry.lab.name
            lab_stats[lab_name]['total_usage'] += 1
            lab_stats[lab_name]['subjects'].add(entry.subject.subject_name if entry.subject else 'Unknown')
            lab_stats[lab_name]['faculties'].add(entry.faculty.short_name if entry.faculty else 'Unknown')
            lab_stats[lab_name]['batches'].add(entry.batch.name if entry.batch else 'Unknown')
            lab_stats[lab_name]['days'].add(entry.day)
            lab_stats[lab_name]['usage_by_day'][entry.day] += 1
            lab_stats[lab_name]['usage_by_subject'][entry.subject.subject_name if entry.subject else 'Unknown'] += 1
    
    # Convert to serializable format
    rooms_result = {}
    for room, stats in room_stats.items():
        rooms_result[room] = {
            'total_usage': stats['total_usage'],
            'subject_count': len(stats['subjects']),
            'faculty_count': len(stats['faculties']),
            'batch_count': len(stats['batches']),
            'day_count': len(stats['days']),
            'subjects': list(stats['subjects']),
            'faculties': list(stats['faculties']),
            'batches': list(stats['batches']),
            'days': list(stats['days']),
            'usage_by_day': dict(stats['usage_by_day']),
            'usage_by_subject': dict(stats['usage_by_subject']),
            'utilization_rate': stats['total_usage'] / len(stats['days']) if stats['days'] else 0
        }
    
    labs_result = {}
    for lab, stats in lab_stats.items():
        labs_result[lab] = {
            'total_usage': stats['total_usage'],
            'subject_count': len(stats['subjects']),
            'faculty_count': len(stats['faculties']),
            'batch_count': len(stats['batches']),
            'day_count': len(stats['days']),
            'subjects': list(stats['subjects']),
            'faculties': list(stats['faculties']),
            'batches': list(stats['batches']),
            'days': list(stats['days']),
            'usage_by_day': dict(stats['usage_by_day']),
            'usage_by_subject': dict(stats['usage_by_subject']),
            'utilization_rate': stats['total_usage'] / len(stats['days']) if stats['days'] else 0
        }
    
    return {'rooms': rooms_result, 'labs': labs_result}


def get_time_slot_occupancy_analytics(entries, days_order, slots_order):
    """Detailed time slot occupancy analysis"""
    occupancy = defaultdict(lambda: defaultdict(int))
    slot_details = defaultdict(lambda: defaultdict(list))
    
    for entry in entries:
        if entry.day and entry.time:
            occupancy[entry.day][entry.time] += 1
            slot_details[entry.day][entry.time].append({
                'subject': entry.subject.subject_name if entry.subject else 'Unknown',
                'faculty': entry.faculty.short_name if entry.faculty else 'Unknown',
                'batch': entry.batch.name if entry.batch else 'Unknown',
                'room': entry.room.name if entry.room else None,
                'lab': entry.lab.name if entry.lab else None
            })
    
    result = []
    for day in days_order:
        for slot in slots_order:
            count = occupancy.get(day, {}).get(slot, 0)
            details = slot_details.get(day, {}).get(slot, [])
            result.append({
                'day': day,
                'slot': slot,
                'occupancy_count': count,
                'details': details,
                'utilization_percentage': (count / len(slots_order)) * 100 if slots_order else 0
            })
    
    return result


def get_faculty_availability_patterns(entries, days_order, slots_order):
    """Analyze faculty availability patterns and free time slots"""
    faculty_busy = defaultdict(lambda: defaultdict(set))
    
    for entry in entries:
        if entry.faculty and entry.day and entry.time:
            faculty_busy[entry.faculty.short_name][entry.day].add(entry.time)
    
    # Get all faculties from entries
    all_faculties = set()
    for entry in entries:
        if entry.faculty:
            all_faculties.add(entry.faculty.short_name)
    
    result = {}
    for faculty in all_faculties:
        busy_slots = faculty_busy[faculty]
        free_slots = {}
        
        for day in days_order:
            busy_today = busy_slots.get(day, set())
            free_today = [slot for slot in slots_order if slot not in busy_today]
            free_slots[day] = free_today
        
        total_possible_slots = len(days_order) * len(slots_order)
        total_busy_slots = sum(len(slots) for slots in busy_slots.values())
        availability_percentage = ((total_possible_slots - total_busy_slots) / total_possible_slots) * 100 if total_possible_slots > 0 else 0
        
        result[faculty] = {
            'free_slots': free_slots,
            'busy_slots': {day: list(slots) for day, slots in busy_slots.items()},
            'total_busy_slots': total_busy_slots,
            'total_free_slots': total_possible_slots - total_busy_slots,
            'availability_percentage': availability_percentage
        }
    
    return result


def get_batch_workload_analytics(entries):
    """Analyze batch workload and subject distribution"""
    batch_stats = defaultdict(lambda: {
        'total_lectures': 0,
        'subjects': set(),
        'faculties': set(),
        'rooms': set(),
        'labs': set(),
        'days': set(),
        'lectures_by_subject': defaultdict(int),
        'lectures_by_faculty': defaultdict(int),
        'lectures_by_day': defaultdict(int)
    })
    
    for entry in entries:
        if entry.batch:
            batch_name = entry.batch.name
            batch_stats[batch_name]['total_lectures'] += 1
            batch_stats[batch_name]['subjects'].add(entry.subject.subject_name if entry.subject else 'Unknown')
            batch_stats[batch_name]['faculties'].add(entry.faculty.short_name if entry.faculty else 'Unknown')
            batch_stats[batch_name]['rooms'].add(entry.room.name if entry.room else 'Unknown')
            batch_stats[batch_name]['labs'].add(entry.lab.name if entry.lab else 'Unknown')
            batch_stats[batch_name]['days'].add(entry.day)
            batch_stats[batch_name]['lectures_by_subject'][entry.subject.subject_name if entry.subject else 'Unknown'] += 1
            batch_stats[batch_name]['lectures_by_faculty'][entry.faculty.short_name if entry.faculty else 'Unknown'] += 1
            batch_stats[batch_name]['lectures_by_day'][entry.day] += 1
    
    result = {}
    for batch, stats in batch_stats.items():
        result[batch] = {
            'total_lectures': stats['total_lectures'],
            'subject_count': len(stats['subjects']),
            'faculty_count': len(stats['faculties']),
            'room_count': len(stats['rooms']),
            'lab_count': len(stats['labs']),
            'day_count': len(stats['days']),
            'subjects': list(stats['subjects']),
            'faculties': list(stats['faculties']),
            'rooms': list(stats['rooms']),
            'labs': list(stats['labs']),
            'days': list(stats['days']),
            'lectures_by_subject': dict(stats['lectures_by_subject']),
            'lectures_by_faculty': dict(stats['lectures_by_faculty']),
            'lectures_by_day': dict(stats['lectures_by_day']),
            'avg_lectures_per_day': stats['total_lectures'] / len(stats['days']) if stats['days'] else 0
        }
    
    return result


def get_conflict_analysis(entries):
    """Analyze potential conflicts and overlaps"""
    conflicts = []
    
    # Group entries by day, time, and resource
    resource_usage = defaultdict(list)
    faculty_usage = defaultdict(list)
    batch_usage = defaultdict(list)
    
    for entry in entries:
        key = (entry.day, entry.time)
        
        # Check resource conflicts
        if entry.room:
            resource_key = f"room_{entry.room.name}"
            resource_usage[key].append(('room', resource_key, entry))
        if entry.lab:
            resource_key = f"lab_{entry.lab.name}"
            resource_usage[key].append(('lab', resource_key, entry))
        
        # Check faculty conflicts
        if entry.faculty:
            faculty_usage[key].append(('faculty', entry.faculty.short_name, entry))
        
        # Check batch conflicts
        if entry.batch:
            batch_usage[key].append(('batch', entry.batch.name, entry))
    
    # Find conflicts
    for key, usages in resource_usage.items():
        if len(usages) > 1:
            conflicts.append({
                'type': 'resource_conflict',
                'day': key[0],
                'time': key[1],
                'conflicting_entries': [{'type': t, 'resource': r, 'entry': e} for t, r, e in usages]
            })
    
    for key, usages in faculty_usage.items():
        if len(usages) > 1:
            conflicts.append({
                'type': 'faculty_conflict',
                'day': key[0],
                'time': key[1],
                'conflicting_entries': [{'type': t, 'faculty': f, 'entry': e} for t, f, e in usages]
            })
    
    for key, usages in batch_usage.items():
        if len(usages) > 1:
            conflicts.append({
                'type': 'batch_conflict',
                'day': key[0],
                'time': key[1],
                'conflicting_entries': [{'type': t, 'batch': b, 'entry': e} for t, b, e in usages]
            })
    
    return {
        'total_conflicts': len(conflicts),
        'conflicts': conflicts,
        'resource_conflicts': len([c for c in conflicts if c['type'] == 'resource_conflict']),
        'faculty_conflicts': len([c for c in conflicts if c['type'] == 'faculty_conflict']),
        'batch_conflicts': len([c for c in conflicts if c['type'] == 'batch_conflict'])
    }


def get_efficiency_metrics(entries, days_order, slots_order):
    """Calculate various efficiency metrics"""
    total_entries = len(entries)
    total_possible_slots = len(days_order) * len(slots_order)
    
    # Calculate utilization rates
    slot_occupancy = defaultdict(lambda: defaultdict(int))
    for entry in entries:
        if entry.day and entry.time:
            slot_occupancy[entry.day][entry.time] += 1
    
    occupied_slots = sum(1 for day in days_order for slot in slots_order if slot_occupancy[day][slot] > 0)
    utilization_rate = (occupied_slots / total_possible_slots) * 100 if total_possible_slots > 0 else 0
    
    # Calculate distribution metrics
    faculty_workloads = defaultdict(int)
    subject_distribution = defaultdict(int)
    room_usage = defaultdict(int)
    lab_usage = defaultdict(int)
    
    for entry in entries:
        if entry.faculty:
            faculty_workloads[entry.faculty.short_name] += 1
        if entry.subject:
            subject_distribution[entry.subject.subject_name] += 1
        if entry.room:
            room_usage[entry.room.name] += 1
        if entry.lab:
            lab_usage[entry.lab.name] += 1
    
    # Calculate workload balance
    faculty_workloads_list = list(faculty_workloads.values())
    workload_variance = 0
    if faculty_workloads_list:
        mean_workload = sum(faculty_workloads_list) / len(faculty_workloads_list)
        workload_variance = sum((w - mean_workload) ** 2 for w in faculty_workloads_list) / len(faculty_workloads_list)
    
    return {
        'total_entries': total_entries,
        'total_possible_slots': total_possible_slots,
        'occupied_slots': occupied_slots,
        'utilization_rate': utilization_rate,
        'faculty_count': len(faculty_workloads),
        'subject_count': len(subject_distribution),
        'room_count': len(room_usage),
        'lab_count': len(lab_usage),
        'workload_balance': 1 / (1 + workload_variance) if workload_variance > 0 else 1,  # Higher is better
        'avg_lectures_per_faculty': sum(faculty_workloads.values()) / len(faculty_workloads) if faculty_workloads else 0,
        'avg_lectures_per_subject': sum(subject_distribution.values()) / len(subject_distribution) if subject_distribution else 0
    }
import json
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.models import Department, Timetable, TimetableEntry, TimeSettings, Faculty

from xhtml2pdf import pisa
from django.template.loader import render_to_string
import io

@login_required
def analytics_report(request):
    """Enhanced Analytics Report with comprehensive faculty and timetable analytics"""
    user_college = request.user.department.college
    college = user_college.name

    departments_qs = Department.objects.filter(college=user_college).order_by("name")
    department_names = [d.name for d in departments_qs]

    selected_departments = request.GET.getlist("departments") or []
    selected_timetables = request.GET.getlist("timetables") or []
    selected_faculty = request.GET.get("faculty", "")

    timetables_for_departments = []
    faculties = []
    if selected_departments:
        timetables_qs = Timetable.objects.filter(department__name__in=selected_departments)
        timetables_for_departments = list(timetables_qs.values_list("name", flat=True).distinct())
        
        # Get all faculties from selected departments
        faculties = list(Faculty.objects.filter(
            department__name__in=selected_departments
        ).values_list("full_name", flat=True).distinct())

    # Analytics data
    analytics_data = {}
    error = None
    days_order = []
    slots_order = []

    if selected_departments and selected_timetables:
        entries = TimetableEntry.objects.filter(
            timetable__name__in=selected_timetables,
            timetable__department__name__in=selected_departments,
            timetable__department__college=user_college
        ).select_related("subject", "faculty", "timetable", "batch", "room", "lab")

        # Get time settings
        first_dept = Department.objects.filter(name=selected_departments[0]).first()
        time_settings = TimeSettings.objects.filter(department=first_dept).first()
        
        if time_settings:
            days_order = [d.name for d in time_settings.selected_days.all()]
            slots_order = [f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}" for s in time_settings.selected_slots.all()]
        else:
            days_order = sorted(set(e.day for e in entries))
            slots_order = sorted(set(e.time for e in entries))

        # Comprehensive analytics
        analytics_data = {
            'faculty_workload': get_faculty_workload_analytics(entries),
            'subject_distribution': get_subject_distribution_analytics(entries),
            'room_lab_utilization': get_room_lab_utilization_analytics(entries),
            'time_slot_occupancy': get_time_slot_occupancy_analytics(entries, days_order, slots_order),
            'faculty_availability_patterns': get_faculty_availability_patterns(entries, days_order, slots_order),
            'batch_workload': get_batch_workload_analytics(entries),
            'conflict_analysis': get_conflict_analysis(entries),
            'efficiency_metrics': get_efficiency_metrics(entries, days_order, slots_order),
            'faculty_subject_matrix': faculty_subject_matrix(entries, selected_departments),
            'total_lectures': faculty_total_lectures(entries),
            'slot_data': slot_occupancy(entries, days_order, slots_order),
        }

    context = {
        "college": college,
        "departments": department_names,
        "selected_departments": selected_departments,
        "timetables_for_departments": timetables_for_departments,
        "selected_timetables": selected_timetables,
        "faculties": faculties,
        "selected_faculty": selected_faculty,
        "analytics_data": analytics_data,
        "days": days_order,
        "slots": slots_order,
        "error": error,
    }

    return render(request, "reports/analytics_report.html", context)


@login_required
def analytics_report_download(request):
    """Download analytics report as PDF or Excel"""
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
    ).select_related("subject", "faculty", "timetable", "batch", "room", "lab")

    # Get time settings
    first_dept = Department.objects.filter(name=selected_departments[0]).first()
    time_settings = TimeSettings.objects.filter(department=first_dept).first()
    days_order = []
    slots_order = []
    
    if time_settings:
        days_order = [d.name for d in time_settings.selected_days.all()]
        slots_order = [f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}" for s in time_settings.selected_slots.all()]
    else:
        days_order = sorted(set(e.day for e in entries))
        slots_order = sorted(set(e.time for e in entries))

    # Get analytics data
    analytics_data = {
        'faculty_workload': get_faculty_workload_analytics(entries),
        'subject_distribution': get_subject_distribution_analytics(entries),
        'room_lab_utilization': get_room_lab_utilization_analytics(entries),
        'time_slot_occupancy': get_time_slot_occupancy_analytics(entries, days_order, slots_order),
        'faculty_availability_patterns': get_faculty_availability_patterns(entries, days_order, slots_order),
        'batch_workload': get_batch_workload_analytics(entries),
        'conflict_analysis': get_conflict_analysis(entries),
        'efficiency_metrics': get_efficiency_metrics(entries, days_order, slots_order),
    }

    if file_format == "pdf":
        context = {
            "college": user_college.name,
            "selected_departments": ", ".join(selected_departments),
            "selected_timetables": ", ".join(selected_timetables),
            "analytics_data": analytics_data,
            "days": days_order,
            "slots": slots_order,
        }
        html = render_to_string("reports/analytics_report_pdf.html", context)
        result = io.BytesIO()
        pdf_status = pisa.CreatePDF(io.StringIO(html), dest=result)
        if pdf_status.err:
            return HttpResponse("Error generating PDF", status=500)

        result.seek(0)
        filename = f"Analytics_Report_{'_'.join(selected_departments)}.pdf"
        response = HttpResponse(result, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    elif file_format == "excel":
        output = io.BytesIO()

        # Create multiple sheets for different analytics
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Faculty Workload Sheet
            faculty_data = []
            for faculty, stats in analytics_data['faculty_workload'].items():
                faculty_data.append({
                    'Faculty': faculty,
                    'Total Lectures': stats['total_lectures'],
                    'Subject Count': stats['subject_count'],
                    'Batch Count': stats['batch_count'],
                    'Day Count': stats['day_count'],
                    'Room Count': stats['room_count'],
                    'Lab Count': stats['lab_count'],
                    'Avg Lectures per Day': round(stats['avg_lectures_per_day'], 2)
                })
            df_faculty = pd.DataFrame(faculty_data)
            df_faculty.to_excel(writer, index=False, sheet_name="Faculty Workload")

            # Subject Distribution Sheet
            subject_data = []
            for subject, stats in analytics_data['subject_distribution'].items():
                subject_data.append({
                    'Subject': subject,
                    'Total Lectures': stats['total_lectures'],
                    'Faculty Count': stats['faculty_count'],
                    'Batch Count': stats['batch_count'],
                    'Room Count': stats['room_count'],
                    'Lab Count': stats['lab_count']
                })
            df_subject = pd.DataFrame(subject_data)
            df_subject.to_excel(writer, index=False, sheet_name="Subject Distribution")

            # Room Utilization Sheet
            room_data = []
            for room, stats in analytics_data['room_lab_utilization']['rooms'].items():
                room_data.append({
                    'Room': room,
                    'Total Usage': stats['total_usage'],
                    'Subject Count': stats['subject_count'],
                    'Faculty Count': stats['faculty_count'],
                    'Batch Count': stats['batch_count'],
                    'Day Count': stats['day_count'],
                    'Utilization Rate': round(stats['utilization_rate'], 2)
                })
            df_room = pd.DataFrame(room_data)
            df_room.to_excel(writer, index=False, sheet_name="Room Utilization")

            # Lab Utilization Sheet
            lab_data = []
            for lab, stats in analytics_data['room_lab_utilization']['labs'].items():
                lab_data.append({
                    'Lab': lab,
                    'Total Usage': stats['total_usage'],
                    'Subject Count': stats['subject_count'],
                    'Faculty Count': stats['faculty_count'],
                    'Batch Count': stats['batch_count'],
                    'Day Count': stats['day_count'],
                    'Utilization Rate': round(stats['utilization_rate'], 2)
                })
            df_lab = pd.DataFrame(lab_data)
            df_lab.to_excel(writer, index=False, sheet_name="Lab Utilization")

            # Batch Workload Sheet
            batch_data = []
            for batch, stats in analytics_data['batch_workload'].items():
                batch_data.append({
                    'Batch': batch,
                    'Total Lectures': stats['total_lectures'],
                    'Subject Count': stats['subject_count'],
                    'Faculty Count': stats['faculty_count'],
                    'Room Count': stats['room_count'],
                    'Lab Count': stats['lab_count'],
                    'Day Count': stats['day_count'],
                    'Avg Lectures per Day': round(stats['avg_lectures_per_day'], 2)
                })
            df_batch = pd.DataFrame(batch_data)
            df_batch.to_excel(writer, index=False, sheet_name="Batch Workload")

            # Efficiency Metrics Sheet
            efficiency = analytics_data['efficiency_metrics']
            efficiency_data = [{
                'Metric': 'Total Entries',
                'Value': efficiency['total_entries']
            }, {
                'Metric': 'Total Possible Slots',
                'Value': efficiency['total_possible_slots']
            }, {
                'Metric': 'Occupied Slots',
                'Value': efficiency['occupied_slots']
            }, {
                'Metric': 'Utilization Rate (%)',
                'Value': round(efficiency['utilization_rate'], 2)
            }, {
                'Metric': 'Faculty Count',
                'Value': efficiency['faculty_count']
            }, {
                'Metric': 'Subject Count',
                'Value': efficiency['subject_count']
            }, {
                'Metric': 'Room Count',
                'Value': efficiency['room_count']
            }, {
                'Metric': 'Lab Count',
                'Value': efficiency['lab_count']
            }, {
                'Metric': 'Workload Balance',
                'Value': round(efficiency['workload_balance'], 2)
            }, {
                'Metric': 'Avg Lectures per Faculty',
                'Value': round(efficiency['avg_lectures_per_faculty'], 2)
            }, {
                'Metric': 'Avg Lectures per Subject',
                'Value': round(efficiency['avg_lectures_per_subject'], 2)
            }]
            df_efficiency = pd.DataFrame(efficiency_data)
            df_efficiency.to_excel(writer, index=False, sheet_name="Efficiency Metrics")

            # Conflict Analysis Sheet
            conflicts = analytics_data['conflict_analysis']
            conflict_data = [{
                'Conflict Type': 'Total Conflicts',
                'Count': conflicts['total_conflicts']
            }, {
                'Conflict Type': 'Resource Conflicts',
                'Count': conflicts['resource_conflicts']
            }, {
                'Conflict Type': 'Faculty Conflicts',
                'Count': conflicts['faculty_conflicts']
            }, {
                'Conflict Type': 'Batch Conflicts',
                'Count': conflicts['batch_conflicts']
            }]
            df_conflicts = pd.DataFrame(conflict_data)
            df_conflicts.to_excel(writer, index=False, sheet_name="Conflict Analysis")

        output.seek(0)
        filename = f"Analytics_Report_{'_'.join(selected_departments)}.xlsx"
        response = HttpResponse(
            output,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    else:
        return HttpResponse("Unsupported format. Use pdf or excel.", status=400)


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

    # Prepare chart data for faculty total lectures
    total_lectures_keys = []
    total_lectures_values = []
    if total_lectures:
        total_lectures_keys = list(total_lectures.keys())
        total_lectures_values = list(total_lectures.values())

    context = {
        "college": college,
        "departments": department_names,
        "selected_departments": selected_departments,
        "timetables_for_departments": timetables_for_departments,
        "selected_timetables": selected_timetables,
        "matrix": matrix,
        "total_lectures": total_lectures,
        "total_lectures_keys": json.dumps(total_lectures_keys),  # JSON string for JS
        "total_lectures_values": json.dumps(total_lectures_values),  # JSON string for JS
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
