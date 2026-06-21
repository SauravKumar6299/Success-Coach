import os
import re
import heapq
import itertools
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import streamlit as st
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

load_dotenv()
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/calendar'
]

# Case-normalized severity ranks (higher = more urgent)
SEVERITY_RANK = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}

# Exact block durations per severity, in minutes
DURATION_MAP = {
    "Critical": 75,
    "High": 60,
    "Medium": 45,
    "Low": 35
}

# Emoji-independent, whitespace-tolerant recognizer for our own emergency events
EMERGENCY_TITLE_RE = re.compile(
    r"\[(Critical|High|Medium|Low)\]\s+Student Emergency Sync\s*\|\s*ID:\s*(.+)"
)

CALENDAR_ID = 'saurav.kumar@nxtwave.co.in'
WINDOW_DAYS = 30           # how far ahead we tear down + rebuild
PACK_DAY_LIMIT = 120       # safety cap on how many days we'll spread into
SAME_SEVERITY_CAP = 5      # max events/day when the day is a single severity
MIXED_SEVERITY_CAP = 2     # max events/day when the day mixes severities
WORKDAY_START_HOUR = 9     # daily anchor


def get_cal_service():
    creds_info = dict(st.secrets["google_creds"])
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return build('calendar', 'v3', credentials=creds)


def _normalize_severity(raw):
    sev = (raw or "Medium").strip().title()
    return sev if sev in DURATION_MAP else "Medium"


