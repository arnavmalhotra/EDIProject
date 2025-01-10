import os
import time
import random
import logging
from datetime import datetime
import pytz
from dateutil import parser
import json
from urllib.parse import quote
import google.generativeai as genai
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from pymongo import MongoClient
from dotenv import load_dotenv
import re
import unicodedata

# =========================
# Configuration and Setup
# =========================

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("script_debug.log"),
        logging.StreamHandler()
    ]
)

# Load environment variables
load_dotenv()

# Validate Environment Variables
MONGO_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not GEMINI_API_KEY:
    logging.error("Missing Gemini API key in environment variables")
    exit(1)

# Initialize MongoDB connection
try:
    client = MongoClient(MONGO_URI)
    db = client.events_db
    events_collection = db.events
    logging.info("Connected to MongoDB successfully.")
except Exception as e:
    logging.error(f"Failed to connect to MongoDB: {e}")
    exit(1)

# =========================
# Selenium Driver Setup
# =========================

def setup_selenium_driver(use_proxy=False):
    """Set up headless Chrome browser with optional proxy support"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Updated headless option
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                'AppleWebKit/537.36 (KHTML, like Gecko) '
                                'Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    if use_proxy:
        proxy_address = os.getenv('PROXY_ADDRESS')
        if proxy_address:
            chrome_options.add_argument(f'--proxy-server={proxy_address}')
            logging.info(f"Using proxy server: {proxy_address}")
        else:
            logging.warning("Proxy address not set in environment variables.")

    try:
        driver = webdriver.Chrome(options=chrome_options)
        # Additional settings to prevent detection
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined})
            """
        })
        logging.info("Selenium WebDriver initialized successfully.")
        return driver
    except Exception as e:
        logging.error(f"Error initializing Selenium WebDriver: {e}")
        exit(1)

# =========================
# Normalization Functions
# =========================

def normalize_event_name(name):
    """
    Normalize event names by:
    - Trimming whitespace
    - Converting to lowercase
    - Removing special characters except spaces
    - Normalizing Unicode characters
    - Replacing known synonyms
    """
    if not name:
        return ""

    # Trim whitespace
    name = name.strip()
    
    # Convert to lowercase
    name = name.lower()
    
    # Replace known synonyms
    synonyms = {
        "nye": "new year's eve",
        "valentine's": "valentines day",
        # Add more synonyms as needed
    }
    for key, value in synonyms.items():
        name = name.replace(key, value)
    
    # Remove special characters except spaces
    name = re.sub(r'[^a-z0-9\s]', '', name)
    
    # Normalize Unicode characters
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8')
    
    # Remove extra spaces
    name = re.sub(r'\s+', ' ', name)
    
    return name

# =========================
# Search Functionality
# =========================

def search_event_with_selenium(driver, event_name, alternate_names):
    """Search for event dates using Google Search with improved accuracy"""
    try:
        # Construct search terms
        search_terms = [f'"{event_name}"', event_name]
        
        words = event_name.split()
        if len(words) > 2:
            for i in range(len(words)-1):
                search_terms.append(f'"{words[i]} {words[i+1]}"')
        
        if alternate_names:
            for alt_name in alternate_names[:2]:
                search_terms.extend([f'"{alt_name}"', alt_name])
        
        # Date-related terms
        date_terms = [
            "2025 date",
            "2025 calendar",
            "2025 observed",
            "when is celebrated 2025",
            "official date 2025",
            "2025 festival",
            "2025 holiday",
            "2025"
        ]
        
        # Site restrictions
        site_terms = [
            'site:*.edu',
            'site:*.gov',
            'site:interfaith-calendar.org',
            'site:timeanddate.com',
            'site:officeholidays.com'
        ]
        
        # Combine search terms
        base_query = f"({' OR '.join(search_terms)}) AND ({' OR '.join(date_terms)})"
        site_query = f"({' OR '.join(site_terms)})"
        full_query = f"{base_query} {site_query} -wikipedia -pinterest"
        
        # URL encode the search query
        encoded_query = quote(full_query)
        url = f"https://www.google.com/search?q={encoded_query}"
        
        logging.debug(f"Constructed Search URL: {url}")
        
        driver.get(url)
        
        # Randomized delay to mimic human behavior
        delay = random.uniform(3, 6)
        logging.debug(f"Sleeping for {delay:.2f} seconds to mimic human behavior.")
        time.sleep(delay)
        
        # Capture screenshot for debugging
        screenshot_path = f"screenshots/{event_name.replace(' ', '_')}_search.png"
        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
        driver.save_screenshot(screenshot_path)
        logging.debug(f"Search results screenshot saved to {screenshot_path}")
        
        # Wait for search results
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.ID, "search"))
            )
        except TimeoutException:
            logging.warning(f"Search results did not load in time for event: {event_name}")
            return None
        
        # Extract search results
        search_results = []
        
        # Attempt to get featured snippet
        try:
            featured = driver.find_element(By.CSS_SELECTOR, "div.kp-wholepage")
            featured_text = featured.text
            search_results.append(f"FEATURED_SNIPPET: {featured_text}")
            logging.debug("Featured snippet extracted.")
        except NoSuchElementException:
            logging.debug("No featured snippet found.")
        
        # Attempt to get knowledge panel
        try:
            knowledge_panel = driver.find_element(By.CSS_SELECTOR, "div.kp-blk")
            knowledge_text = knowledge_panel.text
            search_results.append(f"KNOWLEDGE_PANEL: {knowledge_text}")
            logging.debug("Knowledge panel extracted.")
        except NoSuchElementException:
            logging.debug("No knowledge panel found.")
        
        # Extract main search results
        results = driver.find_elements(By.CSS_SELECTOR, "div.g")
        for idx, result in enumerate(results[:5]):  # Top 5 results
            try:
                title_element = result.find_element(By.TAG_NAME, "h3")
                snippet_element = result.find_element(By.CSS_SELECTOR, ".VwiC3b")
                title = title_element.text
                snippet = snippet_element.text
                search_results.append(f"RESULT_{idx + 1}: {title} {snippet}")
                logging.debug(f"Result {idx + 1} extracted.")
            except NoSuchElementException:
                logging.debug(f"Result {idx + 1} has missing elements; skipping.")
                continue
        
        if not search_results:
            logging.info(f"No search results found for event: {event_name}")
            return None
        
        combined_results = "\n".join(search_results)
        logging.debug(f"Combined Search Results: {combined_results}")
        return combined_results
    
    except Exception as e:
        logging.error(f"Error during search for {event_name}: {e}")
        return None

