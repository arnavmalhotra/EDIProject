import os
import re
import time
from datetime import datetime, date, timedelta
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pymongo import MongoClient
from typing import Dict, Optional, Tuple, List
from fuzzywuzzy import fuzz

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
ONTARIO_URL = "https://www.ontario.ca/page/ontarios-celebrations-and-commemorations"
XAVIER_URL = "https://www.xavier.edu/jesuitresource/online-resources/calendar-religious-holidays-and-observances/index"

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

def scrape_ontario_commemorative() -> Dict[str, Tuple[Optional[date], Optional[date]]]:
    """
    Scrape the Important and commemorative days from Ontario.ca.
    Returns { event_name.lower() -> (start_date, end_date) }
    """
    accommodations = {}
    
    try:
        resp = requests.get(ONTARIO_URL, headers=HEADERS)
        if resp.status_code != 200:
            print(f"[ONTARIO] Failed to retrieve page (status {resp.status_code}).")
            return accommodations

        soup = BeautifulSoup(resp.text, "html.parser")

        # The content is organized in columns by month
        month_columns = soup.find_all("div", class_="medium-4")
        current_year = 2025  # Default to 2025 for consistency

        for column in month_columns:
            # Find month headers (h3)
            month_headers = column.find_all("h3")
            
            for month_header in month_headers:
                month_name = month_header.text.strip()
                month_num = {
                    'January': 1, 'February': 2, 'March': 3, 'April': 4,
                    'May': 5, 'June': 6, 'July': 7, 'August': 8,
                    'September': 9, 'October': 10, 'November': 11, 'December': 12
                }.get(month_name)

                if not month_num:
                    continue

                # Get list of events for this month
                event_list = month_header.find_next("ul")
                if not event_list:
                    continue

                events = event_list.find_all("li")
                for event in events:
                    text = event.get_text(strip=True)
                    event_name = text.split('–')[0].strip()  # Get name before any date marker
                    
                    # Handle month-long events
                    if 'Month' in event_name or not any(char.isdigit() for char in text):
                        start_dt = date(current_year, month_num, 1)
                        if month_num == 12:
                            next_month = date(current_year + 1, 1, 1)
                        else:
                            next_month = date(current_year, month_num + 1, 1)
                        end_dt = next_month - timedelta(days=1)
                        accommodations[event_name.lower()] = (start_dt, end_dt)
                        continue
                    
                    # Handle specific dates and date ranges
                    date_part = text.split('–')[-1].strip()
                    
                    # Handle special date patterns
                    if 'third Monday' in date_part.lower():
                        third_monday = get_nth_weekday(current_year, month_num, 0, 3)
                        if third_monday:
                            accommodations[event_name.lower()] = (third_monday, third_monday)
                            continue

                    if 'fourth Saturday' in date_part.lower():
                        fourth_saturday = get_nth_weekday(current_year, month_num, 5, 4)
                        if fourth_saturday:
                            accommodations[event_name.lower()] = (fourth_saturday, fourth_saturday)
                            continue

                    # Handle specific dates
                    match = re.search(r'(\d{1,2})', date_part)
                    if match:
                        day = int(match.group(1))
                        try:
                            event_date = date(current_year, month_num, day)
                            accommodations[event_name.lower()] = (event_date, event_date)
                        except ValueError:
                            print(f"[ONTARIO] Invalid date: {month_name} {day}")
                            continue

    except Exception as e:
        print(f"[ONTARIO] Error scraping commemorative days: {e}")

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
        
        current_year = 2025  # Default to 2025 for consistency
        
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

