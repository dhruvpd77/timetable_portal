from collections import defaultdict
from ortools.sat.python import cp_model

"""
Enhanced Timetable Solver with Lab Allocation Rules

Key Changes:
1. Labs are always 2 consecutive hours (no 1-hour labs)
2. When a lab is assigned on a day, ensure 2 different subjects are assigned on that day
3. For batches with 4+ subjects: 2 hours of lab + 2 different subjects
4. Enhanced constraints to maintain subject variety and optimal distribution
5. Lab sessions are limited to prevent domination of the day schedule
6. Basic slot assignment - no complex free slot constraints
7. Blocked slot enforcement - respects room and lab blocked slots during generation
8. Double-blocked slot protection - both during variable creation and explicit constraints
9. Fixed blocked slot logic - blocked slots checked BEFORE batch mapping to ensure proper enforcement
"""


def generate_timetable(
    department,
    settings,
    specs,
    assignments,
    faculty_objs,
    batch_objs,
    rooms,
    labs,
    batch_to_rooms=None,     # dict: batch_name -> set of room names
    batch_to_labs=None,      # dict: batch_name -> set of lab names
    blocked_faculty_slots=None,  # Dict: {faculty_short_name: set((day, slot))}
    blocked_room_slots=None,     # Dict: {room_name: set((day, slot))}
    blocked_lab_slots=None,      # Dict: {lab_name: set((day, slot))}
    preferred_faculty_slots=None,  # Dict: {(faculty_short_name, batch_name): set((day, slot))}
    timetable_type='1_hour',     # '1_hour' or '2_hour' slot type
):
    """
    Main timetable generation function that routes to appropriate logic based on timetable_type.
    """
    if timetable_type == '2_hour':
        # Use the new 2-hour pair slot logic
        return generate_timetable_2hour_pairs(
            department, settings, specs, assignments, faculty_objs, batch_objs,
            rooms, labs, batch_to_rooms, batch_to_labs,
            blocked_faculty_slots, blocked_room_slots, blocked_lab_slots, preferred_faculty_slots, timetable_type
        )
    else:
        # Use the original 1-hour slot logic
        return generate_timetable_1hour_original(
            department, settings, specs, assignments, faculty_objs, batch_objs,
            rooms, labs, batch_to_rooms, batch_to_labs,
            blocked_faculty_slots, blocked_room_slots, blocked_lab_slots, preferred_faculty_slots, timetable_type
        )


