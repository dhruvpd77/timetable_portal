from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
import json
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import io
from .excel_leave_forms import ExcelTimetableUploadForm, FacultyDaySelectionForm, LeaveReassignmentForm
from .utils.excel_parser import parse_timetable_excel, find_available_faculty_for_lecture, find_available_rooms_labs_for_lecture, get_faculty_lectures_for_day

def excel_leave_management_view(request):
    """Main view for Excel-based leave management"""
    if request.method == 'POST':
        form = ExcelTimetableUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # Parse the Excel file
                parsed_data = parse_timetable_excel(request.FILES['excel_file'])
                
                # Store parsed data in session
                request.session['excel_timetable_data'] = parsed_data
                
                messages.success(request, 'Excel file uploaded and parsed successfully!')
                return redirect('excel_faculty_day_selection')
                
            except Exception as e:
                messages.error(request, f'Error processing Excel file: {str(e)}')
    else:
        form = ExcelTimetableUploadForm()
    
    return render(request, 'core/excel_leave_management.html', {'form': form})

def excel_faculty_day_selection_view(request):
    """View for selecting faculty and day from parsed Excel data"""
    # Get parsed data from session
    parsed_data = request.session.get('excel_timetable_data')
    if not parsed_data:
        messages.error(request, 'No timetable data found. Please upload an Excel file first.')
        return redirect('excel_leave_management')
    
    # Prepare faculty choices
    faculty_choices = [(faculty, faculty) for faculty in parsed_data['faculty_list']]
    
    if request.method == 'POST':
        form = FacultyDaySelectionForm(faculty_choices, request.POST)
        if form.is_valid():
            faculty = form.cleaned_data['faculty']
            day = form.cleaned_data['day']
            
            # Store selection in session
            request.session['selected_faculty'] = faculty
            request.session['selected_day'] = day
            
            return redirect('excel_leave_details')
    else:
        form = FacultyDaySelectionForm(faculty_choices)
    
    context = {
        'form': form,
        'faculty_count': len(parsed_data['faculty_list']),
        'days_count': len(parsed_data['days_list']),
        'batches_count': len(parsed_data['batches_list']),
        'faculty_list': parsed_data['faculty_list'][:10],  # Show first 10
        'days_list': parsed_data['days_list']
    }
    
    return render(request, 'core/excel_faculty_day_selection.html', context)

def excel_leave_details_view(request):
    """View for showing leave details and reassignment options"""
    # Get data from session
    parsed_data = request.session.get('excel_timetable_data')
    selected_faculty = request.session.get('selected_faculty')
    selected_day = request.session.get('selected_day')
    
    if not all([parsed_data, selected_faculty, selected_day]):
        messages.error(request, 'Missing data. Please start from the beginning.')
        return redirect('excel_leave_management')
    
    # Get faculty lectures for the selected day
    faculty_lectures = get_faculty_lectures_for_day(
        parsed_data['timetable_data'], 
        selected_faculty, 
        selected_day
    )
    
    # Add available faculty and rooms/labs for each lecture
    for lecture in faculty_lectures:
        available_faculty = find_available_faculty_for_lecture(
            parsed_data['timetable_data'],
            selected_day,
            lecture['batch'],
            lecture['time_slot'],
            lecture['subject'],
            selected_faculty
        )
        lecture['available_faculty'] = available_faculty
        
        available_rooms_labs = find_available_rooms_labs_for_lecture(
            parsed_data['timetable_data'],
            selected_day,
            lecture['time_slot']
        )
        lecture['available_rooms_labs'] = available_rooms_labs
    
    if request.method == 'POST':
        # Handle reassignment submissions
        reassignments = {}
        room_lab_assignments = {}
        for key, value in request.POST.items():
            if key.startswith('replacement_'):
                lecture_id = key.replace('replacement_', '')
                if value and value != 'none':
                    reassignments[lecture_id] = value
            elif key.startswith('room_lab_'):
                lecture_id = key.replace('room_lab_', '')
                if value and value != 'none':
                    room_lab_assignments[lecture_id] = value
        
        if reassignments:
            # Store reassignments and room/lab assignments in session
            request.session['reassignments'] = reassignments
            request.session['room_lab_assignments'] = room_lab_assignments
            # Generate temporary timetable
            return redirect('excel_generate_temporary_timetable')
        else:
            messages.warning(request, 'Please select replacement faculty for at least one lecture.')
    
    context = {
        'selected_faculty': selected_faculty,
        'selected_day': selected_day,
        'faculty_lectures': faculty_lectures,
        'total_lectures': len(faculty_lectures)
    }
    
    return render(request, 'core/excel_leave_details.html', context)

