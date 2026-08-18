from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.colors import black, grey, HexColor, lightgrey, white
from reportlab.lib.pagesizes import letter
from datetime import datetime, timedelta, date

class PDFGenerator:
    # Design constants
    CYAN = HexColor('#00BCD4')       # Active tab, current day highlight
    BEIGE = HexColor('#F5E6D3')      # Sidebar background
    GRAY = HexColor('#9E9E9E')       # Inactive tabs
    LIGHT_GRAY = HexColor('#E0E0E0') # Lines

    def __init__(self):
        # Page dimensions for reMarkable Pro Move (1696 x 954 pixels at 264 PPI)
        # Convert pixels to points (72 points per inch)
        pixels_per_inch = 264
        points_per_inch = 72
        conversion_factor = points_per_inch / pixels_per_inch

        self.page_width = 954 * conversion_factor  # ~260 points
        self.page_height = 1696 * conversion_factor   # ~462 points
        self.margin = 18  # 0.25 inch in points

        # Sidebar dimensions
        self.sidebar_width = 32

        # Content area (excluding sidebar)
        self.content_width = self.page_width - (2 * self.margin) - self.sidebar_width
        self.content_height = self.page_height - (2 * self.margin)

        # Page tracking for PDF links
        self.page_index = {}  # {(date_str, page_type): page_num}
        self.current_page = 0

    def generate_pdf(self, start_date, end_date, events, output_path, start_hour=6, end_hour=17, show_todos=True, calendar_colors=None):
        """Generate PDF with 7 pages per day for the specified date range"""
        if calendar_colors is None:
            calendar_colors = ['#4A4A4A']

        c = canvas.Canvas(output_path, pagesize=(self.page_width, self.page_height))
        c.setStrokeColor(black)
        c.setLineWidth(0)

        # Calculate number of days
        total_days = (end_date - start_date).days + 1

        # Get unique years in the range
        years = set()
        current = start_date
        while current <= end_date:
            years.add(current.year)
            current += timedelta(days=1)
        years = sorted(years)

        # First pass: build page index for linking
        self.page_index = {}
        self.current_page = 0

        # Year view pages come first
        for year in years:
            self.page_index[(str(year), 'year_view')] = self.current_page
            self.current_page += 1

        # Then daily pages
        for day_offset in range(total_days):
            current_date = start_date + timedelta(days=day_offset)
            date_str = current_date.strftime('%Y-%m-%d')

            # Each day has 7 pages
            self.page_index[(date_str, 'schedule')] = self.current_page
            self.page_index[(date_str, 'goals')] = self.current_page + 1
            for note_num in range(1, 6):
                self.page_index[(date_str, f'notes_{note_num}')] = self.current_page + 1 + note_num
            self.current_page += 7

        # Store date range for sidebar linking
        self.start_date = start_date
        self.end_date = end_date

        # Second pass: generate pages
        self.current_page = 0

        # Generate year view pages first
        for year in years:
            self._add_bookmark(c, f"year_{year}")
            self.draw_year_view_page(c, year, start_date, end_date)
            c.showPage()
            self.current_page += 1

        # Generate daily pages
        for day_offset in range(total_days):
            current_date = start_date + timedelta(days=day_offset)
            date_str = current_date.strftime('%Y-%m-%d')
            day_events = [e for e in events if e['date'] == date_str]

            # Get week info for this date
            week_dates = self._get_week_dates(current_date, start_date, end_date)

            # Page 1: Schedule
            self._add_bookmark(c, f"day_{date_str}_schedule")
            self.draw_schedule_page(c, current_date, day_events, start_hour, end_hour,
                                   calendar_colors, week_dates, start_date, end_date)
            c.showPage()
            self.current_page += 1

            # Page 2: Goals & To-Dos
            self._add_bookmark(c, f"day_{date_str}_goals")
            self.draw_goals_todos_page(c, current_date, week_dates, start_date, end_date)
            c.showPage()
            self.current_page += 1

            # Pages 3-7: Notes (5 pages)
            for note_num in range(1, 6):
                self._add_bookmark(c, f"day_{date_str}_notes_{note_num}")
                self.draw_notes_page(c, current_date, note_num, week_dates, start_date, end_date)
                if note_num < 5 or day_offset < total_days - 1:
                    c.showPage()
                self.current_page += 1

        c.save()

    def _add_bookmark(self, c, name):
        """Add a named destination for PDF linking"""
        c.bookmarkPage(name)

    def draw_year_view_page(self, c, year, start_date, end_date):
        """Draw a year calendar view with all 12 months"""
        import calendar

        y_pos = self.page_height - self.margin

        # Year title
        c.setFont("Helvetica-Bold", 18)
        c.setFillColor(black)
        c.drawString(self.margin, y_pos - 5, str(year))

        y_pos -= 25

        # Calculate grid dimensions (3 columns x 4 rows of months)
        month_width = (self.page_width - 2 * self.margin) / 3
        month_height = (y_pos - self.margin) / 4

        # Draw each month
        for month in range(1, 13):
            # Calculate position (0-indexed)
            col = (month - 1) % 3
            row = (month - 1) // 3

            month_x = self.margin + col * month_width
            month_y = y_pos - (row + 1) * month_height

            self._draw_mini_month(c, year, month, month_x, month_y,
                                 month_width - 5, month_height - 5,
                                 start_date, end_date)

    def _draw_mini_month(self, c, year, month, x, y, width, height, start_date, end_date):
        """Draw a mini calendar for a single month"""
        import calendar

        # Month name
        month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October', 'November', 'December']

        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(black)
        c.drawString(x + 2, y + height - 10, month_names[month])

        # Day headers
        day_headers = ['S', 'M', 'T', 'W', 'T', 'F', 'S']
        cell_width = width / 7
        cell_height = (height - 15) / 7  # 6 weeks max + header

        c.setFont("Helvetica", 6)
        c.setFillColor(self.GRAY)
        for i, day in enumerate(day_headers):
            c.drawCentredString(x + (i + 0.5) * cell_width, y + height - 22, day)

        # Get calendar data
        cal = calendar.Calendar(firstweekday=6)  # Sunday first
        month_days = cal.monthdayscalendar(year, month)

        c.setFont("Helvetica", 6)
        for week_num, week in enumerate(month_days):
            for day_num, day in enumerate(week):
                if day == 0:
                    continue

                cell_x = x + day_num * cell_width
                cell_y = y + height - 30 - (week_num * cell_height)

                # Check if this day is in our date range
                try:
                    day_date = date(year, month, day)
                    in_range = start_date <= day_date <= end_date
                except ValueError:
                    in_range = False

                if in_range:
                    # Highlight days in range with cyan background
                    c.setFillColor(self.CYAN)
                    c.rect(cell_x + 1, cell_y - 2, cell_width - 2, cell_height - 1, fill=1, stroke=0)
                    c.setFillColor(white)

                    # Add link to this day's schedule
                    date_str = day_date.strftime('%Y-%m-%d')
                    dest = f"day_{date_str}_schedule"
                    c.linkRect("", dest, (cell_x, cell_y - 2, cell_x + cell_width, cell_y + cell_height - 2), relative=0)
                else:
                    c.setFillColor(self.GRAY)

                c.drawCentredString(cell_x + cell_width / 2, cell_y, str(day))

        c.setFillColor(black)

    def _get_week_dates(self, current_date, start_date, end_date):
        """Get the week dates for the current date within the PDF range"""
        # Find Monday of current week
        days_since_monday = current_date.weekday()
        week_start = current_date - timedelta(days=days_since_monday)

        # Get all 7 days of the week
        week_dates = []
        for i in range(7):
            day = week_start + timedelta(days=i)
            # Check if this day exists in our PDF
            if start_date <= day <= end_date:
                week_dates.append(day)
            else:
                week_dates.append(None)

        return week_dates

    def _get_weeks_in_range(self, current_date, start_date, end_date):
        """Get the ISO week numbers present in the date range"""
        weeks = set()
        current = start_date
        while current <= end_date:
            weeks.add(current.isocalendar()[1])
            current += timedelta(days=1)

        # Get current week number
        current_week = current_date.isocalendar()[1]

        return sorted(weeks), current_week

    def _draw_page_header(self, c, current_date, active_tab, note_num=None):
        """Draw the top navigation tabs and date header"""
        y_pos = self.page_height - self.margin

        # Tab names and positions
        tabs = ['Schedule', 'Goals & To-Dos', 'Notes']
        tab_widths = [55, 85, 45]
        tab_x = self.margin

        for i, (tab, width) in enumerate(zip(tabs, tab_widths)):
            is_active = (tab == active_tab)

            # Draw tab text
            if is_active:
                c.setFillColor(self.CYAN)
                c.setFont("Helvetica-Bold", 10)
            else:
                c.setFillColor(self.GRAY)
                c.setFont("Helvetica", 10)

            c.drawString(tab_x, y_pos - 3, tab)

            # Draw underline for active tab
            if is_active:
                c.setStrokeColor(self.CYAN)
                c.setLineWidth(2)
                text_width = c.stringWidth(tab, "Helvetica-Bold", 10)
                c.line(tab_x, y_pos - 8, tab_x + text_width, y_pos - 8)
                c.setStrokeColor(black)
                c.setLineWidth(0.5)

            # Add link rectangle for tab navigation
            date_str = current_date.strftime('%Y-%m-%d')
            if tab == 'Schedule':
                dest = f"day_{date_str}_schedule"
            elif tab == 'Goals & To-Dos':
                dest = f"day_{date_str}_goals"
            else:  # Notes - link to notes page 1
                dest = f"day_{date_str}_notes_1"

            c.linkRect("", dest, (tab_x, y_pos - 12, tab_x + width, y_pos + 5), relative=0)

            tab_x += width + 8

        c.setFillColor(black)

        # Draw horizontal line under tabs
        y_pos -= 14
        c.setStrokeColor(self.LIGHT_GRAY)
        c.setLineWidth(0.5)
        c.line(self.margin, y_pos, self.page_width - self.margin - self.sidebar_width, y_pos)

        # Draw date header
        y_pos -= 20

        # Calendar icon (simple square with lines)
        icon_x = self.margin
        icon_size = 12
        c.setStrokeColor(black)
        c.setLineWidth(0.5)
        c.rect(icon_x, y_pos - 3, icon_size, icon_size)
        # Draw calendar lines inside
        c.line(icon_x, y_pos + 5, icon_x + icon_size, y_pos + 5)
        c.line(icon_x + 3, y_pos + 9, icon_x + 3, y_pos + 12)
        c.line(icon_x + 9, y_pos + 9, icon_x + 9, y_pos + 12)

        # Date text: "September 1"
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(black)
        month_day = current_date.strftime('%B %-d')
        c.drawString(icon_x + icon_size + 6, y_pos, month_day)

        # Day of week in cyan
        day_name = current_date.strftime('%A')
        month_day_width = c.stringWidth(month_day, "Helvetica-Bold", 14)
        c.setFillColor(self.CYAN)
        c.drawString(icon_x + icon_size + 6 + month_day_width + 10, y_pos, day_name)

        c.setFillColor(black)

        return y_pos - 15  # Return Y position for content start

    def _get_week_start_date(self, week_num, year, start_date, end_date):
        """Get the Monday of a given ISO week number that falls within our date range"""
        # Find January 4th of the year (always in week 1)
        jan4 = date(year, 1, 4)
        # Find the Monday of week 1
        week1_monday = jan4 - timedelta(days=jan4.weekday())
        # Calculate the Monday of the target week
        target_monday = week1_monday + timedelta(weeks=week_num - 1)

        # Return the first day of that week that's in our range
        for i in range(7):
            day = target_monday + timedelta(days=i)
            if start_date <= day <= end_date:
                return day
        return None

    def _draw_right_sidebar(self, c, current_date, week_dates, start_date, end_date):
        """Draw the right sidebar with navigation"""
        sidebar_x = self.page_width - self.margin - self.sidebar_width
        y_pos = self.page_height - self.margin

        # Get weeks in range
        weeks_in_range, current_week = self._get_weeks_in_range(current_date, start_date, end_date)

        # Sidebar items from top to bottom
        items = []

        # Year - links to year view page
        items.append(('year', str(current_date.year), False, None, f"year_{current_date.year}"))

        # Month (abbreviated) - links to year view page (user can pick a day there)
        items.append(('month', current_date.strftime('%b'), False, None, f"year_{current_date.year}"))

        # Week numbers - link to Monday of that week
        for week_num in weeks_in_range[:3]:  # Show up to 3 weeks
            week_start = self._get_week_start_date(week_num, current_date.year, start_date, end_date)
            items.append(('week', f'W{week_num}', week_num == current_week, week_start, None))

        # Days of week
        day_abbrevs = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
        current_dow = current_date.weekday()  # Monday = 0
        # Reorder to start with Sunday
        for i, abbrev in enumerate(day_abbrevs):
            dow = (i - 1) % 7  # Convert to Monday=0 format (Sun becomes 6)
            if i == 0:  # Sunday
                dow = 6
            else:
                dow = i - 1
            is_current = (dow == current_dow)
            # Find the date for this day of week
            link_date = week_dates[dow] if dow < len(week_dates) else None
            items.append(('day', abbrev, is_current, link_date, None))

        # Draw each item
        item_height = 28
        for item in items:
            item_type = item[0]
            text = item[1]
            is_highlighted = item[2] if len(item) > 2 else False
            link_date = item[3] if len(item) > 3 else None
            direct_dest = item[4] if len(item) > 4 else None

            # Draw background
            if is_highlighted:
                c.setFillColor(self.CYAN)
            else:
                c.setFillColor(self.BEIGE)

            c.rect(sidebar_x, y_pos - item_height, self.sidebar_width, item_height, fill=1, stroke=0)

            # Draw text
            if is_highlighted:
                c.setFillColor(white)
            else:
                c.setFillColor(black)

            c.setFont("Helvetica", 8)
            text_width = c.stringWidth(text, "Helvetica", 8)
            text_x = sidebar_x + (self.sidebar_width - text_width) / 2
            text_y = y_pos - item_height + (item_height - 8) / 2
            c.drawString(text_x, text_y, text)

            # Add link - either direct destination or date-based
            if direct_dest is not None:
                c.linkRect("", direct_dest, (sidebar_x, y_pos - item_height, sidebar_x + self.sidebar_width, y_pos), relative=0)
            elif link_date is not None:
                date_str = link_date.strftime('%Y-%m-%d')
                dest = f"day_{date_str}_schedule"
                c.linkRect("", dest, (sidebar_x, y_pos - item_height, sidebar_x + self.sidebar_width, y_pos), relative=0)

            y_pos -= item_height

        c.setFillColor(black)

    def draw_schedule_page(self, c, current_date, events, start_hour, end_hour, calendar_colors, week_dates, start_date, end_date):
        """Draw the Schedule page with time slots and events"""
        # Draw common elements
        content_y = self._draw_page_header(c, current_date, 'Schedule')
        self._draw_right_sidebar(c, current_date, week_dates, start_date, end_date)

        # Column headers
        c.setFont("Helvetica", 10)
        c.setFillColor(black)
        c.drawString(self.margin, content_y, "Time")
        c.drawString(self.margin + 45, content_y, "Schedule")

        content_y -= 8

        # Calculate dimensions
        time_column_width = 40
        schedule_x = self.margin + time_column_width
        schedule_width = self.content_width - time_column_width

        # Calculate row height based on number of hours
        num_hours = end_hour - start_hour + 1
        available_height = content_y - self.margin - 10
        row_height = available_height / num_hours

        # Draw time slots
        y_pos = content_y

        # Check for all-day events
        all_day_events = [e for e in events if isinstance(e['start'], date) and not isinstance(e['start'], datetime)]
        has_all_day = len(all_day_events) > 0

        if has_all_day:
            # Draw all-day section
            c.setFont("Helvetica-Bold", 8)
            c.drawString(self.margin, y_pos - 10, "All Day")

            # Draw all-day events
            self._draw_all_day_events(c, all_day_events, schedule_x, schedule_width,
                                     y_pos - row_height, row_height, calendar_colors)

            # Draw line
            c.setStrokeColor(self.LIGHT_GRAY)
            c.setLineWidth(0.5)
            y_pos -= row_height
            c.line(self.margin, y_pos, self.margin + self.content_width, y_pos)

        # Draw hourly time slots
        for hour in range(start_hour, end_hour + 1):
            # Format time
            if hour < 12:
                time_str = f"{hour} AM" if hour > 0 else "12 AM"
            elif hour == 12:
                time_str = "12 PM"
            else:
                time_str = f"{hour-12} PM"

            # Draw time label
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(black)
            c.drawString(self.margin, y_pos - 12, time_str)

            # Draw vertical separator line
            c.setStrokeColor(self.LIGHT_GRAY)
            c.setLineWidth(0.5)
            c.line(schedule_x - 5, y_pos, schedule_x - 5, y_pos - row_height)

            # Draw half-hour dotted line
            half_y = y_pos - (row_height / 2)
            c.setStrokeColor(lightgrey)
            c.setLineWidth(0.25)
            c.setDash(1, 2)
            c.line(schedule_x, half_y, self.margin + self.content_width, half_y)
            c.setDash()

            # Draw hour line
            c.setStrokeColor(self.LIGHT_GRAY)
            c.setLineWidth(0.5)
            y_pos -= row_height
            c.line(self.margin, y_pos, self.margin + self.content_width, y_pos)

        # Draw events
        self._draw_events(c, current_date, events, schedule_x, schedule_width,
                         row_height, start_hour, end_hour, has_all_day, calendar_colors, content_y)

    def draw_goals_todos_page(self, c, current_date, week_dates, start_date, end_date):
        """Draw the Goals & To-Dos page"""
        # Draw common elements
        content_y = self._draw_page_header(c, current_date, 'Goals & To-Dos')
        self._draw_right_sidebar(c, current_date, week_dates, start_date, end_date)

        # Goals section
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(black)
        c.drawString(self.margin, content_y, "Goals")

        content_y -= 5

        # Draw 3 goal lines with underlines
        goal_line_height = 32
        for i in range(3):
            content_y -= goal_line_height
            c.setStrokeColor(black)
            c.setLineWidth(0.5)
            c.line(self.margin, content_y, self.margin + self.content_width, content_y)

        content_y -= 15

        # To-Dos section
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(black)
        c.drawString(self.margin, content_y, "To-Dos")

        content_y -= 5

        # Calculate remaining space for checkboxes
        remaining_height = content_y - self.margin
        checkbox_size = 12
        checkbox_spacing = 28
        num_checkboxes = int(remaining_height / checkbox_spacing)

        # Draw checkbox lines
        for i in range(min(num_checkboxes, 13)):
            content_y -= checkbox_spacing

            # Draw checkbox
            c.setStrokeColor(black)
            c.setLineWidth(0.5)
            c.rect(self.margin, content_y, checkbox_size, checkbox_size)

            # Draw line for text
            line_x = self.margin + checkbox_size + 8
            c.line(line_x, content_y, self.margin + self.content_width, content_y)

    def draw_notes_page(self, c, current_date, note_num, week_dates, start_date, end_date):
        """Draw a Notes page with sub-tabs"""
        # Draw common elements
        content_y = self._draw_page_header(c, current_date, 'Notes')
        self._draw_right_sidebar(c, current_date, week_dates, start_date, end_date)

        # Notes label and sub-tabs
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(black)
        c.drawString(self.margin, content_y, "Notes")

        # Draw sub-tabs [1] [2] [3] [4] [5]
        tab_x = self.margin + 50
        tab_width = 20
        tab_height = 16
        date_str = current_date.strftime('%Y-%m-%d')

        for i in range(1, 6):
            is_active = (i == note_num)

            # Draw tab background
            if is_active:
                c.setFillColor(self.CYAN)
            else:
                c.setFillColor(white)

            c.setStrokeColor(black)
            c.setLineWidth(0.5)
            c.rect(tab_x, content_y - 4, tab_width, tab_height, fill=1, stroke=1)

            # Draw number
            if is_active:
                c.setFillColor(white)
            else:
                c.setFillColor(black)

            c.setFont("Helvetica-Bold", 10)
            num_width = c.stringWidth(str(i), "Helvetica-Bold", 10)
            c.drawString(tab_x + (tab_width - num_width) / 2, content_y, str(i))

            # Add link for tab
            dest = f"day_{date_str}_notes_{i}"
            c.linkRect("", dest, (tab_x, content_y - 4, tab_x + tab_width, content_y + tab_height - 4), relative=0)

            tab_x += tab_width + 4

        c.setFillColor(black)

        content_y -= 20

        # Calculate remaining space for lines
        remaining_height = content_y - self.margin
        line_spacing = 32
        num_lines = int(remaining_height / line_spacing)

        # Draw note lines
        for i in range(num_lines):
            content_y -= line_spacing
            c.setStrokeColor(black)
            c.setLineWidth(0.5)
            c.line(self.margin, content_y, self.margin + self.content_width, content_y)

    def _draw_events(self, c, current_date, events, x_start, width, hour_height, start_hour, end_hour, has_all_day, calendar_colors, grid_top):
        """Draw events as rounded boxes positioned by time"""
        if calendar_colors is None:
            calendar_colors = ['#4A4A4A']

        # Adjust grid top if there's an all-day section
        if has_all_day:
            grid_top -= hour_height

        # Group events by time slot to handle overlaps
        time_slots = {}

        for event in events:
            # Skip all-day events
            if not isinstance(event['start'], datetime):
                continue

            # Check if event overlaps with our displayed time window
            window_end = end_hour + 1
            if event['start'].hour >= window_end:
                continue

            if event['end'] and isinstance(event['end'], datetime):
                event_end_hour = event['end'].hour
                if event['end'].minute > 0:
                    event_end_hour += 1
                if event_end_hour <= start_hour:
                    continue

            event_hour = min(event['start'].hour, end_hour)
            if event_hour < start_hour:
                event_hour = start_hour

            if event_hour not in time_slots:
                time_slots[event_hour] = []
            time_slots[event_hour].append(event)

        # Draw events
        for hour, hour_events in time_slots.items():
            for i, event in enumerate(hour_events):
                event_minute = event['start'].minute
                hours_from_start = hour - start_hour + (event_minute / 60.0)
                event_top = grid_top - (hours_from_start * hour_height) - 1

                # Calculate duration and height
                duration_minutes = 60
                if event['end'] and isinstance(event['end'], datetime):
                    delta = event['end'] - event['start']
                    duration_minutes = delta.total_seconds() / 60

                    clip_time = event['start'].replace(hour=end_hour + 1, minute=15, second=0, microsecond=0)
                    if event['end'] > clip_time:
                        minutes_to_clip = (clip_time - event['start']).total_seconds() / 60
                        duration_minutes = min(duration_minutes, minutes_to_clip)

                duration_minutes = max(15, round(duration_minutes / 15) * 15)
                box_height = (duration_minutes / 60.0) * hour_height

                spacing = 1
                box_height = max(box_height - spacing, 8)
                box_y = event_top - box_height

                event_width = width - 5
                event_x = x_start

                if i > 0:
                    # Handle overlapping events
                    events_in_slot = len(hour_events)
                    event_width = (width - 10) / events_in_slot
                    event_x = x_start + (i * event_width)

                # Draw event box
                cal_index = event.get('calendar_index', 0)
                color = calendar_colors[cal_index] if cal_index < len(calendar_colors) else calendar_colors[0]
                self._draw_rounded_rect(c, event_x, box_y, event_width, box_height, radius=2, color=color)

                # Draw event text
                c.setFillColor(HexColor('#FFFFFF'))
                c.setFont("Helvetica-Bold", 8)

                line_height = 9
                padding = 3
                available_height = box_height - (2 * padding)
                max_lines = max(1, int(available_height / line_height))

                char_width = 4
                max_chars_per_line = int((event_width - 10) / char_width)

                event_text = event['title']
                lines = self._wrap_text(event_text, max_chars_per_line, max_lines)

                for j, line in enumerate(lines):
                    if j >= max_lines:
                        break

                    if len(lines) == 1:
                        text_y = box_y + (box_height / 2) - 3
                    else:
                        total_text_height = len(lines) * line_height
                        start_y = box_y + (box_height - total_text_height) / 2 + (len(lines) - 1) * line_height
                        text_y = start_y - (j * line_height)

                    c.drawString(event_x + 5, text_y, line)

                c.setFillColor(black)

    def _draw_all_day_events(self, c, all_day_events, x_start, width, y_bottom, row_height, calendar_colors):
        """Draw all-day events in the all-day section"""
        if calendar_colors is None:
            calendar_colors = ['#4A4A4A']

        for i, event in enumerate(all_day_events):
            event_width = width - 5
            event_x = x_start

            if i > 0:
                events_count = len(all_day_events)
                event_width = (width - 10) / events_count
                event_x = x_start + (i * event_width)

            box_height = row_height - 6
            box_y = y_bottom + 3

            cal_index = event.get('calendar_index', 0)
            color = calendar_colors[cal_index] if cal_index < len(calendar_colors) else calendar_colors[0]
            self._draw_rounded_rect(c, event_x, box_y, event_width, box_height, radius=2, color=color)

            c.setFillColor(HexColor('#FFFFFF'))
            c.setFont("Helvetica-Bold", 8)

            char_width = 4
            max_chars_per_line = int((event_width - 10) / char_width)
            max_lines = 2

            event_text = event['title']
            lines = self._wrap_text(event_text, max_chars_per_line, max_lines)

            line_height = 9
            for j, line in enumerate(lines):
                if j >= max_lines:
                    break

                if len(lines) == 1:
                    text_y = box_y + (box_height / 2) - 3
                else:
                    total_text_height = len(lines) * line_height
                    start_y = box_y + (box_height - total_text_height) / 2 + (len(lines) - 1) * line_height
                    text_y = start_y - (j * line_height)

                c.drawString(event_x + 5, text_y, line)

            c.setFillColor(black)

    def _draw_rounded_rect(self, c, x, y, width, height, radius=3, color='#4A4A4A'):
        """Draw a rounded rectangle"""
        c.setFillColor(HexColor(color))
        c.setStrokeColor(HexColor(color))
        c.roundRect(x, y, width, height, radius, fill=1, stroke=1)
        c.setFillColor(black)
        c.setStrokeColor(black)

    def _wrap_text(self, text, max_chars_per_line, max_lines):
        """Wrap text to fit within specified constraints"""
        if not text:
            return [""]

        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            if len(current_line + " " + word) > max_chars_per_line:
                if current_line:
                    lines.append(current_line.strip())
                    current_line = word
                else:
                    lines.append(word[:max_chars_per_line - 3] + "...")
                    current_line = ""

                if len(lines) >= max_lines:
                    break
            else:
                current_line += (" " + word) if current_line else word

        if current_line and len(lines) < max_lines:
            lines.append(current_line.strip())

        if len(lines) == max_lines and len(words) > len(" ".join(lines).split()):
            if lines:
                last_line = lines[-1]
                if len(last_line) > 3:
                    lines[-1] = last_line[:-3] + "..."

        return lines if lines else [""]
