import pandas as pd
import re
from collections import defaultdict

def parse_timetable_excel(excel_file):
    """
    Parse Excel timetable file and extract structured data
    Expected format: Day/Batch in column A, time slots in columns B onwards
    Each cell contains: Subject, Faculty, Room/Lab (3 lines)
    """
    try:
        # Read Excel file
        if excel_file.name.endswith('.xlsx'):
            df = pd.read_excel(excel_file, engine='openpyxl', header=None)
        else:
            df = pd.read_excel(excel_file, engine='xlrd', header=None)
        
        # Initialize data structures
        timetable_data = defaultdict(lambda: defaultdict(list))
        faculty_list = set()
        days_list = set()
        batches_list = set()
        
        # Get time slots from header row (row 0, columns B onwards)
        time_slots = []
        for col in range(1, len(df.columns)):
            cell_value = str(df.iloc[0, col]).strip()
            if cell_value and cell_value != 'nan' and ':' in cell_value:
                time_slots.append(cell_value)
        
        # Parse data rows (starting from row 1)
        for row_idx in range(1, len(df)):
            day_batch_cell = str(df.iloc[row_idx, 0]).strip()
            
            if not day_batch_cell or day_batch_cell == 'nan':
                continue
                
            # Parse day and batch from first column
            day_batch_match = re.match(r'(\w+)\s*/\s*(\w+)', day_batch_cell)
            if not day_batch_match:
                continue
                
            day = day_batch_match.group(1).strip()
            batch = day_batch_match.group(2).strip()
            
            days_list.add(day)
            batches_list.add(batch)
            
            # Parse each time slot for this day/batch
            for col_idx, time_slot in enumerate(time_slots):
                if col_idx + 1 >= len(df.columns):
                    break
                    
                cell_value = str(df.iloc[row_idx, col_idx + 1]).strip()
                
                if not cell_value or cell_value == 'nan':
                    continue
                
                # Parse the cell content (Subject, Faculty, Room/Lab)
                lines = [line.strip() for line in cell_value.split('\n') if line.strip()]
                
                if len(lines) >= 3:
                    subject = lines[0]
                    faculty = lines[1]
                    room_lab = lines[2]
                    
                    # Add faculty to the list
                    if faculty and faculty != 'nan':
                        faculty_list.add(faculty)
                    
                    # Store the lecture data
                    lecture_data = {
                        'subject': subject,
                        'faculty': faculty,
                        'room_lab': room_lab,
                        'time_slot': time_slot,
                        'day': day,
                        'batch': batch
                    }
                    
                    timetable_data[day][batch].append(lecture_data)
        
        return {
            'timetable_data': dict(timetable_data),
            'faculty_list': sorted(list(faculty_list)),
            'days_list': sorted(list(days_list)),
            'batches_list': sorted(list(batches_list)),
            'time_slots': time_slots
        }
        
    except Exception as e:
        raise Exception(f"Error parsing Excel file: {str(e)}")

def find_available_faculty_for_lecture(timetable_data, target_day, target_batch, target_time_slot, target_subject, exclude_faculty):
    """
    Find faculty who are teaching in the target batch and are free at the given time slot
    (regardless of which subject they normally teach)
    """
    available_faculty = []
    
    # Get all faculty who teach in the target batch (regardless of subject or day)
    batch_faculty = set()
    for day, batches in timetable_data.items():
        if target_batch in batches:
            for lecture in batches[target_batch]:
                if lecture['faculty']:
                    batch_faculty.add(lecture['faculty'])
    
    # Check which faculty are free at the target time slot
    for faculty in batch_faculty:
        if faculty == exclude_faculty:
            continue
            
        # Check if this faculty is free at the target time slot
        is_free = True
        for day, batches in timetable_data.items():
            for batch, lectures in batches.items():
                for lecture in lectures:
                    if (lecture['faculty'] == faculty and 
                        lecture['time_slot'] == target_time_slot and
                        lecture['day'] == target_day):
                        is_free = False
                        break
                if not is_free:
                    break
            if not is_free:
                break
        
        if is_free:
            available_faculty.append(faculty)
    
    return sorted(available_faculty)

def find_available_rooms_labs_for_lecture(timetable_data, target_day, target_time_slot):
    """
    Find rooms and labs that are available at the given time slot
    """
    available_rooms_labs = []
    
    # Get all rooms/labs from the timetable
    all_rooms_labs = set()
    for day, batches in timetable_data.items():
        for batch, lectures in batches.items():
            for lecture in lectures:
                if lecture['room_lab']:
                    all_rooms_labs.add(lecture['room_lab'])
    
    # Check which rooms/labs are free at the target time slot
    for room_lab in all_rooms_labs:
        is_free = True
        for day, batches in timetable_data.items():
            for batch, lectures in batches.items():
                for lecture in lectures:
                    if (lecture['room_lab'] == room_lab and 
                        lecture['time_slot'] == target_time_slot and
                        lecture['day'] == target_day):
                        is_free = False
                        break
                if not is_free:
                    break
            if not is_free:
                break
        
        if is_free:
            available_rooms_labs.append(room_lab)
    
    return sorted(available_rooms_labs)

def get_faculty_lectures_for_day(timetable_data, faculty, day):
    """
    Get all lectures for a specific faculty on a specific day
    """
    lectures = []
    
    if day in timetable_data:
        for batch, batch_lectures in timetable_data[day].items():
            for lecture in batch_lectures:
                if lecture['faculty'] == faculty:
                    lectures.append(lecture)
    
    # Sort by time slot
    lectures.sort(key=lambda x: x['time_slot'])
    return lectures