def excel_generate_temporary_timetable_view(request):
    """Generate and display temporary timetable with reassignments"""
    # Get data from session
    parsed_data = request.session.get('excel_timetable_data')
    selected_faculty = request.session.get('selected_faculty')
    selected_day = request.session.get('selected_day')
    
    if not all([parsed_data, selected_faculty, selected_day]):
        messages.error(request, 'Missing data. Please start from the beginning.')
        return redirect('excel_leave_management')
    
    # Get reassignments and room/lab assignments from session
    reassignments = request.session.get('reassignments', {})
    room_lab_assignments = request.session.get('room_lab_assignments', {})
    
    # Debug: Print reassignments to console
    print(f"DEBUG: Reassignments from session: {reassignments}")
    print(f"DEBUG: Room/Lab assignments from session: {room_lab_assignments}")
    print(f"DEBUG: Selected faculty: {selected_faculty}")
    print(f"DEBUG: Selected day: {selected_day}")
    
    # Create temporary timetable data - only for the selected day and affected batches
    temporary_timetable = {}
    original_timetable = parsed_data['timetable_data']
    
    # Get affected batches (batches that have reassignments)
    affected_batches = set()
    for key in reassignments.keys():
        batch = key.split('_')[0]  # Extract batch from key like "C7_09:45-10:45"
        affected_batches.add(batch)
    
    # Only process the selected day and affected batches
    if selected_day in original_timetable:
        temporary_timetable[selected_day] = {}
        
        for batch in affected_batches:
            if batch in original_timetable[selected_day]:
                temporary_timetable[selected_day][batch] = []
                
                for lecture in original_timetable[selected_day][batch]:
                    # Create a copy of the lecture
                    temp_lecture = lecture.copy()
                    
                    # Check if this lecture is being reassigned
                    lecture_key = f"{lecture['batch']}_{lecture['time_slot']}"
                    if lecture_key in reassignments:
                        replacement_faculty = reassignments[lecture_key]
                        
                        # Find the replacement faculty's subject for this time slot
                        replacement_subject = None
                        for day, batches in original_timetable.items():
                            for b, lectures in batches.items():
                                for l in lectures:
                                    if (l['faculty'] == replacement_faculty and 
                                        l['time_slot'] == lecture['time_slot'] and
                                        l['day'] == selected_day):
                                        replacement_subject = l['subject']
                                        break
                                if replacement_subject:
                                    break
                            if replacement_subject:
                                break
                        
                        # Apply reassignment
                        temp_lecture['faculty'] = replacement_faculty
                        temp_lecture['subject'] = replacement_subject or lecture['subject']  # Use replacement's subject or keep original
                        temp_lecture['is_reassigned'] = True
                        temp_lecture['original_faculty'] = selected_faculty
                        temp_lecture['original_subject'] = lecture['subject']
                        
                        # Apply room/lab assignment if selected
                        if lecture_key in room_lab_assignments:
                            temp_lecture['room_lab'] = room_lab_assignments[lecture_key]
                            temp_lecture['original_room_lab'] = lecture['room_lab']
                    else:
                        temp_lecture['is_reassigned'] = False
                    
                    temporary_timetable[selected_day][batch].append(temp_lecture)
    
    # Format reassignments for better display
    formatted_reassignments = {}
    for key, replacement in reassignments.items():
        # Replace underscores with spaces for better display
        formatted_key = key.replace('_', ' ')
        formatted_reassignments[formatted_key] = replacement
    
    context = {
        'selected_faculty': selected_faculty,
        'selected_day': selected_day,
        'temporary_timetable': temporary_timetable,
        'reassignments': formatted_reassignments,
        'time_slots': parsed_data['time_slots']
    }
    
    return render(request, 'core/excel_temporary_timetable.html', context)

def clear_excel_session_view(request):
    """Clear Excel data from session"""
    keys_to_clear = [
        'excel_timetable_data',
        'selected_faculty', 
        'selected_day',
        'reassignments',
        'room_lab_assignments'
    ]
    
    for key in keys_to_clear:
        if key in request.session:
            del request.session[key]
    
    messages.info(request, 'Session data cleared. You can upload a new Excel file.')
    return redirect('excel_leave_management')

