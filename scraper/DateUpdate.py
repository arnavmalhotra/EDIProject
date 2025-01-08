#Add support for all the websites other than York, add images on the eventdetails page
import os
import re
import time
import pytz
import requests

from datetime import datetime, date
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pymongo import MongoClient
from typing import Dict, Optional, Tuple, List

# Load environment variables
load_dotenv()

# Initialize MongoDB connection
MONGO_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)
db = client.events_db
events_collection = db.events

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/91.0.4472.124 Safari/537.36'
    )
}

# Define source URL as a constant
YORK_URL = "https://registrar.yorku.ca/enrol/dates/religious-accommodation-resource-2024-2025"

def strip_parentheses(raw_name: str) -> str:
    """
    Remove parentheses (and their contents) plus trailing asterisks.
    E.g. "Shemini Atzeret (Jewish)*" -> "Shemini Atzeret"
    """
    name_no_parens = re.sub(r"\([^)]*\)", "", raw_name)
    name_no_star = re.sub(r"\*$", "", name_no_parens)
    return name_no_star.strip()

def parse_month_day_year(date_str: str) -> Optional[date]:
    """
    Attempt to parse a standard date like "Oct. 12, 2024".
    Returns a date or None if parsing fails.
    """
    possible_formats = [
        "%b. %d, %Y",  # e.g. "Oct. 12, 2024"
        "%b %d, %Y",    # e.g. "Oct 12, 2024"
        "%B %d, %Y"     # e.g. "October 12, 2024"
    ]
    for fmt in possible_formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt).date()
            return dt
        except ValueError:
            pass
    return None

def get_nth_weekday(year: int, month: int, weekday: int, nth: int) -> Optional[date]:
    """
    Return the date corresponding to the nth occurrence of a given weekday
    in a specific year-month.

    - weekday: Monday=0, Tuesday=1, ..., Sunday=6 (Python's .weekday() convention)
    - nth: 1 for first, 2 for second, 3 for third, 4 for fourth, etc.
    Returns None if impossible (e.g., "Fifth Monday in February" might not exist).
    """
    try:
        first_day = date(year, month, 1)
    except ValueError:
        return None  # invalid date

    # Day of week for the 1st of that month
    first_dow = first_day.weekday()  # Monday=0, Sunday=6
    # offset: how many days from day 1 to get to the desired weekday
    offset = (weekday - first_dow) % 7  # e.g., if first_dow=2, weekday=0 => offset=5
    day_num = 1 + offset + 7*(nth-1)

    try:
        result = date(year, month, day_num)
    except ValueError:
        return None
    return result

def parse_nth_weekday_pattern(raw_text: str) -> Optional[Tuple[date, date]]:
    """
    Attempt to parse something like: "Third Monday in January 2025"
    or "Fourth Saturday of November" (with or without a year).

    If no year is given, default to 2025 (arbitrary - adjust as needed).
    Returns (start_date, end_date) or None if we cannot parse.
    """
    # Regex capturing something like:
    # "Third Monday in January 2025" or
    # "Fourth Saturday of November"
    # group(1)=first/second/third/fourth, group(2)=weekday, group(3)=month, group(4)=year (optional)
    pattern = re.compile(r"\b(first|second|third|fourth)\s+"
                         r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+"
                         r"(?:in|of)\s+([A-Za-z]+)(?:\s+(\d{4}))?\b",
                         flags=re.IGNORECASE)
    match = pattern.search(raw_text)
    if not match:
        return None

    ordinal_str, weekday_str, month_str, year_str = match.groups()

    ordinal_map = {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4
    }
    weekday_map = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6
    }
    month_map = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12
    }

    nth = ordinal_map.get(ordinal_str.lower())
    wday = weekday_map.get(weekday_str.lower())
    month_num = month_map.get(month_str.lower())
    # If year is missing, default to 2025
    year = int(year_str) if year_str else 2025

    if not (nth and wday is not None and month_num):
        return None

    possible_date = get_nth_weekday(year, month_num, wday, nth)
    if not possible_date:
        return None

    # Single-day event => start_date == end_date
    return (possible_date, possible_date)