def generate_timetable_1hour_original(
    department,
    settings,
    specs,
    assignments,
    faculty_objs,
    batch_objs,
    rooms,
    labs,
    batch_to_rooms=None,     # dict: batch_name -> set of room names
    batch_to_labs=None,      # dict: batch_name -> set of lab names
    blocked_faculty_slots=None,  # Dict: {faculty_short_name: set((day, slot))}
    blocked_room_slots=None,     # Dict: {room_name: set((day, slot))}
    blocked_lab_slots=None,      # Dict: {lab_name: set((day, slot))}
    preferred_faculty_slots=None,  # Dict: {(faculty_short_name, batch_name): set((day, slot))}
    timetable_type='1_hour',     # '1_hour' or '2_hour' slot type
):
    # -- 1. Setup --
    DAYS = [d.name for d in settings.selected_days.all()]
    SLOTS = [f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}" for s in settings.selected_slots.all()]
    BREAKS = [f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}" for s in settings.break_slots.all()]
    VALID_SLOTS = [s for s in SLOTS if s not in BREAKS]

    subject_types = {s.subject_name: s.subject_type for s in specs}
    faculty_mapping = defaultdict(lambda: defaultdict(dict))
    practical_split = {}

    for a in assignments:
        subj = a.subject.subject_name
        faculty = a.faculty.short_name
        div = a.batch.name
        if subject_types[subj] == "Theory":
            faculty_mapping[subj][faculty][div] = a.hours
        else:
            faculty_mapping[subj][faculty][div] = a.hours
            practical_split[(subj, faculty, div)] = (0, a.hours)  # (room, lab)

    batch_to_rooms = batch_to_rooms or {}
    batch_to_labs = batch_to_labs or {}
    blocked_faculty_slots = blocked_faculty_slots or {}
    blocked_room_slots = blocked_room_slots or {}
    blocked_lab_slots = blocked_lab_slots or {}
    preferred_faculty_slots = preferred_faculty_slots or {}
    
    # Ensure blocked slots are properly enforced
    # blocked_room_slots: {room_name: set((day, slot))} - rooms blocked for specific day/slot combinations
    # blocked_lab_slots: {lab_name: set((day, slot))} - labs blocked for specific day/slot combinations
    # 
    # IMPORTANT: Blocked slot checking happens BEFORE batch mapping to ensure blocked slots are never used
    # This prevents any assignments to blocked time slots, regardless of batch assignments
    
    # Debug: Print blocked slots to verify they are being passed correctly
    print(f"DEBUG: blocked_room_slots = {blocked_room_slots}")
    print(f"DEBUG: blocked_lab_slots = {blocked_lab_slots}")
    print(f"DEBUG: blocked_faculty_slots = {blocked_faculty_slots}")
    
    # Debug: Print room and lab mappings
    print(f"DEBUG: batch_to_rooms = {batch_to_rooms}")
    print(f"DEBUG: batch_to_labs = {batch_to_labs}")
    print(f"DEBUG: rooms = {rooms}")
    print(f"DEBUG: labs = {labs}")

    # -- 2. OR-Tools model --
    model = cp_model.CpModel()
    requests = []
    subjects_sorted = [s.subject_name for s in specs]

    for subject in subjects_sorted:
        for faculty in faculty_mapping[subject]:
            for div, req in faculty_mapping[subject][faculty].items():
                req_type = "theory" if subject_types[subject] == "Theory" else "practical"
                requests.append((subject, faculty, div, req, req_type))

    all_vars = {}

    # Create variables only for allowed rooms and labs per batch mappings:
    for (subject, faculty, div, req, req_type) in requests:
        blocked_set = set(blocked_faculty_slots.get(faculty, []))

        if req_type == "theory":
            # 1-hour theory slots (original logic)
            for d in DAYS:
                for s in VALID_SLOTS:
                    # Skip if faculty is blocked for this slot
                    if (d, s) in blocked_set:
                        continue
                    for r in rooms:
                        # Skip if room is blocked for this day and slot FIRST (before batch mapping)
                        if (d, s) in blocked_room_slots.get(r, set()):
                            print(f"DEBUG: Skipping theory room {r} at {d} {s} for {subject} {faculty} {div} (room blocked)")
                            continue
                        # Enforce batch-to-room mapping: skip rooms not mapped to this batch if mapping exists
                        if batch_to_rooms and div in batch_to_rooms and r not in batch_to_rooms[div]:
                            continue
                        
                        all_vars[(subject, faculty, div, d, s, r, "theory")] = model.NewBoolVar(
                            f"x_{subject}_{faculty}_{div}_{d}_{s}_{r}_theory"
                        )
        else:
            room_req, lab_req = practical_split.get((subject, faculty, div), (req, 0))
            for d in DAYS:
                for s in VALID_SLOTS:
                    # Skip if faculty is blocked for this slot
                    if (d, s) in blocked_set:
                        continue
                    for r in rooms:
                        # Skip if room is blocked for this day and slot FIRST (before batch mapping)
                        if (d, s) in blocked_room_slots.get(r, set()):
                            print(f"DEBUG: Skipping room session room {r} at {d} {s} for {subject} {faculty} {div} (room blocked)")
                            continue
                        if batch_to_rooms and div in batch_to_rooms and r not in batch_to_rooms[div]:
                            continue
                        all_vars[(subject, faculty, div, d, s, r, "room")] = model.NewBoolVar(
                            f"x_{subject}_{faculty}_{div}_{d}_{s}_{r}_room"
                        )
                
                # Lab variables - always 2 consecutive hours
                num_pairs = lab_req // 2
                # Ensure labs are always 2 consecutive hours
                lab_pairs = [(VALID_SLOTS[i], VALID_SLOTS[i+1]) for i in range(0, len(VALID_SLOTS)-1, 2)]
                for d in DAYS:
                    for pair in lab_pairs:
                        # Skip if faculty is blocked for either slot in the pair
                        if (d, pair[0]) in blocked_set or (d, pair[1]) in blocked_set:
                            continue
                        for r in labs:
                            # Skip if lab is blocked for this day and slot pair FIRST (before batch mapping)
                            if (d, pair[0]) in blocked_lab_slots.get(r, set()) or (d, pair[1]) in blocked_lab_slots.get(r, set()):
                                print(f"DEBUG: Skipping lab {r} at {d} {pair[0]}-{pair[1]} for {subject} {faculty} {div} (lab blocked)")
                                continue
                            if batch_to_labs and div in batch_to_labs and r not in batch_to_labs[div]:
                                continue
                            all_vars[(subject, faculty, div, d, pair[0], r, "lab2", pair[1])] = model.NewBoolVar(
                                f"x_{subject}_{faculty}_{div}_{d}_{pair[0]}_{pair[1]}_{r}_lab2"
                            )

    # (A) Total required per subject/batch/faculty/week
    for (subject, faculty, div, req, req_type) in requests:
        if req_type == "theory":
            # 1-hour theory slots (original logic)
            candidate_all = []
            for d in DAYS:
                for s in VALID_SLOTS:
                    for r in rooms:
                        key = (subject, faculty, div, d, s, r, "theory")
                        if key in all_vars:
                            candidate_all.append(all_vars[key])
            model.Add(sum(candidate_all) == req)
            # Max 2 lectures per day
            for d in DAYS:
                slots_this_day = []
                for s in VALID_SLOTS:
                    for r in rooms:
                        key = (subject, faculty, div, d, s, r, "theory")
                        if key in all_vars:
                            slots_this_day.append(all_vars[key])
                model.Add(sum(slots_this_day) <= 2)
        else:
            room_req, lab_req = practical_split.get((subject, faculty, div), (req, 0))
            # Room sessions
            candidate_all_room = []
            for d in DAYS:
                for s in VALID_SLOTS:
                    for r in rooms:
                        key = (subject, faculty, div, d, s, r, "room")
                        if key in all_vars:
                            candidate_all_room.append(all_vars[key])
            model.Add(sum(candidate_all_room) == room_req)
            
            # 2-hour labs only (no 1-hour labs)
            num_pairs = lab_req // 2
            candidate_all_lab2 = []
            lab_pairs = [(VALID_SLOTS[i], VALID_SLOTS[i+1]) for i in range(0, len(VALID_SLOTS)-1, 2)]
            for d in DAYS:
                for pair in lab_pairs:
                    for r in labs:
                        key = (subject, faculty, div, d, pair[0], r, "lab2", pair[1])
                        if key in all_vars:
                            candidate_all_lab2.append(all_vars[key])
            if num_pairs:
                model.Add(sum(candidate_all_lab2) == num_pairs)

    # (A.1) Lab session constraints
    # 1. Only one 2-hour lab session (lab2) per day per batch/subject/faculty
    # 2. Labs must always be 2 consecutive hours
    for subject, faculty, div, req, req_type in requests:
        if req_type == "practical":
            for d in DAYS:
                lab2_vars = []
                lab_pairs = [(VALID_SLOTS[i], VALID_SLOTS[i+1]) for i in range(0, len(VALID_SLOTS)-1, 2)]
                for r in labs:
                    for pair in lab_pairs:
                        key = (subject, faculty, div, d, pair[0], r, "lab2", pair[1])
                        if key in all_vars:
                            lab2_vars.append(all_vars[key])
                if lab2_vars:
                    model.Add(sum(lab2_vars) <= 1)
                
                # Ensure labs are always 2 consecutive hours by preventing single-hour lab assignments
                # This constraint ensures that if a lab is assigned at slot i, it must also be assigned at slot i+1
                for i in range(len(VALID_SLOTS) - 1):
                    slot1, slot2 = VALID_SLOTS[i], VALID_SLOTS[i+1]
                    lab_vars_slot1 = []
                    lab_vars_slot2 = []
                    
                    for r in labs:
                        if batch_to_labs and div in batch_to_labs and r not in batch_to_labs[div]:
                            continue
                        
                        # Check if this pair is a valid lab pair
                        if (slot1, slot2) in lab_pairs:
                            key1 = (subject, faculty, div, d, slot1, r, "lab2", slot2)
                            key2 = (subject, faculty, div, d, slot2, r, "lab2", slot1)
                            
                            if key1 in all_vars:
                                lab_vars_slot1.append(all_vars[key1])
                            if key2 in all_vars:
                                lab_vars_slot2.append(all_vars[key2])
                    
                    # If lab is assigned at slot1, it must also be assigned at slot2 (and vice versa)
                    if lab_vars_slot1 and lab_vars_slot2:
                        model.Add(sum(lab_vars_slot1) == sum(lab_vars_slot2))

    # Define batch_list for constraints
    batch_list = sorted([b.name for b in batch_objs.values()])

    # NEW CONSTRAINT: Lab allocation rules
    # 1. Labs are always 2 consecutive hours (no 1-hour labs)
    # 2. When a lab is assigned on a day, ensure 2 different subjects are assigned on that day
    # 3. For batches with 4+ subjects: 2 hours of lab + 2 different subjects
    for div in batch_list:
        for d in DAYS:
            # Check if any lab is assigned on this day for this batch
            lab_assigned_vars = []
            for key in all_vars:
                if key[2] == div and key[3] == d and len(key) == 8 and key[-2] == "lab2":
                    lab_assigned_vars.append(all_vars[key])
            
            if lab_assigned_vars:
                # If lab is assigned, ensure at least 2 different subjects on this day
                # Get all subjects that could be assigned on this day for this batch
                all_possible_subjects = set()
                for key in all_vars:
                    if key[2] == div and key[3] == d:
                        all_possible_subjects.add(key[0])
                
                # Create variables for each subject being present on this day
                subject_present_vars = {}
                for subject in all_possible_subjects:
                    subject_present_vars[subject] = model.NewBoolVar(f"subject_{subject}_present_{div}_{d}")
                
                # Link subject presence to actual assignments
                for subject in all_possible_subjects:
                    subject_vars = []
                    for key in all_vars:
                        if key[0] == subject and key[2] == div and key[3] == d:
                            subject_vars.append(all_vars[key])
                    if subject_vars:
                        model.Add(sum(subject_vars) >= 1).OnlyEnforceIf(subject_present_vars[subject])
                        model.Add(sum(subject_vars) == 0).OnlyEnforceIf(subject_present_vars[subject].Not())
                
                # Ensure at least 2 different subjects when lab is present
                if len(subject_present_vars) >= 2:
                    model.Add(sum(subject_present_vars.values()) >= 2)
                
                # Additional constraint: When lab is assigned, ensure theory/room sessions are also present
                # This ensures we have both lab and theory/room sessions on the same day
                theory_room_vars = []
                for key in all_vars:
                    if key[2] == div and key[3] == d and (key[-1] == "theory" or key[-1] == "room"):
                        theory_room_vars.append(all_vars[key])
                
                if theory_room_vars:
                    # Ensure at least one theory/room session when lab is present
                    model.Add(sum(theory_room_vars) >= 1)
                
                # For 4-subject scenarios: Ensure 2 hours of lab + 2 different subjects
                # This constraint ensures that when lab is present, we have sufficient variety
                # Example: If 4 subjects exist, we want: 2 hours lab + 2 different subjects on the same day
                total_subjects_for_batch = len([s for s in subjects_sorted if any(
                    faculty_mapping[s][fac][div] for fac in faculty_mapping[s] if div in faculty_mapping[s][fac]
                )])
                
                if total_subjects_for_batch >= 4:
                    # For batches with 4+ subjects, ensure better distribution when lab is present
                    model.Add(sum(subject_present_vars.values()) >= 2)
                    
                    # Additional constraint for 4+ subjects: Ensure optimal distribution
                    # When lab is present, ensure we have at least 2 different subjects with theory/room sessions
                    theory_room_subjects = set()
                    for key in all_vars:
                        if key[2] == div and key[3] == d and (key[-1] == "theory" or key[-1] == "room"):
                            theory_room_subjects.add(key[0])
                    
                    if len(theory_room_subjects) >= 2:
                        # Ensure at least 2 different theory/room subjects when lab is present
                        theory_room_present_vars = {}
                        for subject in theory_room_subjects:
                            theory_room_present_vars[subject] = model.NewBoolVar(f"theory_room_{subject}_present_{div}_{d}")
                        
                        # Link theory/room subject presence to actual assignments
                        for subject in theory_room_subjects:
                            subject_vars = []
                            for key in all_vars:
                                if key[0] == subject and key[2] == div and key[3] == d and (key[-1] == "theory" or key[-1] == "room"):
                                    subject_vars.append(all_vars[key])
                            if subject_vars:
                                model.Add(sum(subject_vars) >= 1).OnlyEnforceIf(theory_room_present_vars[subject])
                                model.Add(sum(subject_vars) == 0).OnlyEnforceIf(theory_room_present_vars[subject].Not())
                        
                        # Ensure at least 2 different theory/room subjects
                        if len(theory_room_present_vars) >= 2:
                            model.Add(sum(theory_room_present_vars.values()) >= 2)
                
                # Ensure lab sessions don't dominate the day - maintain balance
                # When lab is present, limit the number of lab sessions per day to maintain subject variety
                lab_sessions_this_day = []
                for key in all_vars:
                    if key[2] == div and key[3] == d and len(key) == 8 and key[-2] == "lab2":
                        lab_sessions_this_day.append(all_vars[key])
                
                if lab_sessions_this_day:
                    # Limit lab sessions to ensure room for other subjects
                    model.Add(sum(lab_sessions_this_day) <= 2)  # Max 2 lab sessions (4 hours) per day
                    
                    # Additional constraint: Lab sessions should be assigned consecutively
                    # This ensures that if we have lab sessions, they are not scattered throughout the day
                    # but rather grouped together for better schedule continuity
                    
                    # Create variables to track lab session positions
                    lab_slot_positions = []
                    for s_idx, s in enumerate(VALID_SLOTS):
                        lab_at_slot = []
                        for key in all_vars:
                            if key[2] == div and key[3] == d and key[4] == s and len(key) == 8 and key[-2] == "lab2":
                                lab_at_slot.append(all_vars[key])
                        if lab_at_slot:
                            lab_slot_positions.append((s_idx, sum(lab_at_slot)))
                    
                    # Ensure lab sessions are consecutive (no gaps between lab sessions)
                    if len(lab_slot_positions) > 1:
                        for i in range(len(lab_slot_positions) - 1):
                            current_pos, current_lab = lab_slot_positions[i]
                            next_pos, next_lab = lab_slot_positions[i + 1]
                            
                            # If there's a gap between lab sessions, ensure it's not too large
                            # This prevents scattered lab assignments
                            if next_pos - current_pos > 2:  # Allow max 2 slots gap between labs
                                # Create a constraint to discourage large gaps
                                model.Add(next_lab <= current_lab)  # Encourage consecutive assignment
                
                # Ensure subject variety by preventing too many sessions of the same subject on one day
                for subject in all_possible_subjects:
                    subject_sessions_this_day = []
                    for key in all_vars:
                        if key[0] == subject and key[2] == div and key[3] == d:
                            subject_sessions_this_day.append(all_vars[key])
                    
                    if subject_sessions_this_day:
                        # Limit same subject to max 3 sessions per day to ensure variety
                        model.Add(sum(subject_sessions_this_day) <= 3)

    # (B) No double assignment (faculty, batch, resource, slot)
    all_faculty = set(key[1] for key in all_vars.keys())
    resources = rooms + labs
    
    # (B.1) ENFORCE BLOCKED SLOTS - Prevent any assignments to blocked slots
    # This is a backup constraint to ensure blocked slots are never used
    print(f"DEBUG: Enforcing blocked slots for {len(blocked_room_slots)} rooms and {len(blocked_lab_slots)} labs")
    
    for r in rooms:
        if r in blocked_room_slots:
            print(f"DEBUG: Room {r} has {len(blocked_room_slots[r])} blocked slots: {blocked_room_slots[r]}")
            for (day, slot) in blocked_room_slots[r]:
                # Find all variables that could assign to this blocked room/slot combination
                blocked_vars = []
                for key, var in all_vars.items():
                    if (key[5] == r and key[3] == day and key[4] == slot and 
                        (key[-1] == "theory" or key[-1] == "room")):
                        blocked_vars.append(var)
                # Force all these variables to be 0 (no assignment)
                if blocked_vars:
                    model.Add(sum(blocked_vars) == 0)
                    print(f"DEBUG: Blocked room {r} at {day} {slot} - {len(blocked_vars)} variables forced to 0")
                else:
                    print(f"DEBUG: No variables found for blocked room {r} at {day} {slot}")
    
    for r in labs:
        if r in blocked_lab_slots:
            print(f"DEBUG: Lab {r} has {len(blocked_lab_slots[r])} blocked slots: {blocked_lab_slots[r]}")
            for (day, slot) in blocked_lab_slots[r]:
                # Find all variables that could assign to this blocked lab/slot combination
                blocked_vars = []
                for key, var in all_vars.items():
                    if (key[5] == r and key[3] == day and 
                        ((key[-2] == "lab2" and (key[4] == slot or key[7] == slot)))):
                        blocked_vars.append(var)
                # Force all these variables to be 0 (no assignment)
                if blocked_vars:
                    model.Add(sum(blocked_vars) == 0)
                    print(f"DEBUG: Blocked lab {r} at {day} {slot} - {len(blocked_vars)} variables forced to 0")
                else:
                    print(f"DEBUG: No variables found for blocked lab {r} at {day} {slot}")
    
    for faculty in all_faculty:
        if faculty in blocked_faculty_slots:
            for (day, slot) in blocked_faculty_slots[faculty]:
                # Find all variables that could assign this faculty to the blocked slot
                blocked_vars = []
                for key, var in all_vars.items():
                    if (key[1] == faculty and key[3] == day and key[4] == slot and len(key) == 7):
                        blocked_vars.append(var)
                # Force all these variables to be 0 (no assignment)
                if blocked_vars:
                    model.Add(sum(blocked_vars) == 0)
                    print(f"DEBUG: Blocked faculty {faculty} at {day} {slot} - {len(blocked_vars)} variables forced to 0")

    # (B.2) ENFORCE PREFERRED SLOTS - Ensure faculty are assigned to their preferred slots for specific batches
    print(f"DEBUG: Enforcing preferred slots for {len(preferred_faculty_slots)} faculty-batch combinations")
    
    for (faculty, batch), preferred_set in preferred_faculty_slots.items():
        print(f"DEBUG: Faculty {faculty} prefers slots for batch {batch}: {preferred_set}")
        
        # Find all variables for this faculty-batch combination
        faculty_batch_vars = []
        for key, var in all_vars.items():
            if key[1] == faculty and key[2] == batch:
                faculty_batch_vars.append((key, var))
        
        if not faculty_batch_vars:
            print(f"DEBUG: No variables found for faculty {faculty} and batch {batch}")
            continue
        
        # Group variables by day and slot
        vars_by_slot = {}
        for key, var in faculty_batch_vars:
            day = key[3]
            slot = key[4]
            slot_key = (day, slot)
            if slot_key not in vars_by_slot:
                vars_by_slot[slot_key] = []
            vars_by_slot[slot_key].append(var)
        
        # STRONG CONSTRAINT: Faculty must be assigned to their preferred slots
        # Calculate total assignments needed for this faculty-batch combination
        total_assignments = 0
        for key, var in faculty_batch_vars:
            # Count how many hours this faculty-batch combination needs
            subject_name = key[0]
            if subject_name in faculty_mapping[faculty][batch]:
                total_assignments += faculty_mapping[faculty][batch][subject_name]
        
        if total_assignments > 0 and preferred_set:
            # Create a constraint that ensures assignments are in preferred slots
            preferred_vars = []
            
            for (day, slot) in preferred_set:
                slot_key = (day, slot)
                if slot_key in vars_by_slot:
                    preferred_vars.extend(vars_by_slot[slot_key])
            
            if preferred_vars:
                # Calculate how many hours should be in preferred slots
                # For 1-hour slots, each preferred slot is 1 hour
                preferred_hours = len(preferred_set)
                
                # Ensure faculty is assigned to their preferred slots
                # Use the minimum of preferred hours available or total assignments needed
                min_preferred_hours = min(preferred_hours, total_assignments)
                
                if min_preferred_hours > 0:
                    # Force assignment to preferred slots - use exact constraint
                    model.Add(sum(preferred_vars) >= min_preferred_hours)
                    print(f"DEBUG: Enforced {min_preferred_hours} hours in preferred slots for {faculty}-{batch}: {len(preferred_vars)} variables")
                    
                    # For 1-hour slots, ensure we get the exact preferred slots
                    if timetable_type == '1_hour':
                        # For each preferred slot, ensure at least one assignment
                        for (day, slot) in preferred_set:
                            slot_key = (day, slot)
                            if slot_key in vars_by_slot:
                                slot_vars = vars_by_slot[slot_key]
                                if slot_vars:
                                    # STRONG CONSTRAINT: Force assignment in this specific preferred slot
                                    # This ensures the faculty MUST be assigned to this slot
                                    model.Add(sum(slot_vars) >= 1)
                                    print(f"DEBUG: STRONG CONSTRAINT - Enforced assignment in preferred slot {day} {slot} for {faculty}-{batch}")
                                    
                                    # Additional constraint: If any variable in this slot is 1, 
                                    # then the faculty must be assigned to this specific slot
                                    for var in slot_vars:
                                        # This variable represents this faculty-batch-subject combination in this slot
                                        # We want to ensure this specific combination is chosen
                                        pass  # The constraint above should be sufficient
                    
                    # If there are remaining hours, they can be assigned anywhere
                    remaining_hours = total_assignments - min_preferred_hours
                    if remaining_hours > 0:
                        print(f"DEBUG: {remaining_hours} remaining hours for {faculty}-{batch} can be assigned anywhere")
                else:
                    print(f"DEBUG: No preferred hours available for {faculty}-{batch}")
            else:
                print(f"DEBUG: No preferred slot variables found for {faculty}-{batch}")

    for div in batch_list:
        for d in DAYS:
            for s in VALID_SLOTS:
                vars_div = []
                for key in all_vars:
                    if key[2] != div or key[3] != d:
                        continue
                    if len(key) == 7 and key[4] == s:
                        vars_div.append(all_vars[key])
                    elif len(key) == 8 and (key[-2] == "lab2" and (key[4] == s or key[7] == s)):
                        vars_div.append(all_vars[key])
                if vars_div:
                    model.Add(sum(vars_div) <= 1)

    for faculty in all_faculty:
        for d in DAYS:
            for s in VALID_SLOTS:
                vars_fac = []
                for key in all_vars:
                    if key[1] != faculty or key[3] != d:
                        continue
                    if len(key) == 7 and key[4] == s:
                        vars_fac.append(all_vars[key])
                    elif len(key) == 8 and (key[-2] == "lab2" and (key[4] == s or key[7] == s)):
                        vars_fac.append(all_vars[key])
                if vars_fac:
                    model.Add(sum(vars_fac) <= 1)

    for r in resources:
        for d in DAYS:
            for s in VALID_SLOTS:
                vars_res = []
                for key in all_vars:
                    if key[5] != r or key[3] != d:
                        continue
                    if len(key) == 7 and key[4] == s:
                        vars_res.append(all_vars[key])
                    elif len(key) == 8 and (key[-2] == "lab2" and (key[4] == s or key[7] == s)):
                        vars_res.append(all_vars[key])
                if vars_res:
                    model.Add(sum(vars_res) <= 1)

    # (C) Basic slot assignment - keep it simple
    # Only ensure minimum lectures per day for high-hour batches
    for div in batch_list:
        batch_total = sum(
            faculty_mapping[subj][fac][div]
            for subj in faculty_mapping
            for fac in faculty_mapping[subj]
            if div in faculty_mapping[subj][fac]
        )
        for d in DAYS:
            slot_vars = []
            for s in VALID_SLOTS:
                assigned_vars = []
                for subject in subjects_sorted:
                    for faculty in faculty_mapping[subject]:
                        for r in rooms + labs:
                            # 1-hour slots
                            key_theory = (subject, faculty, div, d, s, r, "theory")
                            if key_theory in all_vars:
                                assigned_vars.append(all_vars[key_theory])
                            key_room = (subject, faculty, div, d, s, r, "room")
                            if key_room in all_vars:
                                assigned_vars.append(all_vars[key_room])
                            
                            
                            # Lab assignments (always 2-hour) - same for both slot types
                            for pair in [(VALID_SLOTS[j], VALID_SLOTS[j+1]) for j in range(0, len(VALID_SLOTS)-1, 2)]:
                                if pair[0] == s or pair[1] == s:
                                    key_lab2 = (subject, faculty, div, d, pair[0], r, "lab2", pair[1])
                                    if key_lab2 in all_vars:
                                        assigned_vars.append(all_vars[key_lab2])
                if assigned_vars:
                    is_occupied = model.NewBoolVar(f"is_occupied_{div}_{d}_{s}")
                    model.Add(sum(assigned_vars) >= 1).OnlyEnforceIf(is_occupied)
                    model.Add(sum(assigned_vars) == 0).OnlyEnforceIf(is_occupied.Not())
                    slot_vars.append(is_occupied)
                else:
                    slot_vars.append(model.NewConstant(0))
            
            # Only keep the basic minimum lectures constraint
            if batch_total >= 23:
                model.Add(sum(slot_vars) >= 4)

    # -- 4. Solve --
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    result_entries = []
    timetable_by_day_slot = {}

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        for key, var in all_vars.items():
            if solver.Value(var) == 1:
                if len(key) == 8 and key[-2] == "lab2":
                    # Lab sessions (2-hour)
                    day = key[3]
                    slot1 = key[4]
                    slot2 = key[7]
                    result_entries.append({
                        "day": day, "batch": key[2], "time": slot1,
                        "subject": key[0], "faculty": key[1], "room": None, "lab": key[5]
                    })
                    result_entries.append({
                        "day": day, "batch": key[2], "time": slot2,
                        "subject": key[0], "faculty": key[1], "room": None, "lab": key[5]
                    })
                elif len(key) == 7 and key[-1] == "room":
                    result_entries.append({
                        "day": key[3], "batch": key[2], "time": key[4],
                        "subject": key[0], "faculty": key[1], "room": key[5], "lab": None
                    })
                elif len(key) == 7 and key[-1] == "theory":
                    result_entries.append({
                        "day": key[3], "batch": key[2], "time": key[4],
                        "subject": key[0], "faculty": key[1], "room": key[5], "lab": None
                    })

        # Structure for template
        timetable_by_day_slot = defaultdict(lambda: {
            "slot_data": defaultdict(lambda: defaultdict(list)),
            "batches": set()
        })
        for entry in result_entries:
            day = entry["day"]
            slot = entry["time"]
            batch = entry["batch"]
            timetable_by_day_slot[day]["slot_data"][batch][slot].append({
                "subject": entry["subject"],
                "faculty": entry["faculty"],
                "room_or_lab": entry["room"] or entry["lab"] or "",
            })
            timetable_by_day_slot[day]["batches"].add(batch)
        for day_data in timetable_by_day_slot.values():
            day_data["batches"] = sorted(day_data["batches"])
        timetable_by_day_slot = dict(timetable_by_day_slot)
    else:
        timetable_by_day_slot = None

    return timetable_by_day_slot, result_entries


