from collections import defaultdict

try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
except ImportError:
    cp_model = None
    ORTOOLS_AVAILABLE = False

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
    timetable_type='2_hour',     # Always use 2-hour pair slots
):
    """
    Main timetable generation function. Uses 2-hour pair slot logic.
    """
    if not ORTOOLS_AVAILABLE:
        raise ImportError(
            "The 'ortools' package is required for timetable generation but is not installed. "
            "Install it with: pip install ortools. "
            "On PythonAnywhere free tier, disk quota may prevent installation; consider upgrading or freeing disk space."
        )
    return generate_timetable_2hour_pairs(
        department, settings, specs, assignments, faculty_objs, batch_objs,
        rooms, labs, batch_to_rooms, batch_to_labs,
        blocked_faculty_slots, blocked_room_slots, blocked_lab_slots, preferred_faculty_slots, timetable_type
    )


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
    timetable_type='2_hour',
):
    """
    Generate timetable with 2-hour pair slots for both theory and practical subjects.
    
    For THEORY subjects:
    - Use as many 2-hour pairs as possible.
    - If total hours are odd, schedule exactly one additional 1-hour lecture.
    
    For PRACTICAL subjects:
    - Still use pure 2-hour pairs (labs/rooms), no 1-hour practicals.
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
            # Check room_or_lab field to determine if it's room or lab assignment
            if a.room_or_lab == 'Room':
                practical_split[(subj, faculty, div)] = (a.hours, 0)  # (room, lab)
            else:  # 'Lab'
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

    # Create variables for all subjects
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

            # 1-hour theory slots - used only as leftover when total hours are odd
            for d in DAYS:
                for s in VALID_SLOTS:
                    # Skip if faculty is blocked for this slot
                    if (d, s) in blocked_set:
                        continue
                    for r in rooms:
                        # Skip if room is blocked for this day/slot
                        if (d, s) in blocked_room_slots.get(r, set()):
                            continue
                        # Enforce batch-to-room mapping
                        if batch_to_rooms and div in batch_to_rooms and r not in batch_to_rooms[div]:
                            continue

                        all_vars[(subject, faculty, div, d, s, r, "theory1")] = model.NewBoolVar(
                            f"x_{subject}_{faculty}_{div}_{d}_{s}_{r}_theory1"
                        )
        else:
            # Practical slots - create variables for 2-hour pairs and possible 1-hour leftovers
            room_req, lab_req = practical_split.get((subject, faculty, div), (req, 0))
            
            # ----- ROOM PRACTICALS -----
            if room_req > 0:
                # 2-hour room pairs
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

                # 1-hour room practicals (leftover)
                for d in DAYS:
                    for s in VALID_SLOTS:
                        if (d, s) in blocked_set:
                            continue
                        for r in rooms:
                            if (d, s) in blocked_room_slots.get(r, set()):
                                continue
                            if batch_to_rooms and div in batch_to_rooms and r not in batch_to_rooms[div]:
                                continue
                            all_vars[(subject, faculty, div, d, s, r, "room1")] = model.NewBoolVar(
                                f"x_{subject}_{faculty}_{div}_{d}_{s}_{r}_room1"
                            )
            
            # ----- LAB PRACTICALS -----
            if lab_req > 0:
                # 2-hour lab pairs
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

                # 1-hour lab practicals (leftover)
                for d in DAYS:
                    for s in VALID_SLOTS:
                        if (d, s) in blocked_set:
                            continue
                        for r in labs:
                            if (d, s) in blocked_lab_slots.get(r, set()):
                                continue
                            if batch_to_labs and div in batch_to_labs and r not in batch_to_labs[div]:
                                continue
                            all_vars[(subject, faculty, div, d, s, r, "lab1")] = model.NewBoolVar(
                                f"x_{subject}_{faculty}_{div}_{d}_{s}_{r}_lab1"
                            )

    # (A) Total required per subject/batch/faculty/week
    for (subject, faculty, div, req, req_type) in requests:
        if req_type == "theory":
            # 2-hour theory slots (pairs)
            candidate_2hour = []
            for d in DAYS:
                theory_pairs = [(VALID_SLOTS[i], VALID_SLOTS[i+1]) for i in range(0, len(VALID_SLOTS)-1, 2)]
                for pair in theory_pairs:
                    for r in rooms:
                        key = (subject, faculty, div, d, pair[0], r, "theory2", pair[1])
                        if key in all_vars:
                            candidate_2hour.append(all_vars[key])

            # 1-hour theory slots (leftover hours)
            candidate_1hour = []
            for d in DAYS:
                for s in VALID_SLOTS:
                    for r in rooms:
                        key_single = (subject, faculty, div, d, s, r, "theory1")
                        if key_single in all_vars:
                            candidate_1hour.append(all_vars[key_single])

            # Use maximum possible 2-hour pairs, remaining as single-hour lectures
            pairs_needed = req // 2
            leftover_hours = req % 2

            # Exactly 'pairs_needed' two-hour sessions
            model.Add(sum(candidate_2hour) == pairs_needed)

            # Exactly one 1-hour lecture if hours are odd, else none
            if leftover_hours == 1:
                model.Add(sum(candidate_1hour) == 1)
            else:
                model.Add(sum(candidate_1hour) == 0)
            
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
            
            # ----- ROOM PRACTICALS -----
            candidate_2hour_room = []
            candidate_1hour_room = []
            for d in DAYS:
                room_pairs = [(VALID_SLOTS[i], VALID_SLOTS[i+1]) for i in range(0, len(VALID_SLOTS)-1, 2)]
                for pair in room_pairs:
                    for r in rooms:
                        key = (subject, faculty, div, d, pair[0], r, "room2", pair[1])
                        if key in all_vars:
                            candidate_2hour_room.append(all_vars[key])
                for s in VALID_SLOTS:
                    for r in rooms:
                        key_single = (subject, faculty, div, d, s, r, "room1")
                        if key_single in all_vars:
                            candidate_1hour_room.append(all_vars[key_single])
            
            if room_req > 0:
                room_pairs_needed = room_req // 2
                room_leftover = room_req % 2
                # 2-hour room sessions
                model.Add(sum(candidate_2hour_room) == room_pairs_needed)
                # 1-hour leftover room sessions
                if room_leftover == 1:
                    model.Add(sum(candidate_1hour_room) == 1)
                else:
                    model.Add(sum(candidate_1hour_room) == 0)
            
            # ----- LAB PRACTICALS -----
            candidate_2hour_lab = []
            candidate_1hour_lab = []
            for d in DAYS:
                lab_pairs = [(VALID_SLOTS[i], VALID_SLOTS[i+1]) for i in range(0, len(VALID_SLOTS)-1, 2)]
                for pair in lab_pairs:
                    for r in labs:
                        key = (subject, faculty, div, d, pair[0], r, "lab2", pair[1])
                        if key in all_vars:
                            candidate_2hour_lab.append(all_vars[key])
                for s in VALID_SLOTS:
                    for r in labs:
                        key_single = (subject, faculty, div, d, s, r, "lab1")
                        if key_single in all_vars:
                            candidate_1hour_lab.append(all_vars[key_single])
            
            if lab_req > 0:
                lab_pairs_needed = lab_req // 2
                lab_leftover = lab_req % 2
                # 2-hour lab sessions
                model.Add(sum(candidate_2hour_lab) == lab_pairs_needed)
                # 1-hour leftover lab sessions
                if lab_leftover == 1:
                    model.Add(sum(candidate_1hour_lab) == 1)
                else:
                    model.Add(sum(candidate_1hour_lab) == 0)
            
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
                    if key[5] != r or key[3] != day:
                        continue
                    # Block 2-hour theory/room pairs that touch this slot
                    if len(key) == 8 and (key[-2] == "theory2" or key[-2] == "room2") and (key[4] == slot or key[7] == slot):
                        blocked_vars.append(var)
                    # Block 1-hour theory/room sessions exactly at this slot
                    elif len(key) == 7 and key[4] == slot and (key[-1] == "theory1" or key[-1] == "room1"):
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
                    if key[5] != r or key[3] != day:
                        continue
                    # Block 2-hour lab pairs that touch this slot
                    if len(key) == 8 and key[-2] == "lab2" and (key[4] == slot or key[7] == slot):
                        blocked_vars.append(var)
                    # Block 1-hour lab sessions exactly at this slot
                    elif len(key) == 7 and key[4] == slot and key[-1] == "lab1":
                        blocked_vars.append(var)
                if blocked_vars:
                    model.Add(sum(blocked_vars) == 0)
                    print(f"DEBUG: Blocked lab {r} at {day} {slot} - {len(blocked_vars)} variables forced to 0")
    
    for faculty in all_faculty:
        if faculty in blocked_faculty_slots:
            for (day, slot) in blocked_faculty_slots[faculty]:
                blocked_vars = []
                for key, var in all_vars.items():
                    if key[1] != faculty or key[3] != day or key[4] != slot:
                        continue
                    # Block any 2-hour assignment that touches this slot
                    if len(key) == 8:
                        blocked_vars.append(var)
                    # Block any 1-hour assignment at this slot
                    elif len(key) == 7 and (key[-1] in ["theory1", "room1", "lab1"]):
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

    # Faculty conflicts - SAME AS 1-HOUR (extended for 1-hour theory)
    for faculty in all_faculty:
        for d in DAYS:
            for s in VALID_SLOTS:
                vars_fac = []
                for key in all_vars:
                    if key[1] != faculty or key[3] != d:
                        continue
                    # 2-hour assignments that occupy this slot
                    if len(key) == 8 and (key[4] == s or key[7] == s):
                        vars_fac.append(all_vars[key])
                    # 1-hour theory/room/lab assignments exactly at this slot
                    elif len(key) == 7 and key[4] == s and (key[-1] in ["theory1", "room1", "lab1"]):
                        vars_fac.append(all_vars[key])
                if vars_fac:
                    model.Add(sum(vars_fac) <= 1)

    # Batch conflicts - SAME AS 1-HOUR (extended for 1-hour theory)
    for div in batch_list:
        for d in DAYS:
            for s in VALID_SLOTS:
                vars_div = []
                for key in all_vars:
                    if key[2] != div or key[3] != d:
                        continue
                    # 2-hour assignments that occupy this slot
                    if len(key) == 8 and (key[4] == s or key[7] == s):
                        vars_div.append(all_vars[key])
                    # 1-hour theory/room/lab assignments exactly at this slot
                    elif len(key) == 7 and key[4] == s and (key[-1] in ["theory1", "room1", "lab1"]):
                        vars_div.append(all_vars[key])
                if vars_div:
                    model.Add(sum(vars_div) <= 1)

    # Resource conflicts - SAME AS 1-HOUR (extended for 1-hour theory)
    for r in resources:
        for d in DAYS:
            for s in VALID_SLOTS:
                vars_res = []
                for key in all_vars:
                    if key[5] != r or key[3] != d:
                        continue
                    # 2-hour assignments that occupy this slot
                    if len(key) == 8 and (key[4] == s or key[7] == s):
                        vars_res.append(all_vars[key])
                    # 1-hour theory/room/lab assignments exactly at this slot
                    elif len(key) == 7 and key[4] == s and (key[-1] in ["theory1", "room1", "lab1"]):
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
                
                # Collect 2-hour pair variables only (key length 8); skip 1-hour vars (length 7)
                # Collect lab variables for current pair
                for key in all_vars:
                    if len(key) != 8:
                        continue
                    if (key[2] == div and key[3] == d and 
                        key[4] == current_pair[0] and key[7] == current_pair[1] and 
                        key[-2] == "lab2"):
                        lab_vars_current.append(all_vars[key])
                
                # Collect room variables for current pair
                for key in all_vars:
                    if len(key) != 8:
                        continue
                    if (key[2] == div and key[3] == d and 
                        key[4] == current_pair[0] and key[7] == current_pair[1] and 
                        key[-2] == "room2"):
                        room_vars_current.append(all_vars[key])
                
                # Collect theory variables for current pair
                for key in all_vars:
                    if len(key) != 8:
                        continue
                    if (key[2] == div and key[3] == d and 
                        key[4] == current_pair[0] and key[7] == current_pair[1] and 
                        key[-2] == "theory2"):
                        theory_vars_current.append(all_vars[key])
                
                # Collect lab variables for next pair
                for key in all_vars:
                    if len(key) != 8:
                        continue
                    if (key[2] == div and key[3] == d and 
                        key[4] == next_pair[0] and key[7] == next_pair[1] and 
                        key[-2] == "lab2"):
                        lab_vars_next.append(all_vars[key])
                
                # Collect room variables for next pair
                for key in all_vars:
                    if len(key) != 8:
                        continue
                    if (key[2] == div and key[3] == d and 
                        key[4] == next_pair[0] and key[7] == next_pair[1] and 
                        key[-2] == "room2"):
                        room_vars_next.append(all_vars[key])
                
                # Collect theory variables for next pair
                for key in all_vars:
                    if len(key) != 8:
                        continue
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

    # Objective: Prefer placing classes in earlier time slots so free slots stay at the end
    # Minimize sum(slot_index * assigned) so the solver fills early slots first (low index)
    slot_index_map = {s: i for i, s in enumerate(VALID_SLOTS)}
    objective_terms = []
    for key, var in all_vars.items():
        slot0 = key[4]
        idx = slot_index_map.get(slot0, 0)
        objective_terms.append(idx * var)
    model.Minimize(sum(objective_terms))

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
                    # Theory sessions (2-hour) — emit both slot1 and slot2 so both cells show in the timetable
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
                elif len(key) == 7 and key[-1] == "theory1":
                    # Single 1-hour theory lecture
                    result_entries.append({
                        "day": key[3], "batch": key[2], "time": key[4],
                        "subject": key[0], "faculty": key[1], "room": key[5], "lab": None
                    })
                elif len(key) == 7 and key[-1] == "room1":
                    # Single 1-hour room practical
                    result_entries.append({
                        "day": key[3], "batch": key[2], "time": key[4],
                        "subject": key[0], "faculty": key[1], "room": key[5], "lab": None
                    })
                elif len(key) == 7 and key[-1] == "lab1":
                    # Single 1-hour lab practical
                    result_entries.append({
                        "day": key[3], "batch": key[2], "time": key[4],
                        "subject": key[0], "faculty": key[1], "room": None, "lab": key[5]
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

    status_name = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
        cp_model.UNKNOWN: "UNKNOWN",
    }.get(status, str(status))
    return timetable_by_day_slot, result_entries, status, status_name


def diagnose_timetable_failure(
    department, settings, specs, assignments, faculty_objs, batch_objs,
    rooms, labs,
    batch_to_rooms=None, batch_to_labs=None,
    blocked_faculty_slots=None, blocked_room_slots=None, blocked_lab_slots=None,
    preferred_faculty_slots=None, timetable_type='2_hour',
):
    """Identify which constraint type likely causes timetable generation to fail."""
    if not ORTOOLS_AVAILABLE:
        return [{
            "type": "ortools_missing",
            "title": "ortools Not Installed",
            "description": "The 'ortools' package is required for timetable generation and diagnosis.",
            "fix": "Install with: pip install ortools. On PythonAnywhere free tier, free disk space or upgrade your plan.",
        }]
    reasons = []
    bf = blocked_faculty_slots or {}
    br = blocked_room_slots or {}
    bl = blocked_lab_slots or {}
    pf = preferred_faculty_slots or {}
    btr = batch_to_rooms or {}
    btl = batch_to_labs or {}

    def try_gen(no_fac=False, no_room=False, no_lab=False, no_pref=False):
        tt, entries, status, _ = generate_timetable(
            department, settings, specs, assignments, faculty_objs, batch_objs,
            rooms, labs, batch_to_rooms=btr, batch_to_labs=btl,
            blocked_faculty_slots={} if no_fac else bf,
            blocked_room_slots={} if no_room else br,
            blocked_lab_slots={} if no_lab else bl,
            preferred_faculty_slots={} if no_pref else pf,
            timetable_type=timetable_type,
        )
        return status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

    if bf and try_gen(no_fac=True):
        reasons.append({
            "type": "faculty_block",
            "title": "Faculty Blocked Slots / Visiting Faculty Blocks",
            "description": "Faculty blocked slots prevent scheduling all lectures.",
            "fix": "Review Faculty Blocked Slots or Visiting Faculty Blocks.",
            "url_name": "manage_faculty_blocks",
            "url_name2": "manage_visiting_blocks",
        })
    if br and try_gen(no_room=True):
        reasons.append({
            "type": "room_block",
            "title": "Room Blocked Slots",
            "description": "Room blocked slots prevent scheduling.",
            "fix": "Review Room Blocked Slots.",
            "url_name": "manage_room_blocks",
        })
    if bl and try_gen(no_lab=True):
        reasons.append({
            "type": "lab_block",
            "title": "Lab Blocked Slots",
            "description": "Lab blocked slots prevent scheduling.",
            "fix": "Review Lab Blocked Slots.",
            "url_name": "manage_lab_blocks",
        })
    if pf and try_gen(no_pref=True):
        reasons.append({
            "type": "preferred_slots",
            "title": "Faculty Preferred Slots",
            "description": "Preferred slot constraints are too strict.",
            "fix": "Review Faculty Preferred Slots.",
            "url_name": "faculty_preferred_slots_list",
        })
    if not reasons:
        reasons.append({
            "type": "generic",
            "title": "Complex Constraint Conflict",
            "description": "Constraints may be too tight.",
            "fix": "Add rooms/labs, batch mappings, or reduce blocks.",
        })
    return reasons