# =========================
# Gemini API Integration
# =========================

def get_dates_from_gemini(event_name, search_text):
    """Extract dates using Gemini API with improved accuracy"""
    try:
        # Configure Gemini
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")

        current_time = datetime.now(pytz.UTC)
        
        prompt = f"""
        Current datetime: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}

        Task: Extract the 2025 date(s) for "{event_name}" from the following search results.

        Rules:
        1. ONLY extract dates explicitly mentioned for 2025
        2. Prioritize dates from FEATURED_SNIPPET and KNOWLEDGE_PANEL
        3. If multiple 2025 dates are found, choose the primary celebration date
        4. If no 2025 dates are found but there are 2024 dates with clear annual patterns, extrapolate to 2025
        5. For annually recurring events, verify the day and month match historical patterns
        6. For religious observances that span multiple days, include both start and end dates
        7. Format dates exactly as: {{"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}}
        8. If unsure, return null dates: {{"start_date": null, "end_date": null}}
        9. For single-day events, use the same date for both start and end

        Verification steps:
        1. Check if the date is explicitly given for 2025
        2. If extrapolating from 2024, verify it's an annual event on the same date
        3. Confirm the dates are from reliable sources
        4. Check for consistency across multiple results
        5. Ensure dates follow logical patterns (start_date ≤ end_date)

        Search results:
        {search_text}

        Return ONLY the JSON object with the dates, no other text.
        """

        logging.debug(f"Gemini Prompt for '{event_name}': {prompt}")

        response = model.generate_content(prompt)
        result = response.text.strip()
        
        # Clean up the response
        result = result.replace('```json', '').replace('```', '').strip()
        
        logging.debug(f"Raw Gemini Response: {result}")
        
        # Parse and validate the JSON response
        dates = json.loads(result)
        
        # Additional validation
        if dates.get('start_date') or dates.get('end_date'):
            if dates.get('start_date') and dates.get('end_date'):
                try:
                    start = parser.parse(dates['start_date']).replace(tzinfo=pytz.UTC)
                    end = parser.parse(dates['end_date']).replace(tzinfo=pytz.UTC)
                    
                    # Validate date logic
                    if end < start:
                        logging.warning(f"End date {end} is before start date {start} for event: {event_name}")
                        return {"start_date": None, "end_date": None}
                        
                    # Validate year
                    if start.year != 2025 or end.year != 2025:
                        logging.warning(f"Dates not in 2025 (start: {start.year}, end: {end.year}) for event: {event_name}")
                        return {"start_date": None, "end_date": None}
                except Exception as parse_e:
                    logging.error(f"Error parsing dates for event '{event_name}': {parse_e}")
                    return {"start_date": None, "end_date": None}
            elif dates.get('start_date') and not dates.get('end_date'):
                try:
                    start = parser.parse(dates['start_date']).replace(tzinfo=pytz.UTC)
                    if start.year != 2025:
                        logging.warning(f"Start date not in 2025 (start: {start.year}) for event: {event_name}")
                        dates['start_date'] = None
                except Exception as parse_e:
                    logging.error(f"Error parsing start date for event '{event_name}': {parse_e}")
                    dates['start_date'] = None
            elif dates.get('end_date') and not dates.get('start_date'):
                try:
                    end = parser.parse(dates['end_date']).replace(tzinfo=pytz.UTC)
                    if end.year != 2025:
                        logging.warning(f"End date not in 2025 (end: {end.year}) for event: {event_name}")
                        dates['end_date'] = None
                except Exception as parse_e:
                    logging.error(f"Error parsing end date for event '{event_name}': {parse_e}")
                    dates['end_date'] = None
        
        logging.debug(f"Extracted Dates for '{event_name}': {dates}")
        return dates
        
    except json.JSONDecodeError:
        logging.error(f"Failed to parse JSON from Gemini response for event: {event_name}")
        return {"start_date": None, "end_date": None}
    except Exception as e:
        logging.error(f"Error getting dates from Gemini for {event_name}: {e}")
        return {"start_date": None, "end_date": None}