def download_temporary_timetable_pdf(request):
    """Download temporary timetable as PDF"""
    # Get data from session
    parsed_data = request.session.get('excel_timetable_data')
    selected_faculty = request.session.get('selected_faculty')
    selected_day = request.session.get('selected_day')
    reassignments = request.session.get('reassignments', {})
    room_lab_assignments = request.session.get('room_lab_assignments', {})
    
    if not all([parsed_data, selected_faculty, selected_day]):
        messages.error(request, 'Missing data. Please start from the beginning.')
        return redirect('excel_leave_management')
    
    # Create temporary timetable data - only for the selected day and affected batches
    temporary_timetable = {}
    original_timetable = parsed_data['timetable_data']
    
    # Get affected batches (batches that have reassignments)
    affected_batches = set()
    for key in reassignments.keys():
        batch = key.split('_')[0]  # Extract batch from key like "C7_09:45-10:45"
        affected_batches.add(batch)
    
    # Only process the selected day and affected batches
    if selected_day in original_timetable:
        temporary_timetable[selected_day] = {}
        
        for batch in affected_batches:
            if batch in original_timetable[selected_day]:
                temporary_timetable[selected_day][batch] = []
                
                for lecture in original_timetable[selected_day][batch]:
                    # Create a copy of the lecture
                    temp_lecture = lecture.copy()
                    
                    # Check if this lecture is being reassigned
                    lecture_key = f"{lecture['batch']}_{lecture['time_slot']}"
                    if lecture_key in reassignments:
                        replacement_faculty = reassignments[lecture_key]
                        
                        # Find the replacement faculty's subject for this time slot
                        replacement_subject = None
                        for day, batches in original_timetable.items():
                            for b, lectures in batches.items():
                                for l in lectures:
                                    if (l['faculty'] == replacement_faculty and 
                                        l['time_slot'] == lecture['time_slot'] and
                                        l['day'] == selected_day):
                                        replacement_subject = l['subject']
                                        break
                                if replacement_subject:
                                    break
                            if replacement_subject:
                                break
                        
                        # Apply reassignment
                        temp_lecture['faculty'] = replacement_faculty
                        temp_lecture['subject'] = replacement_subject or lecture['subject']
                        temp_lecture['is_reassigned'] = True
                        temp_lecture['original_faculty'] = selected_faculty
                        temp_lecture['original_subject'] = lecture['subject']
                        
                        # Apply room/lab assignment if selected
                        if lecture_key in room_lab_assignments:
                            temp_lecture['room_lab'] = room_lab_assignments[lecture_key]
                            temp_lecture['original_room_lab'] = lecture['room_lab']
                    else:
                        temp_lecture['is_reassigned'] = False
                    
                    temporary_timetable[selected_day][batch].append(temp_lecture)
    
    # Create PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch, bottomMargin=1*inch)
    story = []
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1,  # Center alignment
        textColor=colors.darkblue
    )
    
    # Title
    title = Paragraph(f"Temporary Timetable - {selected_day}", title_style)
    story.append(title)
    
    # Leave Information
    leave_info = Paragraph(
        f"<b>Faculty on Leave:</b> {selected_faculty}<br/>"
        f"<b>Leave Day:</b> {selected_day}<br/>"
        f"<b>Reassignments Made:</b> {len(reassignments)}",
        styles['Normal']
    )
    story.append(leave_info)
    story.append(Spacer(1, 20))
    
    # Create table data
    time_slots = parsed_data['time_slots']
    table_data = []
    
    # Header row
    header = ['Day / Batch'] + time_slots
    table_data.append(header)
    
    # Data rows
    for day, batches in temporary_timetable.items():
        for batch, lectures in batches.items():
            row = [f"{day} / {batch}"]
            
            for time_slot in time_slots:
                cell_content = ""
                for lecture in lectures:
                    if lecture['time_slot'] == time_slot:
                        if lecture['is_reassigned']:
                            cell_content = f"{lecture['subject']}\n{lecture['faculty']}\n{lecture['room_lab']}\n(CHANGED)"
                        else:
                            cell_content = f"{lecture['subject']}\n{lecture['faculty']}\n{lecture['room_lab']}"
                        break
                
                row.append(cell_content)
            
            table_data.append(row)
    
    # Create table
    table = Table(table_data, colWidths=[1.5*inch] + [1.2*inch] * len(time_slots))
    
    # Table style
    table_style = TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        
        # Data rows
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        
        # Highlight changed cells
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
    ])
    
    # Apply special styling for changed cells
    for i, row in enumerate(table_data[1:], 1):  # Skip header row
        for j, cell in enumerate(row[1:], 1):  # Skip first column
            if cell and "(CHANGED)" in cell:
                table_style.add('BACKGROUND', (j, i), (j, i), colors.lightcoral)
                table_style.add('FONTNAME', (j, i), (j, i), 'Helvetica-Bold')
    
    table.setStyle(table_style)
    story.append(table)
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    
    # Create response
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="temporary_timetable_{selected_day}_{selected_faculty}.pdf"'
    
    return response
