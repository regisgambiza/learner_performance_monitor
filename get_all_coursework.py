import logging
import pandas as pd

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

def get_all_coursework(service, course_id, start_date=None, end_date=None):
    coursework = []
    page_token = None
    while True:
        response = service.courses().courseWork().list(
            courseId=course_id, pageToken=page_token, pageSize=100
        ).execute()
        for cw in response.get("courseWork", []):
            created = cw.get("creationTime")  # e.g. "2025-09-28T10:30:00Z"
            if start_date or end_date:
                if created:
                    created_ts = pd.to_datetime(created)
                    if start_date and created_ts < pd.to_datetime(start_date, utc=True):
                        continue
                    if end_date and created_ts > pd.to_datetime(end_date, utc=True):
                        continue
            coursework.append(cw)
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return coursework