# =========================
# Update Functionality
# =========================

def update_missing_dates():
    """Update only events that are missing both start_date and end_date"""
    logging.info("Fetching events missing dates...")
    
    # Define the query to find events missing start_date or end_date
    missing_dates_query = {
        "$or": [
            {"start_date": {"$exists": False}},
            {"end_date": {"$exists": False}},
            {"start_date": None},
            {"end_date": None}
        ]
    }
    
    try:
        missing_events = list(events_collection.find(missing_dates_query))
        logging.info(f"Found {len(missing_events)} events missing dates.")
    except Exception as e:
        logging.error(f"Error querying MongoDB for missing dates: {e}")
        return
    
    if not missing_events:
        logging.info("No events need updating.")
        return
    
    results = {
        "total_attempted": len(missing_events),
        "successfully_updated": 0,
        "failed_attempts": 0
    }
    
    # Setup Chrome driver with optional proxy support
    driver = setup_selenium_driver(use_proxy=bool(os.getenv('PROXY_ADDRESS')))
    
    try:
        for event in missing_events:
            raw_event_name = event.get("name", "")
            event_name = normalize_event_name(raw_event_name)
            alternate_names = event.get("alternate_names", [])
            alternate_names = [normalize_event_name(name) for name in alternate_names]
            
            if not event_name:
                logging.warning(f"Event with ID {event.get('_id')} has no name after normalization. Skipping.")
                results["failed_attempts"] += 1
                continue
            
            logging.info(f"Processing: '{event_name}'")
            
            # Search Google using Selenium
            search_result = search_event_with_selenium(driver, event_name, alternate_names)
            if not search_result:
                logging.info(f"No search results found for '{event_name}'.")
                results["failed_attempts"] += 1
                continue
            
            # Get dates from Gemini
            dates = get_dates_from_gemini(event_name, search_result)
            
            if dates.get('start_date') or dates.get('end_date'):
                try:
                    update_dict = {
                        "last_updated": datetime.now(pytz.UTC)
                    }
                    
                    if dates.get('start_date'):
                        start_date = parser.parse(dates['start_date']).replace(tzinfo=pytz.UTC)
                        update_dict['start_date'] = start_date
                    if dates.get('end_date'):
                        end_date = parser.parse(dates['end_date']).replace(tzinfo=pytz.UTC)
                        update_dict['end_date'] = end_date
                    
                    # Update the event in MongoDB
                    events_collection.update_one(
                        {"_id": event["_id"]},
                        {
                            "$set": update_dict,
                            "$addToSet": {"source_urls": "selenium_gemini_search"}
                        }
                    )
                    
                    logging.info(f"✓ Updated '{event_name}': {dates['start_date']} to {dates['end_date']}")
                    results["successfully_updated"] += 1
                    
                except Exception as e:
                    logging.error(f"Error updating database for '{event_name}': {e}")
                    results["failed_attempts"] += 1
            else:
                logging.info(f"No valid dates found for '{event_name}'.")
                results["failed_attempts"] += 1
            
            # Randomized delay to prevent detection
            delay = random.uniform(2, 5)
            logging.debug(f"Sleeping for {delay:.2f} seconds before next request.")
            time.sleep(delay)
            
    finally:
        driver.quit()
        logging.info("Selenium WebDriver closed.")
    
    # Log final results
    success_rate = (results["successfully_updated"] / results["total_attempted"] * 100) if results["total_attempted"] else 0
    logging.info("\n=== UPDATE RESULTS ===")
    logging.info(f"Total events processed: {results['total_attempted']}")
    logging.info(f"Successfully updated:   {results['successfully_updated']}")
    logging.info(f"Failed attempts:       {results['failed_attempts']}")
    logging.info(f"Success rate:          {success_rate:.1f}%")
    
    return results

# =========================
# Main Execution Function
# =========================

def main():
    """Main execution function"""
    try:
        logging.info("Starting date update process...")
        results = update_missing_dates()
        logging.info("Update process completed!")
    except Exception as e:
        logging.error(f"Error during update process: {e}")
    finally:
        client.close()
        logging.info("Database connection closed.")

# =========================
# Entry Point
# =========================

if __name__ == "__main__":
    main()
