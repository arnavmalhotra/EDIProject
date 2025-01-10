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
        "intl": "international",
        "womens": "women's",
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
    """Search for event dates using Google Search with improved selectors"""
    try:
        search_terms = [event_name, "date 2025"]
        full_query = ' '.join(search_terms)
        encoded_query = quote(full_query)
        url = f"https://www.google.com/search?q={encoded_query}"
        
        driver.get(url)
        time.sleep(random.uniform(3, 6))
        
        # Expanded selectors to catch more result types
        search_results = []
        
        # Featured snippet (expanded selectors)
        featured_selectors = [
            "div.kp-wholepage",
            "div[data-featured-snippet-id]",
            "div.V3FYCf",  # New Google featured snippet class
            "div.IZ6rdc"   # Alternative featured snippet class
        ]
        
        for selector in featured_selectors:
            try:
                featured = driver.find_element(By.CSS_SELECTOR, selector)
                featured_text = featured.text
                search_results.append(f"FEATURED_SNIPPET: {featured_text}")
                break
            except NoSuchElementException:
                continue
        
        # Main search results (expanded selectors)
        result_selectors = [
            "div.g",
            "div.MjjYud",  # New Google result container
            "div.kvH3mc"   # Alternative result container
        ]
        
        for selector in result_selectors:
            results = driver.find_elements(By.CSS_SELECTOR, selector)
            if results:
                for idx, result in enumerate(results[:5]):
                    try:
                        # Try multiple possible title/snippet selectors
                        title = None
                        for title_selector in ["h3", "div.vvjwJb", "div.yuRUbf"]:
                            try:
                                title_element = result.find_element(By.CSS_SELECTOR, title_selector)
                                title = title_element.text
                                break
                            except NoSuchElementException:
                                continue
                        
                        snippet = None
                        for snippet_selector in [".VwiC3b", ".yXK7lf", ".w8qArf"]:
                            try:
                                snippet_element = result.find_element(By.CSS_SELECTOR, snippet_selector)
                                snippet = snippet_element.text
                                break
                            except NoSuchElementException:
                                continue
                        
                        if title or snippet:
                            search_results.append(f"RESULT_{idx + 1}: {title or ''} {snippet or ''}")
                    except Exception as e:
                        logging.debug(f"Failed to extract result {idx + 1}: {e}")
                break
        
        if search_results:
            return {
                'results': "\n".join(search_results),
                'url': url
            }
        return None
        
    except Exception as e:
        logging.error(f"Error during search for {event_name}: {e}")
        return None

def get_dates_from_gemini(event_name, search_text):
    """Extract dates using Gemini API with improved date handling"""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = f"""
        Current datetime: {datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S %Z')}

        Task: Extract the 2025 date(s) for "{event_name}" from the following search results.

        Rules:
        1. For annual events that occur on fixed dates each year:
           - If 2024 dates are mentioned and it's clearly an annual event, extrapolate to 2025
           - Example: If "November 25 to December 10" is mentioned for 2024, use those same dates for 2025
        2. For events tied to specific calendar systems (e.g., Hindu, Islamic):
           - Use explicitly mentioned 2025 dates
           - If calculating dates based on calendar conversions, include them
        3. For international observances and UN days:
           - These typically occur on the same dates annually
           - Use the standard dates if they are well-established
        4. Format dates as: {{"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}}
        5. For single-day events, use the same date for both start and end
        6. For religious observances, use officially announced dates when available

        Verification:
        1. For annual events, confirm they follow a consistent pattern
        2. For religious/cultural events, verify dates against calendar systems
        3. For international days, check against official sources
        4. For multi-day events, ensure start_date comes before end_date

        Search results:
        {search_text}

        Return ONLY the JSON object with the dates, no other text.
        """

        response = model.generate_content(prompt)
        result = response.text.strip()
        result = result.replace('```json', '').replace('```', '').strip()
        
        dates = json.loads(result)
        
        # Validate and standardize dates
        if dates.get('start_date') or dates.get('end_date'):
            try:
                if dates.get('start_date'):
                    start = parser.parse(dates['start_date']).replace(tzinfo=pytz.UTC)
                    if start.year != 2025:
                        # For annual events, adjust to 2025
                        start = start.replace(year=2025)
                    dates['start_date'] = start.strftime('%Y-%m-%d')
                
                if dates.get('end_date'):
                    end = parser.parse(dates['end_date']).replace(tzinfo=pytz.UTC)
                    if end.year != 2025:
                        # For annual events, adjust to 2025
                        end = end.replace(year=2025)
                    dates['end_date'] = end.strftime('%Y-%m-%d')
            except Exception as parse_e:
                logging.error(f"Error parsing dates for event '{event_name}': {parse_e}")
                return {"start_date": None, "end_date": None}
        
        return dates
        
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
            search_data = search_event_with_selenium(driver, event_name, alternate_names)
            if not search_data:
                logging.info(f"No search results found for '{event_name}'.")
                results["failed_attempts"] += 1
                continue
            
            # Get dates from Gemini
            dates = get_dates_from_gemini(event_name, search_data['results'])
            
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
                    
                    # Update the event in MongoDB with the actual search URL
                    events_collection.update_one(
                        {"_id": event["_id"]},
                        {
                            "$set": update_dict,
                            "$addToSet": {"source_urls": search_data['url']}
                        }
                    )
                    
                    logging.info(f"✓ Updated '{event_name}': {dates['start_date']} to {dates['end_date']}")
                    logging.info(f"  Source URL: {search_data['url']}")
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