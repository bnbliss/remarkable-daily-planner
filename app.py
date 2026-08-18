from flask import Flask, render_template, request, jsonify, send_file
from datetime import datetime, timedelta
import os
import json
from calendar_fetcher import CalendarFetcher
from pdf_generator import PDFGenerator
from google_calendar import GoogleCalendarHelper

import os

def _env(name: str) -> str:
    """Read a credential from the environment, falling back to .env.

    These used to be inline literals. GitHub push protection rejected the
    push, correctly -- a client secret in source is a secret in every clone
    and every backup.
    """
    v = os.environ.get(name)
    if v:
        return v
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    try:
        with open(p) as fh:
            for line in fh:
                k, _, val = line.partition('=')
                if k.strip() == name:
                    return val.strip()
    except OSError:
        pass
    raise RuntimeError(f'{name} not set -- add it to .env or the environment')


app = Flask(__name__)

# Google OAuth credentials
GOOGLE_CLIENT_ID = _env('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = _env('GOOGLE_CLIENT_SECRET')
google_helper = GoogleCalendarHelper(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/google/status')
def google_status():
    """Check if Google is authenticated."""
    return jsonify({'authenticated': google_helper.is_authenticated()})

@app.route('/google/auth')
def google_auth():
    """Get Google OAuth URL."""
    auth_url = google_helper.get_auth_url()
    return jsonify({'auth_url': auth_url})

@app.route('/google/callback', methods=['POST'])
def google_callback():
    """Complete OAuth with authorization code."""
    data = request.get_json()
    code = data.get('code', '').strip()
    if not code:
        return jsonify({'error': 'Authorization code required'}), 400

    try:
        google_helper.authenticate_with_code(code)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/google/calendars')
def google_calendars():
    """Get list of Google calendars."""
    if not google_helper.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401

    calendars = google_helper.get_calendars()
    return jsonify({'calendars': calendars})

@app.route('/google/disconnect', methods=['POST'])
def google_disconnect():
    """Disconnect Google account."""
    google_helper.disconnect()
    return jsonify({'success': True})

@app.route('/generate', methods=['POST'])
def generate_calendar():
    try:
        # get form data - collect calendar URLs and colors
        ical_urls = []
        calendar_colors = []
        i = 0
        while True:
            url = request.form.get(f'ical_url_{i}', '').strip()
            if not url and i > 0:
                break
            if url:
                ical_urls.append(url)
                color = request.form.get(f'color_{i}', '#4A4A4A')
                calendar_colors.append(color)
            i += 1
            if i > 20:  # safety limit
                break

        ical_urls_str = ','.join(ical_urls)

        # collect uploaded ICS files and their colors
        ics_files = []
        file_colors = []
        i = 0
        while True:
            file = request.files.get(f'ics_file_{i}')
            if not file and i > 0:
                break
            if file and file.filename:
                ics_content = file.read().decode('utf-8')
                ics_files.append(ics_content)
                color = request.form.get(f'file_color_{i}', '#2E86AB')
                file_colors.append(color)
            i += 1
            if i > 20:  # safety limit
                break

        # collect selected Google calendars and their colors
        google_calendars = []
        google_colors = []
        i = 0
        while True:
            cal_id = request.form.get(f'google_cal_{i}', '').strip()
            if not cal_id and i > 0:
                break
            if cal_id:
                google_calendars.append(cal_id)
                color = request.form.get(f'google_color_{i}', '#4285F4')
                google_colors.append(color)
            i += 1
            if i > 20:  # safety limit
                break

        start_date_str = request.form.get('start_date', '')
        end_date_str = request.form.get('end_date', '')
        start_hour = int(request.form.get('start_hour', 6))
        end_hour = int(request.form.get('end_hour', 17))

        # Get client timezone from browser
        timezone = request.form.get('timezone')

        if not timezone:
            return jsonify({'error': 'Timezone information is required. Please ensure JavaScript is enabled.'}), 400

        # validate inputs - need at least one source
        if not ical_urls and not ics_files and not google_calendars:
            return jsonify({'error': 'Please provide at least one calendar source'}), 400

        # validate time range (8-16 hours)
        duration = end_hour - start_hour
        if duration < 8:
            return jsonify({'error': 'Time range must be at least 8 hours'}), 400
        if duration > 16:
            return jsonify({'error': 'Time range cannot exceed 16 hours'}), 400

        # parse start date or default to next Monday
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            today = datetime.now().date()
            days_ahead = 0 - today.weekday()  # Monday is 0
            if days_ahead <= 0:
                days_ahead += 7
            start_date = today + timedelta(days=days_ahead)

        # parse end date or default to 7 days from start (minus 1 to make it inclusive)
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            end_date = start_date + timedelta(days=6)  # 7 days total (inclusive)

        # validate date range
        if end_date < start_date:
            return jsonify({'error': 'End date must be on or after start date'}), 400

        # fetch calendar events with timezone
        fetcher = CalendarFetcher(ical_urls_str, timezone)
        events = fetcher.fetch_events(start_date, end_date, ics_files, len(ical_urls))

        # fetch Google Calendar events
        google_event_count = len(ical_urls) + len(ics_files)
        for i, cal_id in enumerate(google_calendars):
            cal_index = google_event_count + i
            google_events = google_helper.get_calendar_events(cal_id, start_date, end_date, timezone)
            for g_event in google_events:
                parsed = fetcher.parse_google_event(g_event, cal_index)
                if parsed:
                    events.append(parsed)

        # combine colors: URL colors, then file colors, then Google colors
        all_colors = calendar_colors + file_colors + google_colors
        if not all_colors:
            all_colors = ['#4A4A4A']


        # generate filename based on date range
        if start_date == end_date:
            # single day: just month-day
            filename = f"{start_date.month}-{start_date.day}.pdf"
        else:
            # date range: month-day to month-day
            filename = f"{start_date.month}-{start_date.day}-to-{end_date.month}-{end_date.day}.pdf"
        output_path = os.path.join('output', filename)
        os.makedirs('output', exist_ok=True)

        generator = PDFGenerator()
        generator.generate_pdf(start_date, end_date, events, output_path, start_hour, end_hour, True, all_colors)

        # return the PDF file directly for download and remove from server
        try:
            response = send_file(output_path, as_attachment=True, download_name=filename)
            # delete the file after sending
            if os.path.exists(output_path):
                os.remove(output_path)
            return response
        except Exception as e:
            # clean up file if send fails
            if os.path.exists(output_path):
                os.remove(output_path)
            raise e

    except Exception as e:
        return jsonify({'error': 'An error occurred generating the calendar'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050)