def parse_date_range(raw_text: str) -> Tuple[Optional[date], Optional[date]]:
    """
    Attempts to parse the date info from a string using multiple patterns:
      1) "Begins ... on Mar. 1, 2025 ... ends ... on Mar. 30, 2025"
      2) "From June 4, 2025 to June 9, 2025"
      3) "July 5, 2025 to July 6, 2025"
      4) Single date: "Oct. 12, 2024"
      5) Two single dates in the string
      6) "Third Monday in January 2025" (custom nth-weekday logic)
      7) If none matched => (None, None)
    """
    # 6) Check for "Third Monday in January" style patterns first
    nth_pattern_result = parse_nth_weekday_pattern(raw_text)
    if nth_pattern_result:
        return nth_pattern_result

    # 1) "Begins ... on Mar. 1, 2025 ... ends ... on Mar. 30, 2025"
    pattern_begins_ends = re.compile(
        r"[Bb]egins.*on\s+([A-Za-z]+\.*\s+\d{1,2},\s*\d{4}).*ends.*on\s+([A-Za-z]+\.*\s+\d{1,2},\s*\d{4})"
    )
    match = pattern_begins_ends.search(raw_text)
    if match:
        start_str, end_str = match.groups()
        start_dt = parse_month_day_year(start_str)
        end_dt   = parse_month_day_year(end_str)
        if start_dt and end_dt:
            return (start_dt, end_dt)

    # 2) "From June 4, 2025 to June 9, 2025"
    pattern_from_to = re.compile(
        r"[Ff]rom\s+([A-Za-z]+\.*\s+\d{1,2},\s*\d{4})\s+to\s+([A-Za-z]+\.*\s+\d{1,2},\s*\d{4})"
    )
    match = pattern_from_to.search(raw_text)
    if match:
        start_str, end_str = match.groups()
        start_dt = parse_month_day_year(start_str)
        end_dt   = parse_month_day_year(end_str)
        if start_dt and end_dt:
            return (start_dt, end_dt)

    # 3) "July 5, 2025 to July 6, 2025"
    pattern_simple_to = re.compile(
        r"([A-Za-z]+\.*\s+\d{1,2},\s*\d{4})\s+to\s+([A-Za-z]+\.*\s+\d{1,2},\s*\d{4})"
    )
    match = pattern_simple_to.search(raw_text)
    if match:
        start_str, end_str = match.groups()
        start_dt = parse_month_day_year(start_str)
        end_dt   = parse_month_day_year(end_str)
        if start_dt and end_dt:
            return (start_dt, end_dt)

    # 4) Single date e.g. "Oct. 12, 2024"
    pattern_single_date = re.compile(r"\b([A-Za-z]+\.*\s+\d{1,2},\s*\d{4})\b")
    single_dates = pattern_single_date.findall(raw_text)

    if len(single_dates) == 1:
        dt = parse_month_day_year(single_dates[0])
        if dt:
            return (dt, dt)

    # 5) Possibly 2 separate single-dates with no 'from/to':
    if len(single_dates) == 2:
        start_dt = parse_month_day_year(single_dates[0])
        end_dt   = parse_month_day_year(single_dates[1])
        if start_dt and end_dt:
            return (start_dt, end_dt)

    # 7) Could not parse
    return (None, None)

