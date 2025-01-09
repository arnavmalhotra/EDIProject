import os
import time
from datetime import datetime
import pytz
from dateutil import parser
import json
import google.generativeai as genai
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize MongoDB connection
MONGO_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)
db = client.events_db
events_collection = db.events

def setup_selenium_driver():
    """Set up headless Chrome browser"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    return webdriver.Chrome(options=chrome_options)

def search_event_with_selenium(driver, event_name, alternate_names):
    """Search for event dates using Google Search with improved accuracy"""
    try:
        # Add main event name variations
        search_terms = []
        search_terms.append(f'"{event_name}"')  # Exact match
        search_terms.append(event_name)  # Non-exact match for flexibility
        
        # Add permutations of the main name
        words = event_name.split()
        if len(words) > 2:
            # Add combinations of adjacent words for better matching
            for i in range(len(words)-1):
                search_terms.append(f'"{words[i]} {words[i+1]}"')
        
        # Add alternate names if available
        if alternate_names:
            for alt_name in alternate_names[:2]:
                search_terms.append(f'"{alt_name}"')
                search_terms.append(alt_name)
        
        # Build search query with specific date-related terms
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
        
        # Add specific site searches for reliable sources
        site_terms = [
            'site:*.edu',
            'site:*.gov',
            'site:interfaith-calendar.org',
            'site:timeanddate.com',
            'site:officeholidays.com'
        ]
        
        # Combine search terms with date terms and site restrictions
        base_query = f"({' OR '.join(search_terms)}) ({' OR '.join(date_terms)})"
        site_query = f"({' OR '.join(site_terms)})"
        search_query = f"{base_query} {site_query} -wikipedia -pinterest"
        
        url = f"https://www.google.com/search?q={search_query}"
        driver.get(url)
        time.sleep(2)  # Wait for page to load
        
        # Wait for search results with increased timeout
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.ID, "search"))
            )
        except TimeoutException:
            # If regular search results don't load, try to get any visible content
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        
        # Get all relevant text content
        search_results = []
        
        # Try to get featured snippet first (highest priority)
        try:
            featured = driver.find_element(By.CLASS_NAME, "kp-wholepage")
            featured_text = featured.text
            search_results.append(f"FEATURED_SNIPPET: {featured_text}")
        except NoSuchElementException:
            pass
        
        # Get knowledge panel info (second priority)
        try:
            knowledge_panel = driver.find_element(By.CLASS_NAME, "kp-blk")
            knowledge_text = knowledge_panel.text
            search_results.append(f"KNOWLEDGE_PANEL: {knowledge_text}")
        except NoSuchElementException:
            pass
        
        # Get main search results
        results = driver.find_elements(By.CLASS_NAME, "g")
        for idx, result in enumerate(results[:5]):  # Look at top 5 results
            try:
                title = result.find_element(By.TAG_NAME, "h3").text
                snippet = result.find_element(By.CLASS_NAME, "VwiC3b").text
                search_results.append(f"RESULT_{idx + 1}: {title} {snippet}")
            except NoSuchElementException:
                continue
        
        return "\n".join(search_results)
        
    except Exception as e:
        print(f"Error searching for {event_name}: {str(e)}")
        return None

def get_dates_from_gemini(event_name, search_text):
    """Extract dates using Gemini API with improved accuracy"""
    try:
        # Configure Gemini
        GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
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

        response = model.generate_content(prompt)
        result = response.text.strip()
        
        # Clean up the response
        result = result.replace('```json', '').replace('```', '').strip()
        
        # Parse and validate the JSON response
        dates = json.loads(result)
        
        # Additional validation
        if dates['start_date'] and dates['end_date']:
            start = parser.parse(dates['start_date']).replace(tzinfo=pytz.UTC)
            end = parser.parse(dates['end_date']).replace(tzinfo=pytz.UTC)
            
            # Validate date logic
            if end < start:
                print(f"Warning: End date {end} is before start date {start}")
                return {"start_date": None, "end_date": None}
                
            # Validate year
            if start.year != 2025 or end.year != 2025:
                print(f"Warning: Dates not in 2025 (start: {start.year}, end: {end.year})")
                return {"start_date": None, "end_date": None}
        
        return dates
        
    except Exception as e:
        print(f"Error getting dates from Gemini for {event_name}: {str(e)}")
        return {"start_date": None, "end_date": None}

def update_missing_dates():
    """Update only events that are missing both start_date and end_date"""
    print("\nFetching events missing dates...")
    
    # Find events missing both start_date and end_date
    missing_dates_query = {
        "$or": [
            {"start_date": {"$exists": False}},
            {"end_date": {"$exists": False}},
            {"start_date": None},
            {"end_date": None}
        ]
    }
    
    missing_events = list(events_collection.find(missing_dates_query))
    print(f"Found {len(missing_events)} events missing dates")
    
    if not missing_events:
        print("No events need updating.")
        return
    
    results = {
        "total_attempted": len(missing_events),
        "successfully_updated": 0,
        "failed_attempts": 0
    }
    
    # Setup Chrome driver
    driver = setup_selenium_driver()
    
    try:
        for event in missing_events:
            event_name = event.get("name", "").strip()
            alternate_names = event.get("alternate_names", [])
            
            print(f"\nProcessing: '{event_name}'")
            
            # Search Google using Selenium
            search_result = search_event_with_selenium(driver, event_name, alternate_names)
            if not search_result:
                print(f"No search results found for {event_name}")
                results["failed_attempts"] += 1
                continue
            
            # Get dates from Gemini
            dates = get_dates_from_gemini(event_name, search_result)
            
            if dates['start_date'] or dates['end_date']:
                try:
                    update_dict = {
                        "last_updated": datetime.now(pytz.UTC)
                    }
                    
                    if dates['start_date']:
                        start_date = parser.parse(dates['start_date']).replace(tzinfo=pytz.UTC)
                        update_dict['start_date'] = start_date
                    if dates['end_date']:
                        end_date = parser.parse(dates['end_date']).replace(tzinfo=pytz.UTC)
                        update_dict['end_date'] = end_date
                    
                    events_collection.update_one(
                        {"_id": event["_id"]},
                        {
                            "$set": update_dict,
                            "$addToSet": {"source_urls": "selenium_gemini_search"}
                        }
                    )
                    
                    print(f"✓ Updated: {dates['start_date']} to {dates['end_date']}")
                    results["successfully_updated"] += 1
                    
                except Exception as e:
                    print(f"✗ Error updating database: {e}")
                    results["failed_attempts"] += 1
            else:
                print(f"No valid dates found for {event_name}")
                results["failed_attempts"] += 1
            
            time.sleep(2)  # Rate limiting
            
    finally:
        driver.quit()
    
    # Print final results
    print("\n=== UPDATE RESULTS ===")
    print(f"Total events processed: {results['total_attempted']}")
    print(f"Successfully updated:   {results['successfully_updated']}")
    print(f"Failed attempts:       {results['failed_attempts']}")
    print(f"Success rate:          {(results['successfully_updated'] / results['total_attempted'] * 100):.1f}%")
    
    return results

def main():
    """Main execution function"""
    try:
        # Verify API keys
        if not os.getenv('GEMINI_API_KEY'):
            print("Error: Missing Gemini API key in environment variables")
            return
            
        print("Starting date update process...")
        results = update_missing_dates()
        print("\nUpdate process completed!")
        
    except Exception as e:
        print(f"\nError during update process: {e}")
        
    finally:
        client.close()
        print("\nDatabase connection closed")

if __name__ == "__main__":
    main()