def add_to_calendar(roll_no, ai_extracted_data, start_day_offset=0):
    """
    Priority-queue rebuild of the emergency-sync schedule.

    Algorithm:
      1. Pull every event in the next WINDOW_DAYS days.
      2. Recognized emergency syncs -> pushed into a severity max-heap and
         deleted from the calendar (full tear-down). Non-emergency events are
         kept only as per-day "blocked" intervals so we never double-book over
         real appointments.
      3. The new incoming signal is pushed into the same heap.
      4. Pop the heap and re-pack day by day from 9 AM. Per-day capacity:
            - up to SAME_SEVERITY_CAP (5) if the day holds a single severity,
            - up to MIXED_SEVERITY_CAP (2) the moment two severities mix.
         Because the heap yields highest severity first, each day starts with
         its top severity; we keep taking that severity (up to 5), and only
         drop to the mixed cap of 2 once a lower severity would be added.

    Returns (ok, schedule_updates) where schedule_updates maps roll_no -> start ISO.
    Use it to rebuild your signal list (order it by the ISO timestamp).
    """
    try:
        service = get_cal_service()

        IST = timezone(timedelta(hours=5, minutes=30))
        now_local = datetime.now(IST)

        today0 = datetime(now_local.year, now_local.month, now_local.day, 0, 0, 0, tzinfo=IST)
        window_start = today0
        window_end = today0 + timedelta(days=WINDOW_DAYS)

        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=window_start.isoformat(),
            timeMax=window_end.isoformat(),
            singleEvents=True,
            orderBy='startTime',
            maxResults=2500
        ).execute()

        # tiebreaker so heapq never has to compare the payload dicts; also gives
        # FIFO ordering within a severity (lower counter pops first)
        counter = itertools.count()
        heap = []                      # entries: (-rank, seq, payload)
        blocked_by_day = defaultdict(list)   # date -> [(start_dt, end_dt), ...]
        to_delete = []                 # ids of recognized emergency events to remove

        def push(payload):
            rank = SEVERITY_RANK.get(payload['severity'], 2)
            heapq.heappush(heap, (-rank, next(counter), payload))

        # --- the new incoming signal goes into the heap too ---
        input_severity = _normalize_severity(ai_extracted_data.get("severity"))
        push({
            "roll_no": roll_no,
            "severity": input_severity,
            "signal_type": ai_extracted_data.get("signal_type", "Urgent Review"),
            "reason": ai_extracted_data.get("reason", "No details provided"),
        })

        # --- scan the window: emergencies -> heap+delete, others -> blocked ---
        for event in events_result.get('items', []):
            if event.get('status') == 'cancelled':
                continue

            start_str = event.get('start', {}).get('dateTime') or event.get('start', {}).get('date')
            end_str = event.get('end', {}).get('dateTime') or event.get('end', {}).get('date')
            if not start_str or not end_str:
                continue

            # skip all-day events entirely (don't let them consume work hours)
            if 'T' not in start_str:
                continue

            s_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00')).astimezone(IST)
            e_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00')).astimezone(IST)

            summary = event.get('summary', '')
            match = EMERGENCY_TITLE_RE.search(summary)

            if match:
                push({
                    "roll_no": match.group(2).strip(),
                    "severity": match.group(1).title(),
                    "signal_type": "Retrieved Sync",
                    "reason": event.get('description', ''),
                })
                to_delete.append(event['id'])
            else:
                blocked_by_day[s_dt.date()].append((s_dt, e_dt))

        # --- full tear-down of existing emergency syncs ---
        for eid in to_delete:
            try:
                service.events().delete(calendarId=CALENDAR_ID, eventId=eid).execute()
            except Exception as del_err:
                print(f"[teardown] failed to delete {eid}: {del_err}")

        # --- re-pack from the heap, day by day ---
        schedule_updates = {}
        start_date = (now_local + timedelta(days=start_day_offset)).date()
        day_index = 0

        while heap and day_index < PACK_DAY_LIMIT:
            date = start_date + timedelta(days=day_index)
            day_index += 1

            day_end = datetime(date.year, date.month, date.day, 23, 59, 59, tzinfo=IST)
            blocked = sorted(blocked_by_day.get(date, []))
            pointer = datetime(date.year, date.month, date.day, WORKDAY_START_HOUR, 0, 0, tzinfo=IST)

            # ----- decide this day's batch using the 2 / 5 rule -----
            lead_rank = heap[0][0]   # -rank of the current top severity
            batch = []
            while heap:
                top_rank = heap[0][0]
                if top_rank == lead_rank:
                    # still the day's lead severity -> single-severity day, cap 5
                    if len(batch) >= SAME_SEVERITY_CAP:
                        break
                    batch.append(heapq.heappop(heap))
                else:
                    # a lower severity would join -> day becomes mixed, cap 2
                    if len(batch) >= MIXED_SEVERITY_CAP:
                        break
                    batch.append(heapq.heappop(heap))

            # ----- place the batch, skipping over real appointments -----
            i = 0
            while i < len(batch):
                rank, seq, student = batch[i]
                severity = student['severity']
                duration_mins = DURATION_MAP.get(severity, 30)

                while True:
                    candidate_end = pointer + timedelta(minutes=duration_mins)
                    collision = False
                    for s_dt, e_dt in blocked:
                        if pointer < e_dt and candidate_end > s_dt:
                            pointer = e_dt
                            collision = True
                            break
                    if not collision:
                        break

                # if a slot runs past midnight, push this item and the rest of
                # the batch back onto the heap and end the day
                if candidate_end > day_end:
                    for j in range(i, len(batch)):
                        rk, _, st = batch[j]
                        heapq.heappush(heap, (rk, next(counter), st))
                    break

                start_iso = pointer.isoformat()
                end_iso = candidate_end.isoformat()

                event_title = f"🚨 [{severity}] Student Emergency Sync | ID: {student['roll_no']}"
                event_description = f"Signal Type: {student['signal_type']}\nReason: {student['reason']}"
                event_body = {
                    'summary': event_title,
                    'description': event_description,
                    'start': {'dateTime': start_iso, 'timeZone': 'Asia/Kolkata'},
                    'end': {'dateTime': end_iso, 'timeZone': 'Asia/Kolkata'},
                }

                service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()

                schedule_updates[student['roll_no']] = start_iso
                blocked.append((pointer, candidate_end))   # block our own slot for the rest of the day
                pointer = candidate_end
                i += 1

        if heap:
            leftover = [p['roll_no'] for _, _, p in heap]
            print(f"[pack] {len(leftover)} signals did not fit within {PACK_DAY_LIMIT} days: {leftover}")

        return True, schedule_updates

    except Exception as e:
        print(f"!!! add_to_calendar crashed: {e}")
        return False, str(e)


def remove_from_calendar(student_id):
    """Searches the calendar and deletes all meetings for a specific student."""
    try:
        service = get_cal_service()

        IST = timezone(timedelta(hours=5, minutes=30))
        now_local = datetime.now(IST)

        time_min = (now_local - timedelta(days=1)).isoformat()
        time_max = (now_local + timedelta(days=WINDOW_DAYS)).isoformat()

        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True
        ).execute()

        deleted_any = False
        match_string = f"ID: {student_id}"

        for event in events_result.get('items', []):
            summary = event.get('summary', '')
            description = event.get('description', '')
            if match_string in summary or match_string in description:
                service.events().delete(calendarId=CALENDAR_ID, eventId=event['id']).execute()
                deleted_any = True

        return deleted_any

    except Exception as e:
        print(f"Error deleting event: {e}")
        return False