def scrape_york_accommodations() -> Dict[str, Tuple[Optional[date], Optional[date]]]:
    """
    Scrape the Religious Accommodation Resource (2024-2025) from York.
    Returns { stripped_event_name.lower() -> (start_date, end_date) }
    """
    accommodations = {}
    try:
        resp = requests.get(YORK_URL, headers=HEADERS)
        if resp.status_code != 200:
            print(f"[YORK] Failed to retrieve page (status {resp.status_code}).")
            return accommodations

        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table")
        if not table:
            print("[YORK] Could not find table on the page.")
            return accommodations

        tbody = table.find("tbody")
        if not tbody:
            print("[YORK] Could not find <tbody> in the table.")
            return accommodations

        rows = tbody.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 2:
                continue
            raw_name = cols[0].get_text(strip=True)
            raw_date_str = cols[1].get_text(strip=True)

            event_name_stripped = strip_parentheses(raw_name)
            start_dt, end_dt = parse_date_range(raw_date_str)
            accommodations[event_name_stripped.lower()] = (start_dt, end_dt)

    except Exception as e:
        print(f"[YORK] Error scraping accommodations: {e}")

    return accommodations

def update_event_dates():
    """
    1) Scrape York University data.
    2) For each event in DB, match name (stripped, lowercase) and alternate names:
       - Use York data if found.
    3) If found, parse & update. If not, skip.
    4) Summarize counts.
    """
    print("Scraping data from York University (primary) ...")
    york_dict = scrape_york_accommodations()

    print("\nStarting database update...")

    # Counters for summary
    total_events = 0
    updated_events = 0
    parse_failed = 0
    not_found = 0

    events = events_collection.find({})

    for event in events:
        total_events += 1
        db_raw_name = event.get("name", "").strip()
        alternate_names = event.get("alternate_names", [])
        # Prepare a list of all possible names: primary and alternate
        possible_names = [strip_parentheses(db_raw_name).lower()] + [strip_parentheses(name).lower() for name in alternate_names]

        print(f"\nChecking DB event: '{db_raw_name}' (Possible names: {possible_names})")

        # Initialize variables
        start_dt, end_dt = None, None
        source_url = None

        # 1) Check York: iterate through all possible names
        for name in possible_names:
            if name in york_dict:
                start_dt, end_dt = york_dict[name]
                source_url = YORK_URL
                print(f"   Found in York data using name: '{name}'")
                break  # Prefer first match in York

        # If not found in York, skip
        if start_dt is None and end_dt is None:
            print("   No match in York data.")
            not_found += 1
            continue

        # If the name was found but the date(s) could not be parsed => skip
        if not start_dt or not end_dt:
            print(f"   Could not parse dates for '{db_raw_name}'. Skipping update.")
            parse_failed += 1
            continue

        # Convert date -> datetime at midnight UTC
        start_date = datetime.combine(start_dt, datetime.min.time()).replace(tzinfo=pytz.utc)
        end_date = datetime.combine(end_dt, datetime.min.time()).replace(tzinfo=pytz.utc)

        try:
            update_fields = {
                "start_date": start_date,
                "end_date": end_date,
                "last_updated": datetime.now(pytz.utc)
            }

            # Update source_urls using $addToSet to avoid duplicates
            if source_url:
                events_collection.update_one(
                    {"_id": event["_id"]},
                    {
                        "$set": update_fields,
                        "$addToSet": {
                            "source_urls": source_url
                        }
                    }
                )
            else:
                events_collection.update_one(
                    {"_id": event["_id"]},
                    {
                        "$set": update_fields
                    }
                )

            print(f"   ✓ Updated '{db_raw_name}' with {start_dt} to {end_dt}")
            updated_events += 1
        except Exception as e:
            print(f"   ✗ Error updating DB: {e}")

        # Be nice to servers
        time.sleep(1)

    print("\n=== UPDATE SUMMARY ===")
    print(f"Total events processed: {total_events}")
    print(f"Events updated:        {updated_events}")
    print(f"Events not found:      {not_found}")
    print(f"Events parse failed:   {parse_failed}")

def main():
    """Main execution function."""
    try:
        print("Connected to MongoDB successfully")
        update_event_dates()
        print("\nDate update process completed successfully!")

    except Exception as e:
        print(f"\nError during update: {e}")

    finally:
        client.close()
        print("Database connection closed")

if __name__ == "__main__":
    main()
