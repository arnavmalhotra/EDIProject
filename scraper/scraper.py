import google.generativeai as genai
import requests
import json
import re
import time
from datetime import date, datetime, timedelta
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
import pytz
import logging
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

class EventsDatabase:
    def __init__(self, connection_string="mongodb://localhost:27017/"):
        """Initialize MongoDB connection and setup database."""
        self.client = MongoClient(connection_string)
        self.db = self.client.events_db
        self.events = self.db.events
        self.scrape_history = self.db.scrape_history
        self._setup_indexes()
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            filename='events_scraper.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    def _setup_indexes(self):
        """Setup necessary indexes for efficient querying and data consistency."""
        # Event indexes
        self.events.create_index([("name", ASCENDING)])
        self.events.create_index([("start_date", ASCENDING)])
        self.events.create_index([("end_date", ASCENDING)])
        self.events.create_index([("start_date", ASCENDING), ("end_date", ASCENDING)])
        
        # Unique compound index for event identification
        self.events.create_index(
            [
                ("name", ASCENDING), 
                ("start_date", ASCENDING), 
                ("source_url", ASCENDING)
            ],
            unique=True
        )
    
    def record_scrape(self, source_url, success, events_count=0, error=None):
        """Record scraping attempt in history."""
        record = {
            "source_url": source_url,
            "scrape_date": datetime.now(pytz.utc),
            "success": success,
            "events_count": events_count,
            "error": str(error) if error else None
        }
        self.scrape_history.insert_one(record)
    
    def insert_events(self, events, source_url):
        """Insert or update events in MongoDB."""
        successful_updates = 0
        
        for event in events:
            try:
                # Parse dates
                start_date = datetime.strptime(event.get('Start Date'), '%d-%m-%y')
                end_date = datetime.strptime(event.get('End Date'), '%d-%m-%y')
                
                # Create document
                event_doc = {
                    "name": event.get('Name'),
                    "start_date": start_date,
                    "end_date": end_date,
                    "additional_details": event.get('Additional Details'),
                    "source_url": source_url,
                    "last_updated": datetime.now(pytz.utc)
                }
                
                # Update or insert the event
                result = self.events.update_one(
                    {
                        "name": event_doc["name"],
                        "start_date": event_doc["start_date"],
                        "source_url": source_url
                    },
                    {
                        "$set": event_doc,
                        "$setOnInsert": {"created_at": datetime.now(pytz.utc)}
                    },
                    upsert=True
                )
                
                if result.modified_count or result.upserted_id:
                    successful_updates += 1
                
            except Exception as e:
                logging.error(f"Error inserting event {event}: {e}")
        
        return successful_updates
    
    def get_all_events(self, sort_by="start_date"):
        """Get all events from the database."""
        return list(self.events.find().sort(sort_by, ASCENDING))
    
    def get_upcoming_events(self, days=30):
        """Get events occurring in the next X days."""
        start_date = datetime.now()
        end_date = start_date + timedelta(days=days)
        
        return list(self.events.find({
            "start_date": {"$gte": start_date},
            "end_date": {"$lte": end_date}
        }).sort("start_date", ASCENDING))
    
    def search_events(self, query=None, start_date=None, end_date=None, source_url=None):
        """Search events with flexible criteria."""
        search_filter = {}
        
        if query:
            search_filter["$or"] = [
                {"name": {"$regex": query, "$options": "i"}},
                {"additional_details": {"$regex": query, "$options": "i"}}
            ]
        
        if start_date:
            search_filter["start_date"] = {"$gte": start_date}
        if end_date:
            search_filter["end_date"] = {"$lte": end_date}
        if source_url:
            search_filter["source_url"] = source_url
            
        return list(self.events.find(search_filter).sort("start_date", ASCENDING))
    
    def get_events_by_year(self, year):
        """Get all events for a specific year."""
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31, 23, 59, 59)
        
        return list(self.events.find({
            "start_date": {"$gte": start_date},
            "end_date": {"$lte": end_date}
        }).sort("start_date", ASCENDING))
    
    def get_events_statistics(self):
        """Get statistics about the events in the database."""
        stats = {
            "total_events": self.events.count_documents({}),
            "sources": list(self.events.distinct("source_url")),
            "date_range": {
                "earliest": self.events.find_one({}, sort=[("start_date", ASCENDING)])["start_date"],
                "latest": self.events.find_one({}, sort=[("end_date", DESCENDING)])["end_date"]
            },
            "events_by_source": {}
        }
        
        for source in stats["sources"]:
            stats["events_by_source"][source] = self.events.count_documents({"source_url": source})
        
        return stats

def get_website_html(url):
    """Fetch HTML content from a URL."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching website {url}: {e}")
        return None

def clean_json_response(response_text):
    """Clean and parse JSON response from AI model."""
    cleaned_text = re.sub(r'```json\n', '', response_text)
    cleaned_text = re.sub(r'```', '', cleaned_text)
    
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON: {e}")
        return None

def scrape_events(urls, db_connection_string="mongodb://localhost:27017/"):
    """Main function to scrape events."""
    # Initialize database connection
    db = EventsDatabase(db_connection_string)
    
    # Configure Gemini AI
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    for url in urls:
        try:
            logging.info(f"Starting scrape for: {url}")
            
            # Fetch and process HTML
            html_content = get_website_html(url)
            if not html_content:
                db.record_scrape(url, False, error="Failed to fetch HTML")
                continue
            
            # Extract events
            response = model.generate_content(f"""
            Here is the HTML content from a webpage.
            Extract all the events along with their dates from the html and return only JSON code of the events.
            The JSON should be formatted as such:
                                              Name:
                                              Start Date: (Include the year for both start date and end date, it should be in the format DD-MM-YY, the current date is {date.today()})
                                              End Date: (The same as the start date in most cases, If the event is an entire month, the end date should be the last date of the month specified)
                                              Additional Details: (Null, if nothing is specified, otherwise return the specified details)
            Do not return anything other than the JSON code requested
            
            {html_content}
            """)
            print(response.text)
            events_data = clean_json_response(response.text)
            if not events_data:
                db.record_scrape(url, False, error="No events found")
                continue
            
            # Process events
            events_list = events_data if isinstance(events_data, list) else [events_data]
            updated_count = db.insert_events(events_list, url)
            
            # Record successful scrape
            db.record_scrape(url, True, events_count=updated_count)
            
            logging.info(f"Successfully processed {url}: {updated_count} events updated/added")
            
        except Exception as e:
            logging.error(f"Error processing {url}: {e}")
            db.record_scrape(url, False, error=str(e))
        
        time.sleep(2)  # Delay between requests
    
    db.client.close()

def main():
    """Main execution function."""
    # URLs to scrape
    urls = [
    "https://www.xavier.edu/jesuitresource/online-resources/calendar-religious-holidays-and-observances/index",
    "https://www.theinterfaithobserver.org/religious-calendar",
    ]
    
    # MongoDB connection string - modify as needed
    connection_string = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
    
    # Run the scraper
    scrape_events(urls, connection_string)
    
    # Print statistics after scraping
    db = EventsDatabase(connection_string)
    stats = db.get_events_statistics()
    
    print("\nScraping completed. Database statistics:")
    print(f"Total events: {stats['total_events']}")
    print("\nEvents by source:")
    for source, count in stats['events_by_source'].items():
        print(f"{source}: {count} events")
    print(f"\nDate range: {stats['date_range']['earliest']} to {stats['date_range']['latest']}")
    
    db.client.close()

if __name__ == "__main__":
    main()