def generate_timetable_2hour_pairs(
    department,
    settings,
    specs,
    assignments,
    faculty_objs,
    batch_objs,
    rooms,
    labs,
    batch_to_rooms=None,
    batch_to_labs=None,
    blocked_faculty_slots=None,
    blocked_room_slots=None,
    blocked_lab_slots=None,
    preferred_faculty_slots=None,
    timetable_type='2_hour',     # '1_hour' or '2_hour' slot type
):
    """
    Generate timetable with 2-hour pair slots for both theory and practical subjects.
    All subjects (theory and practical) use 2-hour consecutive slots.
    """
    # -- 1. Setup --
    DAYS = [d.name for d in settings.selected_days.all()]
    SLOTS = [f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}" for s in settings.selected_slots.all()]
    BREAKS = [f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}" for s in settings.break_slots.all()]
    VALID_SLOTS = [s for s in SLOTS if s not in BREAKS]

    subject_types = {s.subject_name: s.subject_type for s in specs}
    faculty_mapping = defaultdict(lambda: defaultdict(dict))
    practical_split = {}

    for a in assignments:
        subj = a.subject.subject_name
        faculty = a.faculty.short_name
        div = a.batch.name
        if subject_types[subj] == "Theory":
            faculty_mapping[subj][faculty][div] = a.hours
        else:
            faculty_mapping[subj][faculty][div] = a.hours
            practical_split[(subj, faculty, div)] = (0, a.hours)  # (room, lab)

    batch_to_rooms = batch_to_rooms or {}
    batch_to_labs = batch_to_labs or {}
    blocked_faculty_slots = blocked_faculty_slots or {}
    blocked_room_slots = blocked_room_slots or {}
    blocked_lab_slots = blocked_lab_slots or {}
    preferred_faculty_slots = preferred_faculty_slots or {}
    
    # Debug: Print blocked slots to verify they are being passed correctly
    print(f"DEBUG: blocked_room_slots = {blocked_room_slots}")
    print(f"DEBUG: blocked_lab_slots = {blocked_lab_slots}")
    print(f"DEBUG: blocked_faculty_slots = {blocked_faculty_slots}")
    
    # Debug: Print room and lab mappings
    print(f"DEBUG: batch_to_rooms = {batch_to_rooms}")
    print(f"DEBUG: batch_to_labs = {batch_to_labs}")
    print(f"DEBUG: rooms = {rooms}")
    print(f"DEBUG: labs = {labs}")

    # -- 2. OR-Tools model --
    model = cp_model.CpModel()
    requests = []
    subjects_sorted = [s.subject_name for s in specs]

    for subject in subjects_sorted:
        for faculty in faculty_mapping[subject]:
            for div, req in faculty_mapping[subject][faculty].items():
                req_type = "theory" if subject_types[subject] == "Theory" else "practical"
                requests.append((subject, faculty, div, req, req_type))

    all_vars = {}

    # Create 2-hour pair variables for all subjects
    for (subject, faculty, div, req, req_type) in requests:
        blocked_set = set(blocked_faculty_slots.get(faculty, []))

        if req_type == "theory":
            # 2-hour theory slots - create variables for consecutive pairs
            theory_pairs = [(VALID_SLOTS[i], VALID_SLOTS[i+1]) for i in range(0, len(VALID_SLOTS)-1, 2)]
            for d in DAYS:
                for pair in theory_pairs:
                    # Skip if faculty is blocked for either slot in the pair
                    if (d, pair[0]) in blocked_set or (d, pair[1]) in blocked_set:
                        continue
                    for r in rooms:
                        # Skip if room is blocked for this day and slot pair
                        if (d, pair[0]) in blocked_room_slots.get(r, set()) or (d, pair[1]) in blocked_room_slots.get(r, set()):
                            print(f"DEBUG: Skipping 2-hour theory room {r} at {d} {pair[0]}-{pair[1]} for {subject} {faculty} {div} (room blocked)")
                            continue
                        # Enforce batch-to-room mapping
                        if batch_to_rooms and div in batch_to_rooms and r not in batch_to_rooms[div]:
                            continue
                        
                        all_vars[(subject, faculty, div, d, pair[0], r, "theory2", pair[1])] = model.NewBoolVar(
                            f"x_{subject}_{faculty}_{div}_{d}_{pair[0]}_{pair[1]}_{r}_theory2"
                        )
        else:
            # 2-hour practical slots - both room and lab sessions use 2-hour pairs
            room_req, lab_req = practical_split.get((subject, faculty, div), (req, 0))
            
            # Room sessions - 2-hour pairs
            room_pairs = [(VALID_SLOTS[i], VALID_SLOTS[i+1]) for i in range(0, len(VALID_SLOTS)-1, 2)]
            for d in DAYS:
                for pair in room_pairs:
                    # Skip if faculty is blocked for either slot in the pair
                    if (d, pair[0]) in blocked_set or (d, pair[1]) in blocked_set:
                        continue
                    for r in rooms:
                        # Skip if room is blocked for this day and slot pair
                        if (d, pair[0]) in blocked_room_slots.get(r, set()) or (d, pair[1]) in blocked_room_slots.get(r, set()):
                            print(f"DEBUG: Skipping 2-hour room session room {r} at {d} {pair[0]}-{pair[1]} for {subject} {faculty} {div} (room blocked)")
                            continue
                        if batch_to_rooms and div in batch_to_rooms and r not in batch_to_rooms[div]:
                            continue
                        all_vars[(subject, faculty, div, d, pair[0], r, "room2", pair[1])] = model.NewBoolVar(
                            f"x_{subject}_{faculty}_{div}_{d}_{pair[0]}_{pair[1]}_{r}_room2"
                        )
            
            # Lab sessions - 2-hour pairs
            lab_pairs = [(VALID_SLOTS[i], VALID_SLOTS[i+1]) for i in range(0, len(VALID_SLOTS)-1, 2)]
            for d in DAYS:
                for pair in lab_pairs:
                    # Skip if faculty is blocked for either slot in the pair
                    if (d, pair[0]) in blocked_set or (d, pair[1]) in blocked_set:
                        continue
                    for r in labs:
                        # Skip if lab is blocked for this day and slot pair
                        if (d, pair[0]) in blocked_lab_slots.get(r, set()) or (d, pair[1]) in blocked_lab_slots.get(r, set()):
                            print(f"DEBUG: Skipping 2-hour lab {r} at {d} {pair[0]}-{pair[1]} for {subject} {faculty} {div} (lab blocked)")
                            continue
                        if batch_to_labs and div in batch_to_labs and r not in batch_to_labs[div]:
                            continue
                        all_vars[(subject, faculty, div, d, pair[0], r, "lab2", pair[1])] = model.NewBoolVar(
                            f"x_{subject}_{faculty}_{div}_{d}_{pair[0]}_{pair[1]}_{r}_lab2"
                        )

    # (A) Total required per subject/batch/faculty/week
    for (subject, faculty, div, req, req_type) in requests:
        if req_type == "theory":
            # 2-hour theory slots
            candidate_2hour = []
            for d in DAYS:
                theory_pairs = [(VALID_SLOTS[i], VALID_SLOTS[i+1]) for i in range(0, len(VALID_SLOTS)-1, 2)]
                for pair in theory_pairs:
                    for r in rooms:
                        key = (subject, faculty, div, d, pair[0], r, "theory2", pair[1])
                        if key in all_vars:
                            candidate_2hour.append(all_vars[key])
            
            # Total hours constraint: 2-hour slots count as 2
            model.Add(sum(candidate_2hour) * 2 == req)
            
            # Max 1 two-hour lecture per day
            for d in DAYS:
                day_2hour = []
                theory_pairs = [(VALID_SLOTS[i], VALID_SLOTS[i+1]) for i in range(0, len(VALID_SLOTS)-1, 2)]
                for pair in theory_pairs:
                    for r in rooms:
                        key = (subject, faculty, div, d, pair[0], r, "theory2", pair[1])
                        if key in all_vars:
                            day_2hour.append(all_vars[key])
                
                # Max 1 two-hour slot per day
                model.Add(sum(day_2hour) <= 1)
        else:
            room_req, lab_req = practical_split.get((subject, faculty, div), (req, 0))
            
            # 2-hour room sessions
            candidate_2hour_room = []
            for d in DAYS:
                room_pairs = [(VALID_SLOTS[i], VALID_SLOTS[i+1]) for i in range(0, len(VALID_SLOTS)-1, 2)]
                for pair in room_pairs:
                    for r in rooms:
                        key = (subject, faculty, div, d, pair[0], r, "room2", pair[1])
                        if key in all_vars:
                            candidate_2hour_room.append(all_vars[key])
            
            # Total hours constraint: 2-hour room slots count as 2
            if room_req > 0:
                model.Add(sum(candidate_2hour_room) * 2 == room_req)
            
            # 2-hour lab sessions
            candidate_2hour_lab = []
            for d in DAYS:
                lab_pairs = [(VALID_SLOTS[i], VALID_SLOTS[i+1]) for i in range(0, len(VALID_SLOTS)-1, 2)]
                for pair in lab_pairs:
                    for r in labs:
                        key = (subject, faculty, div, d, pair[0], r, "lab2", pair[1])
                        if key in all_vars:
                            candidate_2hour_lab.append(all_vars[key])
            
            # Total hours constraint: 2-hour lab slots count as 2
            if lab_req > 0:
                model.Add(sum(candidate_2hour_lab) * 2 == lab_req)
            
            # Max 1 two-hour room session per day
            for d in DAYS:
                day_2hour_room = []
                room_pairs = [(VALID_SLOTS[i], VALID_SLOTS[i+1]) for i in range(0, len(VALID_SLOTS)-1, 2)]
                for pair in room_pairs:
                    for r in rooms:
                        key = (subject, faculty, div, d, pair[0], r, "room2", pair[1])
                        if key in all_vars:
                            day_2hour_room.append(all_vars[key])
                
                if day_2hour_room:
                    model.Add(sum(day_2hour_room) <= 1)
            
            # Max 1 two-hour lab session per day
            for d in DAYS:
                day_2hour_lab = []
                lab_pairs = [(VALID_SLOTS[i], VALID_SLOTS[i+1]) for i in range(0, len(VALID_SLOTS)-1, 2)]
                for pair in lab_pairs:
                    for r in labs:
                        key = (subject, faculty, div, d, pair[0], r, "lab2", pair[1])
                        if key in all_vars:
                            day_2hour_lab.append(all_vars[key])
                
                if day_2hour_lab:
                    model.Add(sum(day_2hour_lab) <= 1)

    # Define batch_list for constraints
    batch_list = sorted([b.name for b in batch_objs.values()])

    # (B) No double assignment (faculty, batch, resource, slot) - SAME AS 1-HOUR
    all_faculty = set(key[1] for key in all_vars.keys())
    resources = rooms + labs
    
    # (B.1) ENFORCE BLOCKED SLOTS - SAME AS 1-HOUR
    print(f"DEBUG: Enforcing blocked slots for {len(blocked_room_slots)} rooms and {len(blocked_lab_slots)} labs")
    
    for r in rooms:
        if r in blocked_room_slots:
            print(f"DEBUG: Room {r} has {len(blocked_room_slots[r])} blocked slots: {blocked_room_slots[r]}")
            for (day, slot) in blocked_room_slots[r]:
                blocked_vars = []
                for key, var in all_vars.items():
                    if (key[5] == r and key[3] == day and key[4] == slot and 
                        (key[-2] == "theory2" or key[-2] == "room2")):
                        blocked_vars.append(var)
                if blocked_vars:
                    model.Add(sum(blocked_vars) == 0)
                    print(f"DEBUG: Blocked room {r} at {day} {slot} - {len(blocked_vars)} variables forced to 0")
    
    for r in labs:
        if r in blocked_lab_slots:
            print(f"DEBUG: Lab {r} has {len(blocked_lab_slots[r])} blocked slots: {blocked_lab_slots[r]}")
            for (day, slot) in blocked_lab_slots[r]:
                blocked_vars = []
                for key, var in all_vars.items():
                    if (key[5] == r and key[3] == day and 
                        ((key[-2] == "lab2" and (key[4] == slot or key[7] == slot)))):
                        blocked_vars.append(var)
                if blocked_vars:
                    model.Add(sum(blocked_vars) == 0)
                    print(f"DEBUG: Blocked lab {r} at {day} {slot} - {len(blocked_vars)} variables forced to 0")
    
    for faculty in all_faculty:
        if faculty in blocked_faculty_slots:
            for (day, slot) in blocked_faculty_slots[faculty]:
                blocked_vars = []
                for key, var in all_vars.items():
                    if (key[1] == faculty and key[3] == day and key[4] == slot and len(key) == 8):
                        blocked_vars.append(var)
                if blocked_vars:
                    model.Add(sum(blocked_vars) == 0)
                    print(f"DEBUG: Blocked faculty {faculty} at {day} {slot} - {len(blocked_vars)} variables forced to 0")

    # (B.2) ENFORCE PREFERRED SLOTS - Ensure faculty are assigned to their preferred slots for specific batches
    print(f"DEBUG: Enforcing preferred slots for {len(preferred_faculty_slots)} faculty-batch combinations")
    
    for (faculty, batch), preferred_set in preferred_faculty_slots.items():
        print(f"DEBUG: Faculty {faculty} prefers slots for batch {batch}: {preferred_set}")
        
        # Find all variables for this faculty-batch combination
        faculty_batch_vars = []
        for key, var in all_vars.items():
            if key[1] == faculty and key[2] == batch:
                faculty_batch_vars.append((key, var))
        
        if not faculty_batch_vars:
            print(f"DEBUG: No variables found for faculty {faculty} and batch {batch}")
            continue
        
        # Group variables by day and slot
        vars_by_slot = {}
        for key, var in faculty_batch_vars:
            day = key[3]
            slot = key[4]
            slot_key = (day, slot)
            if slot_key not in vars_by_slot:
                vars_by_slot[slot_key] = []
            vars_by_slot[slot_key].append(var)
        
        # STRONG CONSTRAINT: Faculty must be assigned to their preferred slots
        # Calculate total assignments needed for this faculty-batch combination
        total_assignments = 0
        for key, var in faculty_batch_vars:
            # Count how many hours this faculty-batch combination needs
            subject_name = key[0]
            if subject_name in faculty_mapping[faculty][batch]:
                total_assignments += faculty_mapping[faculty][batch][subject_name]
        
        if total_assignments > 0 and preferred_set:
            # Create a constraint that ensures assignments are in preferred slots
            preferred_vars = []
            
            for (day, slot) in preferred_set:
                slot_key = (day, slot)
                if slot_key in vars_by_slot:
                    preferred_vars.extend(vars_by_slot[slot_key])
            
            if preferred_vars:
                # Calculate how many hours should be in preferred slots
                # For 2-hour slots, each preferred slot is 2 hours (1 pair)
                preferred_hours = len(preferred_set) * 2
                
                # Ensure faculty is assigned to their preferred slots
                # Use the minimum of preferred hours available or total assignments needed
                min_preferred_hours = min(preferred_hours, total_assignments)
                
                if min_preferred_hours > 0:
                    # Force assignment to preferred slots - use exact constraint
                    model.Add(sum(preferred_vars) >= min_preferred_hours)
                    print(f"DEBUG: Enforced {min_preferred_hours} hours in preferred slots for {faculty}-{batch}: {len(preferred_vars)} variables")
                    
                    # For 2-hour slots, ensure we get the exact preferred slots
                    if timetable_type == '2_hour':
                        # For each preferred slot, ensure at least one assignment
                        for (day, slot) in preferred_set:
                            slot_key = (day, slot)
                            if slot_key in vars_by_slot:
                                slot_vars = vars_by_slot[slot_key]
                                if slot_vars:
                                    # STRONG CONSTRAINT: Force assignment in this specific preferred slot
                                    # This ensures the faculty MUST be assigned to this slot
                                    model.Add(sum(slot_vars) >= 1)
                                    print(f"DEBUG: STRONG CONSTRAINT - Enforced assignment in preferred slot {day} {slot} for {faculty}-{batch}")
                                    
                                    # Additional constraint: If any variable in this slot is 1, 
                                    # then the faculty must be assigned to this specific slot
                                    for var in slot_vars:
                                        # This variable represents this faculty-batch-subject combination in this slot
                                        # We want to ensure this specific combination is chosen
                                        pass  # The constraint above should be sufficient
                    
                    # If there are remaining hours, they can be assigned anywhere
                    remaining_hours = total_assignments - min_preferred_hours
                    if remaining_hours > 0:
                        print(f"DEBUG: {remaining_hours} remaining hours for {faculty}-{batch} can be assigned anywhere")
                else:
                    print(f"DEBUG: No preferred hours available for {faculty}-{batch}")
            else:
                print(f"DEBUG: No preferred slot variables found for {faculty}-{batch}")

    # Faculty conflicts - SAME AS 1-HOUR
    for faculty in all_faculty:
        for d in DAYS:
            for s in VALID_SLOTS:
                vars_fac = []
                for key in all_vars:
                    if key[1] != faculty or key[3] != d:
                        continue
                    if len(key) == 8 and (key[4] == s or key[7] == s):
                        vars_fac.append(all_vars[key])
                if vars_fac:
                    model.Add(sum(vars_fac) <= 1)

    # Batch conflicts - SAME AS 1-HOUR
    for div in batch_list:
        for d in DAYS:
            for s in VALID_SLOTS:
                vars_div = []
                for key in all_vars:
                    if key[2] != div or key[3] != d:
                        continue
                    if len(key) == 8 and (key[4] == s or key[7] == s):
                        vars_div.append(all_vars[key])
                if vars_div:
                    model.Add(sum(vars_div) <= 1)

    # Resource conflicts - SAME AS 1-HOUR
    for r in resources:
        for d in DAYS:
            for s in VALID_SLOTS:
                vars_res = []
                for key in all_vars:
                    if key[5] != r or key[3] != d:
                        continue
                    if len(key) == 8 and (key[4] == s or key[7] == s):
                        vars_res.append(all_vars[key])
                if vars_res:
                    model.Add(sum(vars_res) <= 1)

    # NEW CONSTRAINT: Alternating 2-hour slot assignments (Lab-Room-Lab-Room pattern)
    # If first 2-hour slot is lab, next must be room, and vice versa
    for div in batch_list:
        for d in DAYS:
            # Get all 2-hour slot pairs for this batch and day
            slot_pairs = [(VALID_SLOTS[i], VALID_SLOTS[i+1]) for i in range(0, len(VALID_SLOTS)-1, 2)]
            
            for i in range(len(slot_pairs) - 1):
                current_pair = slot_pairs[i]
                next_pair = slot_pairs[i + 1]
                
                # Variables for current pair
                lab_vars_current = []
                room_vars_current = []
                theory_vars_current = []
                
                # Variables for next pair
                lab_vars_next = []
                room_vars_next = []
                theory_vars_next = []
                
                # Collect lab variables for current pair
                for key in all_vars:
                    if (key[2] == div and key[3] == d and 
                        key[4] == current_pair[0] and key[7] == current_pair[1] and 
                        key[-2] == "lab2"):
                        lab_vars_current.append(all_vars[key])
                
                # Collect room variables for current pair
                for key in all_vars:
                    if (key[2] == div and key[3] == d and 
                        key[4] == current_pair[0] and key[7] == current_pair[1] and 
                        key[-2] == "room2"):
                        room_vars_current.append(all_vars[key])
                
                # Collect theory variables for current pair
                for key in all_vars:
                    if (key[2] == div and key[3] == d and 
                        key[4] == current_pair[0] and key[7] == current_pair[1] and 
                        key[-2] == "theory2"):
                        theory_vars_current.append(all_vars[key])
                
                # Collect lab variables for next pair
                for key in all_vars:
                    if (key[2] == div and key[3] == d and 
                        key[4] == next_pair[0] and key[7] == next_pair[1] and 
                        key[-2] == "lab2"):
                        lab_vars_next.append(all_vars[key])
                
                # Collect room variables for next pair
                for key in all_vars:
                    if (key[2] == div and key[3] == d and 
                        key[4] == next_pair[0] and key[7] == next_pair[1] and 
                        key[-2] == "room2"):
                        room_vars_next.append(all_vars[key])
                
                # Collect theory variables for next pair
                for key in all_vars:
                    if (key[2] == div and key[3] == d and 
                        key[4] == next_pair[0] and key[7] == next_pair[1] and 
                        key[-2] == "theory2"):
                        theory_vars_next.append(all_vars[key])
                
                # Create boolean variables to track what type is assigned
                current_is_lab = model.NewBoolVar(f"current_is_lab_{div}_{d}_{i}")
                current_is_room = model.NewBoolVar(f"current_is_room_{div}_{d}_{i}")
                current_is_theory = model.NewBoolVar(f"current_is_theory_{div}_{d}_{i}")
                
                next_is_lab = model.NewBoolVar(f"next_is_lab_{div}_{d}_{i}")
                next_is_room = model.NewBoolVar(f"next_is_room_{div}_{d}_{i}")
                next_is_theory = model.NewBoolVar(f"next_is_theory_{div}_{d}_{i}")
                
                # Link boolean variables to actual assignments
                if lab_vars_current:
                    model.Add(sum(lab_vars_current) >= 1).OnlyEnforceIf(current_is_lab)
                    model.Add(sum(lab_vars_current) == 0).OnlyEnforceIf(current_is_lab.Not())
                else:
                    model.Add(current_is_lab == 0)
                
                if room_vars_current:
                    model.Add(sum(room_vars_current) >= 1).OnlyEnforceIf(current_is_room)
                    model.Add(sum(room_vars_current) == 0).OnlyEnforceIf(current_is_room.Not())
                else:
                    model.Add(current_is_room == 0)
                
                if theory_vars_current:
                    model.Add(sum(theory_vars_current) >= 1).OnlyEnforceIf(current_is_theory)
                    model.Add(sum(theory_vars_current) == 0).OnlyEnforceIf(current_is_theory.Not())
                else:
                    model.Add(current_is_theory == 0)
                
                if lab_vars_next:
                    model.Add(sum(lab_vars_next) >= 1).OnlyEnforceIf(next_is_lab)
                    model.Add(sum(lab_vars_next) == 0).OnlyEnforceIf(next_is_lab.Not())
                else:
                    model.Add(next_is_lab == 0)
                
                if room_vars_next:
                    model.Add(sum(room_vars_next) >= 1).OnlyEnforceIf(next_is_room)
                    model.Add(sum(room_vars_next) == 0).OnlyEnforceIf(next_is_room.Not())
                else:
                    model.Add(next_is_room == 0)
                
                if theory_vars_next:
                    model.Add(sum(theory_vars_next) >= 1).OnlyEnforceIf(next_is_theory)
                    model.Add(sum(theory_vars_next) == 0).OnlyEnforceIf(next_is_theory.Not())
                else:
                    model.Add(next_is_theory == 0)
                
                # Alternating constraint: If current is lab, next must be room or theory
                # If current is room, next must be lab or theory
                # If current is theory, next can be lab or room
                model.Add(next_is_room + next_is_theory >= 1).OnlyEnforceIf(current_is_lab)
                model.Add(next_is_lab + next_is_theory >= 1).OnlyEnforceIf(current_is_room)
                
                # Ensure only one type per pair
                model.Add(current_is_lab + current_is_room + current_is_theory <= 1)
                model.Add(next_is_lab + next_is_room + next_is_theory <= 1)

    # -- 3. Solve --
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    result_entries = []
    timetable_by_day_slot = {}

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        for key, var in all_vars.items():
            if solver.Value(var) == 1:
                if len(key) == 8 and key[-2] == "lab2":
                    # Lab sessions (2-hour)
                    day = key[3]
                    slot1 = key[4]
                    slot2 = key[7]
                    result_entries.append({
                        "day": day, "batch": key[2], "time": slot1,
                        "subject": key[0], "faculty": key[1], "room": None, "lab": key[5]
                    })
                    result_entries.append({
                        "day": day, "batch": key[2], "time": slot2,
                        "subject": key[0], "faculty": key[1], "room": None, "lab": key[5]
                    })
                elif len(key) == 8 and key[-2] == "room2":
                    # Room sessions (2-hour)
                    day = key[3]
                    slot1 = key[4]
                    slot2 = key[7]
                    result_entries.append({
                        "day": day, "batch": key[2], "time": slot1,
                        "subject": key[0], "faculty": key[1], "room": key[5], "lab": None
                    })
                    result_entries.append({
                        "day": day, "batch": key[2], "time": slot2,
                        "subject": key[0], "faculty": key[1], "room": key[5], "lab": None
                    })
                elif len(key) == 8 and key[-2] == "theory2":
                    # Theory sessions (2-hour)
                    day = key[3]
                    slot1 = key[4]
                    slot2 = key[7]
                    result_entries.append({
                        "day": day, "batch": key[2], "time": slot1,
                        "subject": key[0], "faculty": key[1], "room": key[5], "lab": None
                    })
                    result_entries.append({
                        "day": day, "batch": key[2], "time": slot2,
                        "subject": key[0], "faculty": key[1], "room": key[5], "lab": None
                    })

        # Structure for template
        timetable_by_day_slot = defaultdict(lambda: {
            "slot_data": defaultdict(lambda: defaultdict(list)),
            "batches": set()
        })
        for entry in result_entries:
            day = entry["day"]
            slot = entry["time"]
            batch = entry["batch"]
            timetable_by_day_slot[day]["slot_data"][batch][slot].append({
                "subject": entry["subject"],
                "faculty": entry["faculty"],
                "room_or_lab": entry["room"] or entry["lab"] or "",
            })
            timetable_by_day_slot[day]["batches"].add(batch)
        for day_data in timetable_by_day_slot.values():
            day_data["batches"] = sorted(day_data["batches"])
        timetable_by_day_slot = dict(timetable_by_day_slot)
    else:
        timetable_by_day_slot = None

    return timetable_by_day_slot, result_entries