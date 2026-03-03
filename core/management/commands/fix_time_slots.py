from django.core.management.base import BaseCommand
from core.models import GlobalTimeSlot, Department, TimeSettings
from datetime import time

class Command(BaseCommand):
    help = 'Fix time slots to match the actual timetable format'

    def handle(self, *args, **options):
        self.stdout.write('Fixing time slots...')
        
        # Define the correct time slots based on the timetable image
        correct_slots = [
            (time(8, 45), time(9, 45)),   # 08:45 - 09:45
            (time(9, 45), time(10, 45)),  # 09:45 - 10:45
            (time(11, 30), time(12, 30)), # 11:30 - 12:30
            (time(12, 30), time(13, 30)), # 12:30 - 13:30 (This is the missing one!)
            (time(13, 45), time(14, 45)), # 13:45 - 14:45 (if needed)
        ]
        
        # Clear existing time slots
        GlobalTimeSlot.objects.all().delete()
        self.stdout.write('Cleared existing time slots')
        
        # Create new time slots
        for start_time, end_time in correct_slots:
            slot, created = GlobalTimeSlot.objects.get_or_create(
                start_time=start_time,
                end_time=end_time
            )
            if created:
                self.stdout.write(f'Created time slot: {start_time} - {end_time}')
            else:
                self.stdout.write(f'Time slot already exists: {start_time} - {end_time}')
        
        # Update all department time settings to use these slots
        for department in Department.objects.all():
            try:
                time_settings = department.timesettings
                time_settings.selected_slots.set(GlobalTimeSlot.objects.all())
                self.stdout.write(f'Updated time settings for {department.name}')
            except TimeSettings.DoesNotExist:
                # Create time settings if they don't exist
                time_settings = TimeSettings.objects.create(department=department)
                time_settings.selected_slots.set(GlobalTimeSlot.objects.all())
                self.stdout.write(f'Created time settings for {department.name}')
        
        self.stdout.write(
            self.style.SUCCESS('Successfully fixed time slots!')
        )
