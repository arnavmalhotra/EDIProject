import os
import re
import time
from datetime import datetime, date, timedelta
import requests
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

# Define source URLs as constants
YORK_URL = "https://registrar.yorku.ca/enrol/dates/religious-accommodation-resource-2024-2025"
CANADA_URL = "https://www.canada.ca/en/canadian-heritage/services/important-commemorative-days.html"

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
    Returns a date object (without time components) or None if parsing fails.
    """
    possible_formats = [
        "%b. %d, %Y",  # e.g. "Oct. 12, 2024"
        "%b %d, %Y",   # e.g. "Oct 12, 2024"
        "%B %d, %Y"    # e.g. "October 12, 2024"
    ]
    for fmt in possible_formats:
        try:
            parsed_date = datetime.strptime(date_str.strip(), fmt)
            # Return only the date component
            return date(parsed_date.year, parsed_date.month, parsed_date.day)
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
        return None

    first_dow = first_day.weekday()
    offset = (weekday - first_dow) % 7
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
    """
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
    Attempts to parse the date info from a string using multiple patterns.
    Returns tuple of date objects (without time components).
    """
    # Check for nth weekday patterns first
    nth_pattern_result = parse_nth_weekday_pattern(raw_text)
    if nth_pattern_result:
        return nth_pattern_result

    # "Begins ... on Mar. 1, 2025 ... ends ... on Mar. 30, 2025"
    pattern_begins_ends = re.compile(
        r"[Bb]egins.*on\s+([A-Za-z]+\.*\s+\d{1,2},\s*\d{4}).*ends.*on\s+([A-Za-z]+\.*\s+\d{1,2},\s*\d{4})"
    )
    match = pattern_begins_ends.search(raw_text)
    if match:
        start_str, end_str = match.groups()
        start_dt = parse_month_day_year(start_str)
        end_dt = parse_month_day_year(end_str)
        if start_dt and end_dt:
            return (start_dt, end_dt)

    # "From June 4, 2025 to June 9, 2025"
    pattern_from_to = re.compile(
        r"[Ff]rom\s+([A-Za-z]+\.*\s+\d{1,2},\s*\d{4})\s+to\s+([A-Za-z]+\.*\s+\d{1,2},\s*\d{4})"
    )
    match = pattern_from_to.search(raw_text)
    if match:
        start_str, end_str = match.groups()
        start_dt = parse_month_day_year(start_str)
        end_dt = parse_month_day_year(end_str)
        if start_dt and end_dt:
            return (start_dt, end_dt)

    # "July 5, 2025 to July 6, 2025"
    pattern_simple_to = re.compile(
        r"([A-Za-z]+\.*\s+\d{1,2},\s*\d{4})\s+to\s+([A-Za-z]+\.*\s+\d{1,2},\s*\d{4})"
    )
    match = pattern_simple_to.search(raw_text)
    if match:
        start_str, end_str = match.groups()
        start_dt = parse_month_day_year(start_str)
        end_dt = parse_month_day_year(end_str)
        if start_dt and end_dt:
            return (start_dt, end_dt)

    # Single date e.g. "Oct. 12, 2024"
    pattern_single_date = re.compile(r"\b([A-Za-z]+\.*\s+\d{1,2},\s*\d{4})\b")
    single_dates = pattern_single_date.findall(raw_text)

    if len(single_dates) == 1:
        dt = parse_month_day_year(single_dates[0])
        if dt:
            return (dt, dt)

    # Two separate single-dates with no 'from/to'
    if len(single_dates) == 2:
        start_dt = parse_month_day_year(single_dates[0])
        end_dt = parse_month_day_year(single_dates[1])
        if start_dt and end_dt:
            return (start_dt, end_dt)

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

def scrape_canada_commemorative() -> Dict[str, Tuple[Optional[date], Optional[date]]]:
    """
    Scrape the Important and commemorative days from Canada.ca.
    Returns { event_name.lower() -> (start_date, end_date) }
    """
    accommodations = {}
    
    try:
        resp = requests.get(CANADA_URL)
        if resp.status_code != 200:
            print(f"[CANADA] Failed to retrieve page (status {resp.status_code}).")
            return accommodations

        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Find all month sections (they're in columns)
        month_columns = soup.find_all("div", class_="col-md-4")
        
        current_year = 2025  # Default to 2025 for the academic year
        
        for column in month_columns:
            # Each column contains multiple month sections
            month_sections = column.find_all("h2")
            
            for month_section in month_sections:
                month_name = month_section.get_text(strip=True)
                month_num = {
                    'January': 1, 'February': 2, 'March': 3, 'April': 4,
                    'May': 5, 'June': 6, 'July': 7, 'August': 8,
                    'September': 9, 'October': 10, 'November': 11, 'December': 12
                }.get(month_name)
                
                if not month_num:
                    continue
                
                # Get the list of events for this month
                event_list = month_section.find_next("ul", class_="list-unstyled")
                if not event_list:
                    continue
                
                events = event_list.find_all("li", class_="mrgn-bttm-md")
                for event in events:
                    text = event.get_text(strip=True)
                    
                    # Handle month-long events (no specific date mentioned)
                    if not any(char.isdigit() for char in text):
                        # Create start and end dates for the whole month
                        start_dt = date(current_year, month_num, 1)
                        # Find last day of month
                        if month_num == 12:
                            next_month = date(current_year + 1, 1, 1)
                        else:
                            next_month = date(current_year, month_num + 1, 1)
                        end_dt = next_month - timedelta(days=1)
                        
                        # Extract event name (usually before any parentheses)
                        event_name = text.split('(')[0].strip()
                        accommodations[event_name.lower()] = (start_dt, end_dt)
                        continue
                    
                    # Handle specific dates
                    date_match = re.search(r'(\w+\s+\d{1,2})', text)
                    if date_match:
                        day_str = date_match.group(1)
                        try:
                            # Parse the specific date
                            day_dt = datetime.strptime(f"{day_str} {current_year}", "%B %d %Y").date()
                            # Extract event name (everything after the date)
                            name_parts = text.split(day_str)
                            if len(name_parts) > 1:
                                event_name = name_parts[1].split('(')[0].strip()
                                # Remove leading/trailing punctuation
                                event_name = re.sub(r'^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$', '', event_name)
                                accommodations[event_name.lower()] = (day_dt, day_dt)
                        except ValueError:
                            print(f"[CANADA] Could not parse date: {day_str}")
                            continue

    except Exception as e:
        print(f"[CANADA] Error scraping commemorative days: {e}")
        
    return accommodations

def update_event_dates():
    """
    Update event dates in the database from multiple sources.
    """
    print("Scraping data from York University (primary)...")
    york_dict = scrape_york_accommodations()

    print("\nScraping data from Canada.ca...")
    canada_dict = scrape_canada_commemorative()

    print("\nStarting database update...")

    total_events = 0
    updated_events = 0
    parse_failed = 0
    not_found = 0

    events = events_collection.find({})

    for event in events:
        total_events += 1
        db_raw_name = event.get("name", "").strip()
        alternate_names = event.get("alternate_names", [])
        possible_names = [strip_parentheses(db_raw_name).lower()] + [
            strip_parentheses(name).lower() for name in alternate_names
        ]

        print(f"\nChecking DB event: '{db_raw_name}' (Possible names: {possible_names})")

        start_dt, end_dt = None, None
        source_url = None

        # Try York data first
        for name in possible_names:
            if name in york_dict:
                start_dt, end_dt = york_dict[name]
                source_url = YORK_URL
                print(f"   Found in York data using name: '{name}'")
                break

        # If not found in York data, try Canada.ca data
        if start_dt is None and end_dt is None:
            for name in possible_names:
                if name in canada_dict:
                    start_dt, end_dt = canada_dict[name]
                    source_url = CANADA_URL
                    print(f"   Found in Canada.ca data using name: '{name}'")
                    break

        if start_dt is None and end_dt is None:
            print("   No match found in any source.")
            not_found += 1
            continue

        if not start_dt or not end_dt:
            print(f"   Could not parse dates for '{db_raw_name}'. Skipping update.")
            parse_failed += 1
            continue

        try:
            # Store dates as datetime objects at midnight (00:00:00)
            start_date = datetime(start_dt.year, start_dt.month, start_dt.day)
            end_date = datetime(end_dt.year, end_dt.month, end_dt.day)

            update_fields = {
                "start_date": start_date,
                "end_date": end_date,
                "last_updated": datetime.now().replace(microsecond=0)
            }

            if source_url:
                events_collection.update_one(
                    {"_id": event["_id"]},
                    {
                        "$set": update_fields,
                        "$addToSet": {"source_urls": source_url}
                    }
                )
            else:
                events_collection.update_one(
                    {"_id": event["_id"]},
                    {"$set": update_fields}
                )

            print(f"   ✓ Updated '{db_raw_name}' with {start_dt} to {end_dt}")
            updated_events += 1

        except Exception as e:
            print(f"   ✗ Error updating DB: {e}")

        time.sleep(1)  # Rate limiting

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