def scrape_xavier_calendar() -> Dict[str, Tuple[Optional[date], Optional[date]]]:
    """
    Scrape the Religious Calendar from Xavier University.
    Returns { event_name.lower() -> (start_date, end_date) }
    """
    accommodations = {}
    
    try:
        resp = requests.get(XAVIER_URL, headers=HEADERS)
        if resp.status_code != 200:
            print(f"[XAVIER] Failed to retrieve page (status {resp.status_code}).")
            return accommodations

        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Find the main table containing the calendar
        table = soup.find("table", class_="table")
        if not table:
            print("[XAVIER] Could not find calendar table.")
            return accommodations

        current_month = None
        current_year = 2025  # Default for consistency with other scrapers
        
        # Process each row in the table
        rows = table.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if not cols:
                continue
                
            # Check if this is a month header row
            if len(cols[0].get_text(strip=True)) > 0 and len(cols) == 4:
                month_text = cols[0].get_text(strip=True)
                if month_text.lower() in ['january', 'february', 'march', 'april', 'may', 'june', 
                                        'july', 'august', 'september', 'october', 'november', 'december']:
                    current_month = {
                        'January': 1, 'February': 2, 'March': 3, 'April': 4,
                        'May': 5, 'June': 6, 'July': 7, 'August': 8,
                        'September': 9, 'October': 10, 'November': 11, 'December': 12
                    }[month_text]
                    continue

            # Process regular event rows
            if len(cols) >= 2:
                date_text = cols[0].get_text(strip=True)
                event_name = cols[1].get_text(strip=True)
                
                if not date_text or not event_name or current_month is None:
                    continue

                # Handle various date formats
                try:
                    # Handle date ranges like "16-17"
                    if "-" in date_text and not any(m in date_text.lower() for m in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                        start_day, end_day = map(int, date_text.split("-"))
                        start_dt = date(current_year, current_month, start_day)
                        end_dt = date(current_year, current_month, end_day)
                        
                    # Handle cross-month ranges like "Aug. 31-7"
                    elif "-" in date_text and any(m in date_text.lower() for m in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                        parts = date_text.replace(".", "").split("-")
                        if len(parts) == 2:
                            month_name = ''.join(c for c in parts[0] if not c.isdigit()).strip()
                            start_month = {
                                'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                                'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
                            }[month_name[:3]]
                            
                            start_day = int(''.join(c for c in parts[0] if c.isdigit()))
                            end_day = int(parts[1])
                            
                            start_dt = date(current_year, start_month, start_day)
                            end_dt = date(current_year, current_month, end_day)
                            
                    # Handle normal single dates
                    else:
                        day = int(''.join(c for c in date_text if c.isdigit()))
                        start_dt = date(current_year, current_month, day)
                        end_dt = start_dt

                    # Clean event name and store in dictionary
                    event_name = event_name.split("(")[0].strip()  # Remove any parenthetical notes
                    accommodations[event_name.lower()] = (start_dt, end_dt)

                except ValueError as e:
                    print(f"[XAVIER] Error parsing date '{date_text}' for event '{event_name}': {e}")
                    continue

    except Exception as e:
        print(f"[XAVIER] Error scraping calendar: {e}")
        
    return accommodations

def fetch_from_calendarific(event_name: str, api_key: str) -> Tuple[Optional[date], Optional[date]]:
    """
    Query the Calendarific API to find dates for an event.
    Returns (start_date, end_date) tuple or (None, None) if not found.
    """
    CALENDARIFIC_BASE_URL = "https://calendarific.com/api/v2/holidays"
    
    # Try both Canada and US as fallback sources
    countries = ["CA", "US"]
    year = 2025  # Current target year
    
    for country in countries:
        try:
            params = {
                "api_key": api_key,
                "country": country,
                "year": year,
            }
            
            response = requests.get(CALENDARIFIC_BASE_URL, params=params)
            if response.status_code != 200:
                print(f"[CALENDARIFIC] API error for {country}: {response.status_code}")
                continue
                
            data = response.json()
            if "response" not in data or "holidays" not in data["response"]:
                print(f"[CALENDARIFIC] Unexpected response format for {country}")
                continue
            
            # Search through holidays for matching name
            for holiday in data["response"]["holidays"]:
                api_name = holiday["name"].lower()
                if (event_name.lower() in api_name or 
                    api_name in event_name.lower() or
                    # Add fuzzy matching for similar names
                    fuzz.ratio(event_name.lower(), api_name) > 85):
                    
                    # Parse the ISO date from the API
                    try:
                        iso_date = holiday["date"]["iso"]
                        parsed_date = datetime.strptime(iso_date, "%Y-%m-%d").date()
                        # For single-day events, return same date for start and end
                        return (parsed_date, parsed_date)
                    except (KeyError, ValueError) as e:
                        print(f"[CALENDARIFIC] Date parsing error: {e}")
                        continue
            
            time.sleep(1)  # Rate limiting between country requests
            
        except Exception as e:
            print(f"[CALENDARIFIC] Error querying API for {country}: {e}")
            continue
    
    return (None, None)

def update_missing_events(not_found_events: List[Dict], api_key: str):
    """
    Update events that weren't found in primary sources using Calendarific API.
    """
    print("\nAttempting to update missing events using Calendarific API...")
    
    updated_count = 0
    
    for event in not_found_events:
        db_raw_name = event.get("name", "").strip()
        print(f"\nTrying Calendarific API for: '{db_raw_name}'")
        
        # Try with main name and alternates
        start_dt = end_dt = None
        for name in [db_raw_name] + event.get("alternate_names", []):
            start_dt, end_dt = fetch_from_calendarific(name, api_key)
            if start_dt and end_dt:
                print(f"   Found date via Calendarific: {start_dt} to {end_dt}")
                break
        
        if not start_dt or not end_dt:
            print(f"   Not found in Calendarific API")
            continue
            
        try:
            # Store dates as datetime objects at midnight
            start_date = datetime(start_dt.year, start_dt.month, start_dt.day)
            end_date = datetime(end_dt.year, end_dt.month, end_dt.day)
            
            # Update the database
            events_collection.update_one(
                {"_id": event["_id"]},
                {
                    "$set": {
                        "start_date": start_date,
                        "end_date": end_date,
                        "last_updated": datetime.now().replace(microsecond=0)
                    },
                    "$addToSet": {"source_urls": "https://calendarific.com/api/v2"}
                }
            )
            
            print(f"   ✓ Updated successfully")
            updated_count += 1
            
        except Exception as e:
            print(f"   ✗ Error updating database: {e}")
        
        time.sleep(1)  # Rate limiting between requests
    
    return updated_count
def fetch_from_apininjas(event_name: str, api_key: str) -> Tuple[Optional[date], Optional[date]]:
    """
    Query the API Ninjas Holiday API to find dates for an event.
    Returns (start_date, end_date) tuple or (None, None) if not found.
    """
    API_NINJAS_URL = "https://api.api-ninjas.com/v1/holidays"
    
    # Try both US and Canada
    countries = ["US", "CA"]
    year = 2025  # Current target year
    
    for country in countries:
        try:
            params = {
                "country": country,
                "year": year
            }
            
            headers = {
                'X-Api-Key': api_key
            }
            
            response = requests.get(API_NINJAS_URL, headers=headers, params=params)
            if response.status_code != 200:
                print(f"[API_NINJAS] API error for {country}: {response.status_code}")
                continue
                
            holidays = response.json()
            if not isinstance(holidays, list):
                print(f"[API_NINJAS] Unexpected response format for {country}")
                continue
            
            # Search through holidays for matching name
            for holiday in holidays:
                api_name = holiday.get("name", "").lower()
                if (event_name.lower() in api_name or 
                    api_name in event_name.lower() or
                    fuzz.ratio(event_name.lower(), api_name) > 85):
                    
                    try:
                        date_str = holiday.get("date")
                        if date_str:
                            parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                            # Also check the type of holiday to prioritize major holidays
                            holiday_type = holiday.get("type", "").lower()
                            if "public" in holiday_type or "major" in holiday_type:
                                return (parsed_date, parsed_date)
                            return (parsed_date, parsed_date)  # Return even if not major holiday
                    except ValueError as e:
                        print(f"[API_NINJAS] Date parsing error: {e}")
                        continue
            
            time.sleep(1)  # Rate limiting
            
        except Exception as e:
            print(f"[API_NINJAS] Error querying API for {country}: {e}")
            continue
    
    return (None, None)
def update_remaining_events(remaining_events: List[Dict], api_keys: Dict[str, str]) -> Dict[str, int]:
    """
    Update events using both APIs sequentially.
    Returns summary statistics for each API.
    """
    results = {
        "calendarific_updated": 0,
        "apininjas_updated": 0,
        "still_missing": 0
    }
    
    # Try Calendarific API first
    print("\nAttempting to update remaining events using Calendarific API...")
    calendarific_updated_events = set()
    
    for event in remaining_events:
        db_raw_name = event.get("name", "").strip()
        print(f"\nTrying Calendarific API for: '{db_raw_name}'")
        
        # Try with main name and alternates
        start_dt = end_dt = None
        for name in [db_raw_name] + event.get("alternate_names", []):
            start_dt, end_dt = fetch_from_calendarific(name, api_keys["calendarific"])
            if start_dt and end_dt:
                print(f"   Found date via Calendarific: {start_dt} to {end_dt}")
                try:
                    start_date = datetime(start_dt.year, start_dt.month, start_dt.day)
                    end_date = datetime(end_dt.year, end_dt.month, end_dt.day)
                    
                    events_collection.update_one(
                        {"_id": event["_id"]},
                        {
                            "$set": {
                                "start_date": start_date,
                                "end_date": end_date,
                                "last_updated": datetime.now().replace(microsecond=0)
                            },
                            "$addToSet": {"source_urls": "https://calendarific.com/api/v2"}
                        }
                    )
                    
                    print(f"   ✓ Updated successfully via Calendarific")
                    results["calendarific_updated"] += 1
                    calendarific_updated_events.add(event["_id"])
                    break
                    
                except Exception as e:
                    print(f"   ✗ Error updating database: {e}")
        
        time.sleep(1)  # Rate limiting
    
    # Try Abstract API for remaining events
    print("\nAttempting to update remaining events using API Ninjas...")
    events_for_apininjas = [e for e in remaining_events if e["_id"] not in calendarific_updated_events]
    
    for event in events_for_apininjas:
        db_raw_name = event.get("name", "").strip()
        print(f"\nTrying API Ninjas for: '{db_raw_name}'")
        
        # Try with main name and alternates
        start_dt = end_dt = None
        for name in [db_raw_name] + event.get("alternate_names", []):
            start_dt, end_dt = fetch_from_apininjas(name, api_keys["apininjas"])
            if start_dt and end_dt:
                print(f"   Found date via API Ninjas: {start_dt} to {end_dt}")
                try:
                    start_date = datetime(start_dt.year, start_dt.month, start_dt.day)
                    end_date = datetime(end_dt.year, end_dt.month, end_dt.day)
                    
                    events_collection.update_one(
                        {"_id": event["_id"]},
                        {
                            "$set": {
                                "start_date": start_date,
                                "end_date": end_date,
                                "last_updated": datetime.now().replace(microsecond=0)
                            },
                            "$addToSet": {"source_urls": "https://api.api-ninjas.com/v1/holidays"}
                        }
                    )
                    
                    print(f"   ✓ Updated successfully via API Ninjas")
                    results["apininjas_updated"] += 1
                    break
                    
                except Exception as e:
                    print(f"   ✗ Error updating database: {e}")
        
        time.sleep(1)  # Rate limiting
    
    # Calculate remaining missing events
    results["still_missing"] = len(remaining_events) - results["calendarific_updated"] - results["apininjas_updated"]
    
    return results

def update_event_dates(api_keys: Dict[str, str]):
    """
    Update event dates in the database from multiple sources including APIs.
    """
    print("Scraping data from York University (primary)...")
    york_dict = scrape_york_accommodations()

    print("\nScraping data from Canada.ca...")
    canada_dict = scrape_canada_commemorative()
    
    print("\nScraping data from Ontario.ca...")
    ontario_dict = scrape_ontario_commemorative()
    
    print("\nScraping data from Xavier University...")
    xavier_dict = scrape_xavier_calendar()

    print("\nStarting database update...")

    # Initialize statistics
    stats = {
        "total_events": 0,
        "updated_from_scraping": 0,
        "parse_failed": 0,
        "not_found": 0
    }

    # Get all events from database
    events = events_collection.find({})
    not_found_events = []

    # Process each event
    for event in events:
        stats["total_events"] += 1
        db_raw_name = event.get("name", "").strip()
        alternate_names = event.get("alternate_names", [])
        possible_names = [strip_parentheses(db_raw_name).lower()] + [
            strip_parentheses(name).lower() for name in alternate_names
        ]

        print(f"\nChecking DB event: '{db_raw_name}' (Possible names: {possible_names})")

        start_dt, end_dt = None, None
        source_url = None

        # Try sources in order of reliability: York -> Canada -> Ontario -> Xavier
        for name in possible_names:
            # Try York data first (most reliable)
            if name in york_dict:
                start_dt, end_dt = york_dict[name]
                source_url = YORK_URL
                print(f"   Found in York data using name: '{name}'")
                break
            
            # Try Canada.ca data second
            elif name in canada_dict:
                start_dt, end_dt = canada_dict[name]
                source_url = CANADA_URL
                print(f"   Found in Canada.ca data using name: '{name}'")
                break
            
            # Try Ontario.ca data third
            elif name in ontario_dict:
                start_dt, end_dt = ontario_dict[name]
                source_url = ONTARIO_URL
                print(f"   Found in Ontario.ca data using name: '{name}'")
                break
            
            # Try Xavier data last
            elif name in xavier_dict:
                start_dt, end_dt = xavier_dict[name]
                source_url = XAVIER_URL
                print(f"   Found in Xavier data using name: '{name}'")
                break

        # If no data found from any source
        if start_dt is None and end_dt is None:
            print("   No match found in any source.")
            stats["not_found"] += 1
            not_found_events.append(event)
            continue

        # If dates couldn't be parsed
        if not start_dt or not end_dt:
            print(f"   Could not parse dates for '{db_raw_name}'. Skipping update.")
            stats["parse_failed"] += 1
            continue

        # Update database with found dates
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
            stats["updated_from_scraping"] += 1

        except Exception as e:
            print(f"   ✗ Error updating DB: {e}")

        time.sleep(1)  # Rate limiting

    # Print scraping summary
    print("\n=== SCRAPING SUMMARY ===")
    print(f"Total events processed:  {stats['total_events']}")
    print(f"Updated from scraping:   {stats['updated_from_scraping']}")
    print(f"Parse failed:           {stats['parse_failed']}")
    print(f"Not found:             {stats['not_found']}")

    # Try APIs for events that weren't found through scraping
    if stats["not_found"] > 0:
        # Get list of events that still need dates
        events_to_update = list(events_collection.find(
            {
                "$or": [
                    {"start_date": {"$exists": False}},
                    {"end_date": {"$exists": False}},
                    {"last_updated": {"$exists": False}}
                ]
            }
        ))
        
        if events_to_update:
            # Try updating with APIs
            api_results = update_remaining_events(events_to_update, api_keys)
            
            # Print API update summary
            print("\n=== API UPDATE SUMMARY ===")
            print(f"Updated via Calendarific: {api_results['calendarific_updated']}")
            print(f"Updated via API Ninjas:   {api_results['apininjas_updated']}")
            print(f"Still missing:           {api_results['still_missing']}")
            
            # Print final results
            print("\n=== FINAL RESULTS ===")
            print(f"Total events:            {stats['total_events']}")
            print(f"Successfully updated:    {stats['updated_from_scraping'] + api_results['calendarific_updated'] + api_results['apininjas_updated']}")
            print(f"Still missing:           {api_results['still_missing']}")
            print(f"Parse failed:           {stats['parse_failed']}")

def main():
    """Main execution function."""
    # Get API keys from environment variables
    CALENDARIFIC_API_KEY = os.getenv('CALENDARIFIC_API_KEY')
    APININJAS_API_KEY = os.getenv('APININJAS_API_KEY')

    # Verify that API keys are available
    if not CALENDARIFIC_API_KEY or not APININJAS_API_KEY:
        print("Error: Missing API keys in environment variables.")
        print("Please ensure CALENDARIFIC_API_KEY and APININJAS_API_KEY are set in your .env file.")
        return

    API_KEYS = {
        "calendarific": CALENDARIFIC_API_KEY,
        "apininjas": APININJAS_API_KEY
    }

    
    try:
        print("Connected to MongoDB successfully")
        update_event_dates(API_KEYS)
        print("\nDate update process completed successfully!")

    except Exception as e:
        print(f"\nError during update: {e}")

    finally:
        client.close()
        print("Database connection closed")

if __name__ == "__main__":
    main()