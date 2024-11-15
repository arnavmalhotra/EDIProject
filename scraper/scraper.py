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
from fuzzywuzzy import fuzz
from typing import Set, List, Dict, Any, Optional

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
        """Setup necessary indexes for efficient querying."""
        # Event indexes
        self.events.create_index([("name", ASCENDING)])
        self.events.create_index([("start_date", ASCENDING)])
        self.events.create_index([("end_date", ASCENDING)])
        self.events.create_index([("start_date", ASCENDING), ("end_date", ASCENDING)])

    def _get_cultural_terms(self) -> Set[str]:
        """Get set of cultural and ethnic terms."""
        return {
            'albanian', 'lebanese', 'hindu', 'sikh', 'islamic', 'jewish', 'christian',
            'buddhist', 'jain', 'armenian', 'korean', 'chinese', 'japanese', 'tibetan',
            'vietnamese', 'filipino', 'polish', 'german', 'irish', 'italian', 'french',
            'spanish', 'portuguese', 'greek', 'russian', 'ukrainian', 'indian', 'persian',
            'turkish', 'arab', 'african', 'latin', 'nordic', 'celtic', 'slavic', 'baltic',
            'mediterranean', 'scandinavian', 'asian', 'european', 'american', 'canadian',
            'mexican', 'brazilian', 'australian', 'egyptian', 'moroccan', 'thai', 'vietnamese',
            'indonesian', 'malaysian', 'mongolian', 'kazakh', 'uzbek', 'iranian', 'iraqi',
            'syrian', 'palestinian', 'israeli', 'saudi', 'yemeni', 'omani', 'emirati',
            'qatari', 'kuwaiti', 'bahraini'
        }

    def _normalize_event_name(self, name: str) -> str:
        """Normalize event names for comparison."""
        # Convert to lowercase and remove special characters
        normalized = re.sub(r'[^\w\s]', '', name.lower())
        
        # Get cultural terms
        cultural_terms = self._get_cultural_terms()
        
        # Remove common words that don't affect meaning
        stop_words = {
            'the', 'of', 'and', 'birth', 'day', 'feast', 'festival', 'celebration',
            'holiday', 'month', 'week', 'commemoration', 'anniversary', 'observance'
        }
        
        words = normalized.split()
        # Keep cultural terms even if they're part of stop words
        normalized = ' '.join(w for w in words if w not in stop_words or w in cultural_terms)
        
        return normalized

    def _is_month_long(self, event: Dict[str, Any]) -> bool:
        """Check if an event is a month-long observance."""
        start = event['start_date']
        end = event['end_date']
        return (
            start.day == 1 and
            end.month == start.month and
            end.year == start.year and
            end.day >= 28
        )

    def _are_similar_events(self, event1: Dict[str, Any], event2: Dict[str, Any], threshold: int = 85) -> bool:
        """Check if two events are similar based on name and date."""
        # Compare normalized names using fuzzy matching
        name1 = self._normalize_event_name(event1['name'])
        name2 = self._normalize_event_name(event2['name'])
        
        # Extract cultural terms from both names
        cultural_terms1 = set(word for word in name1.split() if word in self._get_cultural_terms())
        cultural_terms2 = set(word for word in name2.split() if word in self._get_cultural_terms())
        
        # If both events have cultural terms and they're different, they're not the same
        if cultural_terms1 and cultural_terms2 and cultural_terms1 != cultural_terms2:
            return False
        
        # Calculate name similarity
        name_similarity = fuzz.ratio(name1, name2)
        
        # Check if dates overlap
        date_overlap = (
            event1['start_date'] <= event2['end_date'] and
            event2['start_date'] <= event1['end_date']
        )
        
        # For month-long observances, be extra careful
        if self._is_month_long(event1) and self._is_month_long(event2):
            # Must have exact same month and year
            same_month = (
                event1['start_date'].month == event2['start_date'].month and
                event1['start_date'].year == event2['start_date'].year
            )
            return name_similarity >= threshold and same_month
        
        return name_similarity >= threshold and date_overlap

    def _merge_event_details(self, existing_event: Dict[str, Any], new_event: Dict[str, Any]) -> Dict[str, Any]:
        """Merge details from two similar events."""
        merged_details = []
        
        # Combine additional details if they exist and are different
        if existing_event.get('additional_details'):
            merged_details.append(existing_event['additional_details'])
        if new_event.get('additional_details'):
            if new_event['additional_details'] not in merged_details:
                merged_details.append(new_event['additional_details'])
        
        # Combine source URLs
        sources = set()
        if isinstance(existing_event['source_url'], list):
            sources.update(existing_event['source_url'])
        else:
            sources.add(existing_event['source_url'])
        
        if isinstance(new_event['source_url'], list):
            sources.update(new_event['source_url'])
        else:
            sources.add(new_event['source_url'])
        
        # Create merged event
        merged_event = {
            **existing_event,
            'additional_details': ' | '.join(merged_details) if merged_details else None,
            'source_url': list(sources),
            'alternate_names': list(set(
                existing_event.get('alternate_names', []) + 
                [existing_event['name'], new_event['name']]
            )),
            'last_updated': datetime.now(pytz.utc)
        }
        
        return merged_event
    
    def record_scrape(self, source_url: str, success: bool, events_count: int = 0, error: Optional[str] = None):
        """Record scraping attempt in history."""
        record = {
            "source_url": source_url,
            "scrape_date": datetime.now(pytz.utc),
            "success": success,
            "events_count": events_count,
            "error": str(error) if error else None
        }
        self.scrape_history.insert_one(record)
    
    def insert_events(self, events: List[Dict[str, Any]], source_url: str) -> int:
        """Insert or update events in MongoDB with duplicate detection."""
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
                
                # Look for similar existing events
                similar_events = self.events.find({
                    "start_date": {"$lte": end_date},
                    "end_date": {"$gte": start_date}
                })
                
                similar_found = False
                for existing_event in similar_events:
                    if self._are_similar_events(existing_event, event_doc):
                        # Merge the events
                        merged_event = self._merge_event_details(existing_event, event_doc)
                        
                        # Update the existing event with merged details
                        self.events.update_one(
                            {"_id": existing_event["_id"]},
                            {"$set": merged_event}
                        )
                        similar_found = True
                        successful_updates += 1
                        break
                
                # If no similar event found, insert as new
                if not similar_found:
                    result = self.events.update_one(
                        {
                            "name": event_doc["name"],
                            "start_date": event_doc["start_date"],
                            "source_url": source_url
                        },
                        {
                            "$set": event_doc,
                            "$setOnInsert": {
                                "created_at": datetime.now(pytz.utc),
                                "alternate_names": [event_doc["name"]]
                            }
                        },
                        upsert=True
                    )
                    
                    if result.modified_count or result.upserted_id:
                        successful_updates += 1
                
            except Exception as e:
                logging.error(f"Error inserting event {event}: {e}")
        
        return successful_updates

    def get_all_events(self, sort_by: str = "start_date") -> List[Dict[str, Any]]:
        """Get all events from the database."""
        return list(self.events.find().sort(sort_by, ASCENDING))

    def get_events_statistics(self) -> Dict[str, Any]:
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
            if isinstance(source, list):
                for s in source:
                    stats["events_by_source"][s] = self.events.count_documents(
                        {"source_url": {"$in": [s]}}
                    )
            else:
                stats["events_by_source"][source] = self.events.count_documents(
                    {"source_url": source}
                )
        
        return stats

def get_website_html(url: str) -> Optional[str]:
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

def clean_json_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Clean and parse JSON response from AI model."""
    cleaned_text = re.sub(r'```json\n', '', response_text)
    cleaned_text = re.sub(r'```', '', cleaned_text)
    
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON: {e}")
        return None

def scrape_events(urls: List[str], db_connection_string: str = "mongodb://localhost:27017/") -> None:
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
        "https://registrar.yorku.ca/enrol/dates/religious-accommodation-resource-2024-2025",
        "https://www.canada.ca/en/canadian-heritage/services/important-commemorative-days.html",
        "https://www.ontario.ca/page/ontarios-celebrations-and-commemorations",
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
    if 'date_range' in stats:
        print(f"\nDate range: {stats['date_range']['earliest']} to {stats['date_range']['latest']}")
    
    db.client.close()

if __name__ == "__main__":
    main()