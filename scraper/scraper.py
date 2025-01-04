#MAKE CHANGES TO ENSURE ACCURACY OF CONTENT IN EVENTDETAILS PAGE AND REMOVE DUPLICATES FROM THE DATABASE
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
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables
load_dotenv()

class EventDefinitions:
    """Class to maintain the list of events we want to track."""
    
    # Your existing EVENTS_BY_CATEGORY dictionary here
    EVENTS_BY_CATEGORY = {
        "Christianity": [
            "Epiphany", "Theophany", "Christmas", "Shrove Tuesday", "Ash Wednesday",
            "Palm Sunday", "Good Friday", "Easter", "All Saints Day",
            "Advent", "Ascension", "Pentecost"
        ],
        "Buddhism": [
            "Mahāyāna New Year", "Lunar New Year", "Nirvana Day", "Magha Puja",
            "Festival of Higan-e", "Spring Ohigan", "Saka New Year", "Theravāda New Year",
            "Wesak", "Asalha Puja", "Vassa", "Festival of Ksitigarbha", "Pavarana Day",
            "Bodhi Day"
        ],
        "Hinduism": [
            "Makar Sankranti", "Vasanta Panchami", "Mahashivaratri", "Holi",
            "Navvarsha", "Ramanavami", "Hanuman Jayanti", "Raksha Bandhan",
            "Sri Krishna Jayanti", "Ganesh Chaturthi", "Navaratri", "Dassehra",
            "Diwali", "Vikram New Year"
        ],
        "Islam": [
            "Laylat al-Mi'rāj", "Laylat al Baraat", "Ramadan", "Laylat al-Qadr",
            "ʻĪd al-Fiṭr", "ʻĪd al-'Aḍḥá", "Day of Ḥajj", "Islamic New Year",
            "Āshūrā", "Mawlid al-Nabīy", "Birth Date of the Aga Khan", "Arbaeen"
        ],
        "Sikhism": [
            "Lohri", "Birth Date of Guru Gobind Singh Ji", "Hola Mohalla",
            "Vaisakhi", "Martyrdom of Guru Arjan Dev Ji",
            "Installation of the Sri Guru Granth Sahib Ji", "Bandhi Chhor Divas",
            "Birth Date of Guru Nanak Dev Ji", "Martyrdom of Guru Tegh Bahadur Ji"
        ],
        "National Commemorative Days": [
            "Sir John A. Macdonald Day", "National Flag of Canada Day",
            "Commonwealth Day", "Victoria Day", "Saint-Jean-Baptiste Day",
            "Canada Day", "Emancipation Day", "Persons Day",
            "Indigenous Veterans Day", "Remembrance Day"
        ],
        "Additional Observances": [
            "Mid-Autumn Festival", "Chinese New Year", "Pride Weekend",
            "Thanksgiving", "Nowruz", "Le Réveillon de Noël", "Yalda",
            "4shanbe Souri", "Midsummer", "Lucia", "Labour Day",
            "National Indigenous Peoples Day", "National Day for Truth and Reconciliation",
            "National Day for Remembrance and Action on Violence Against Women",
            "St. Patrick's Day", "Family Day"
        ]
    }

    # Your existing ALTERNATE_NAMES dictionary here
    ALTERNATE_NAMES = {
        "Christmas": ["Christmas Day", "Christmas Eve", "Nativity of Jesus", "Nativity of the Lord"],
        "Easter": ["Easter Sunday", "Easter Day", "Resurrection Sunday", "Paschal Sunday"],
        "Lunar New Year": ["Chinese New Year", "Spring Festival", "Tết"],
        "Wesak": ["Vesak", "Buddha Day", "Buddha Purnima", "Buddha Jayanti"],
        "Diwali": ["Deepavali", "Festival of Lights", "Deepawali"],
        "ʻĪd al-Fiṭr": ["Eid ul-Fitr", "Eid al-Fitr", "Ramadan Eid", "Lesser Eid"],
        "ʻĪd al-'Aḍḥá": ["Eid ul-Adha", "Eid al-Adha", "Bakrid", "Greater Eid"],
        "Vaisakhi": ["Baisakhi", "Vaisakhdi", "Khalsa Day"],
        "Nowruz": ["Norooz", "Persian New Year", "Iranian New Year"],
        "Mahashivaratri": ["Maha Shivaratri", "Great Night of Shiva"],
        "Sri Krishna Jayanti": ["Janmashtami", "Krishna Janmashtami", "Gokulashtami"],
        "Ganesh Chaturthi": ["Vinayaka Chaturthi", "Ganeshotsav"],
        "Navaratri": ["Navratri", "Durga Puja", "Dussehra"],
        "Ramadan": ["Ramazan", "Ramzan", "Month of Fasting"],
        "Islamic New Year": ["Hijri New Year", "Arabic New Year", "Muharram"],
        "Āshūrā": ["Ashura", "Yawm Ashura", "Day of Ashura"],
        "Mawlid al-Nabīy": ["Mawlid", "Milad un Nabi", "Prophet's Birthday"],
        "Mid-Autumn Festival": ["Moon Festival", "Mooncake Festival"],
        "National Day for Truth and Reconciliation": ["Orange Shirt Day"],
        "Family Day": ["Ontario Family Day", "Provincial Family Day"]
    }

    @classmethod
    def get_all_events(cls) -> Set[str]:
        """Get a set of all event names we want to track."""
        events = {
            event for events in cls.EVENTS_BY_CATEGORY.values() 
            for event in events
        }
        for main_name, alternates in cls.ALTERNATE_NAMES.items():
            events.add(main_name)
            events.update(alternates)
        return events

    @classmethod
    def get_event_category(cls, event_name: str) -> Optional[str]:
        normalized_name = cls.normalize_event_name(event_name)
        for category, events in cls.EVENTS_BY_CATEGORY.items():
            if normalized_name in events:
                return category
            if any(fuzz.ratio(normalized_name.lower(), e.lower()) > 85 for e in events):
                return category
        return None

    @classmethod
    def normalize_event_name(cls, name: str) -> str:
        name = name.strip()
        for main_name, alternates in cls.ALTERNATE_NAMES.items():
            if name.lower() == main_name.lower() or name.lower() in [alt.lower() for alt in alternates]:
                return main_name

        best_match = None
        highest_ratio = 0
        for main_name, alternates in cls.ALTERNATE_NAMES.items():
            ratio = fuzz.ratio(name.lower(), main_name.lower())
            if ratio > highest_ratio and ratio > 85:
                highest_ratio = ratio
                best_match = main_name
            
            for alt in alternates:
                ratio = fuzz.ratio(name.lower(), alt.lower())
                if ratio > highest_ratio and ratio > 85:
                    highest_ratio = ratio
                    best_match = main_name
        
        return best_match if best_match else name

def generate_additional_information(event_name: str, model: Any) -> Dict[str, str]:
    """Generate additional information about an event using Gemini."""
    prompt = f"""
    Generate detailed information about the event: {event_name}
    
    Provide the information in JSON format with these exact fields:
    {{
        "historical_background": "Brief history and origin of the event (2-3 sentences)",
        "significance": "Cultural and social significance (2-3 sentences)",
        "observance_details": "How the event is traditionally observed (2-3 sentences)",
        "modern_celebration": "How it's celebrated in modern times (2-3 sentences)",
        "impact_and_legacy": "Impact on society and lasting legacy (2-3 sentences)"
    }}
    
    Keep each section concise but informative. Return only the JSON object, no additional text.
    """
    
    try:
        response = model.generate_content(prompt)
        additional_info = clean_json_response(response.text)
        time.sleep(1)  # Rate limiting
        return additional_info if additional_info else {}
    except Exception as e:
        logging.error(f"Error generating additional information for {event_name}: {e}")
        return {}

class EventsDatabase:
    def __init__(self, connection_string="mongodb://localhost:27017/"):
        self.client = MongoClient(connection_string)
        self.db = self.client.events_db
        self.events = self.db.events
        self.scrape_history = self.db.scrape_history
        self.tracked_events = EventDefinitions.get_all_events()
        self._setup_indexes()
        self._setup_logging()

    def _setup_logging(self):
        logging.basicConfig(
            filename='events_scraper.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def _setup_indexes(self):
        self.events.create_index([("name", ASCENDING)])
        self.events.create_index([("category", ASCENDING)])
        self.events.create_index([("start_date", ASCENDING)])
        self.events.create_index([("end_date", ASCENDING)])
        self.events.create_index([("source_urls", ASCENDING)])
        self.events.create_index([("last_updated", ASCENDING)])

    def record_scrape(self, source_url: str, success: bool, events_count: int = 0, error: Optional[str] = None):
        record = {
            "source_url": source_url,
            "scrape_date": datetime.now(pytz.utc),
            "success": success,
            "events_count": events_count,
            "error": str(error) if error else None
        }
        self.scrape_history.insert_one(record)

    def insert_events(self, events: List[Dict[str, Any]], source_url: str, model: Any = None) -> int:
        """Insert or update events in MongoDB with optional additional information."""
        successful_updates = 0
        
        for event in events:
            try:
                if not self._is_tracked_event(event.get('Name')):
                    logging.info(f"Skipping untracked event: {event.get('Name')}")
                    continue
                
                try:
                    start_date = datetime.strptime(event.get('Start Date'), '%d-%m-%y')
                    end_date = datetime.strptime(event.get('End Date'), '%d-%m-%y')
                except ValueError as e:
                    logging.error(f"Date parsing error for event {event.get('Name')}: {e}")
                    continue
                
                normalized_name = EventDefinitions.normalize_event_name(event.get('Name'))
                category = EventDefinitions.get_event_category(normalized_name)
                
                if not category:
                    logging.warning(f"Could not determine category for event: {normalized_name}")
                    continue

                # Create base document
                event_doc = {
                    "name": normalized_name,
                    "category": category,
                    "start_date": start_date,
                    "end_date": end_date,
                    "additional_details": event.get('Additional Details'),
                    "last_updated": datetime.now(pytz.utc)
                }

                # Generate additional information if model is provided
                if model:
                    existing_event = self.events.find_one({
                        "name": normalized_name,
                        "start_date": start_date
                    })
                    
                    if not existing_event or not existing_event.get('additional_information'):
                        logging.info(f"Generating additional information for: {normalized_name}")
                        additional_info = generate_additional_information(normalized_name, model)
                        if additional_info:
                            event_doc["additional_information"] = additional_info

                # Update or insert the event
                result = self.events.update_one(
                    {
                        "name": event_doc["name"],
                        "start_date": event_doc["start_date"],
                    },
                    {
                        "$set": event_doc,
                        "$addToSet": {"source_urls": source_url},
                        "$setOnInsert": {
                            "created_at": datetime.now(pytz.utc),
                            "alternate_names": EventDefinitions.ALTERNATE_NAMES.get(normalized_name, [])
                        }
                    },
                    upsert=True
                )
                
                if result.modified_count or result.upserted_id:
                    successful_updates += 1
                    logging.info(f"Successfully updated/inserted event: {normalized_name}")
                    
            except Exception as e:
                logging.error(f"Error inserting event {event}: {e}")
        
        return successful_updates

    def _is_tracked_event(self, event_name: str) -> bool:
        if not event_name:
            return False
        normalized_name = EventDefinitions.normalize_event_name(event_name)
        return normalized_name in self.tracked_events or any(
            fuzz.ratio(event_name.lower(), tracked.lower()) > 85
            for tracked in self.tracked_events
        )

    def get_events_by_category(self, category: str) -> List[Dict[str, Any]]:
        return list(self.events.find({"category": category}).sort("start_date", ASCENDING))

    def get_events_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        return list(self.events.find({
            "$or": [
                {
                    "start_date": {"$gte": start_date, "$lte": end_date}
                },
                {
                    "end_date": {"$gte": start_date, "$lte": end_date}
                }
            ]
        }).sort("start_date", ASCENDING))

    def get_events_statistics(self) -> Dict[str, Any]:
        stats = {
            "total_events": self.events.count_documents({}),
            "events_by_category": {},
            "sources": list(self.events.distinct("source_urls")),
            "date_range": {
                "earliest": None,
                "latest": None
            },
            "last_update": None
        }
        
        for category in EventDefinitions.EVENTS_BY_CATEGORY.keys():
            stats["events_by_category"][category] = self.events.count_documents(
                {"category": category}
            )
        
        if stats["total_events"] > 0:
            earliest = self.events.find_one({}, sort=[("start_date", ASCENDING)])
            latest = self.events.find_one({}, sort=[("end_date", DESCENDING)])
            stats["date_range"]["earliest"] = earliest["start_date"] if earliest else None
            stats["date_range"]["latest"] = latest["end_date"] if latest else None
            
            last_updated = self.events.find_one({}, sort=[("last_updated", DESCENDING)])
            stats["last_update"] = last_updated["last_updated"] if last_updated else None
        
        return stats

def get_website_html(url: str) -> Optional[str]:
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching website {url}: {e}")
        return None

def clean_json_response(response_text: str) -> Optional[Dict[str, Any]]:
    try:
        cleaned_text = re.sub(r'```json\n?', '', response_text)
        cleaned_text = re.sub(r'```\n?', '', cleaned_text)
        
        json_match = re.search(r'\{[\s\S]*\}|\[[\s\S]*\]', cleaned_text)
        if json_match:
            cleaned_text = json_match.group(0)
        
        return json.loads(cleaned_text)
    except Exception as e:
        logging.error(f"Error parsing JSON: {e}")
        return None

def process_single_url(url: str, model: Any, db: EventsDatabase) -> None:
    try:
        logging.info(f"Starting scrape for: {url}")
        
        html_content = get_website_html(url)
        if not html_content:
            db.record_scrape(url, False, error="Failed to fetch HTML")
            return
        
        tracked_events_str = "\n".join(EventDefinitions.get_all_events())
        
        # First prompt for event extraction
        date_extraction_prompt = f"""
        From the following HTML content, extract ONLY the dates for these specific events:

        {tracked_events_str}

        Return the data as a JSON array with each event in this format:
        {{
            "Name": "Event Name",
            "Start Date": "DD-MM-YY",
            "End Date": "DD-MM-YY",
            "Additional Details": "Any specific details about the event"
        }}

        Important rules:
        1. Only return events from the provided list
        2. Dates must be in DD-MM-YY format
        3. If an event spans multiple days, use different Start and End Dates
        4. If an event is a single day, use the same date for Start and End
        5. The current date is {date.today()}
        6. Return dates for the next occurrence of each event
        7. Include the year in the dates (YY part of DD-MM-YY)
        """
        
        response = model.generate_content(date_extraction_prompt + "\n\n" + html_content)
        events_data = clean_json_response(response.text)
        
        if not events_data:
            db.record_scrape(url, False, error="No tracked events found")
            return
        
        events_list = events_data if isinstance(events_data, list) else [events_data]
        updated_count = db.insert_events(events_list, url, model)
        
        db.record_scrape(url, True, events_count=updated_count)
        logging.info(f"Successfully processed {url}: {updated_count} events updated/added")
        
    except Exception as e:
        logging.error(f"Error processing {url}: {e}")
        db.record_scrape(url, False, error=str(e))

def scrape_events(urls: List[str], db_connection_string: str = "mongodb://localhost:27017/") -> None:
    db = EventsDatabase(db_connection_string)
    
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_url = {
            executor.submit(process_single_url, url, model, db): url
            for url in urls
        }
        
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                future.result()
            except Exception as e:
                logging.error(f"Error processing {url}: {e}")
            
            time.sleep(2)
    
    db.client.close()

def export_events_to_json(db: EventsDatabase, output_file: str = "events_export.json") -> None:
    """Export all events to a JSON file."""
    try:
        events = db.events.find({}, {'_id': 0})  # Exclude MongoDB _id field
        
        # Convert datetime objects to string format
        events_list = []
        for event in events:
            event['start_date'] = event['start_date'].strftime('%d-%m-%y')
            event['end_date'] = event['end_date'].strftime('%d-%m-%y')
            event['last_updated'] = event['last_updated'].strftime('%Y-%m-%d %H:%M:%S UTC')
            if 'created_at' in event:
                event['created_at'] = event['created_at'].strftime('%Y-%m-%d %H:%M:%S UTC')
            events_list.append(event)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(events_list, f, indent=2, ensure_ascii=False)
            
        logging.info(f"Successfully exported {len(events_list)} events to {output_file}")
        
    except Exception as e:
        logging.error(f"Error exporting events to JSON: {e}")

def main():
    """Main execution function."""
    urls = [
        "https://registrar.yorku.ca/enrol/dates/religious-accommodation-resource-2024-2025",
        "https://www.canada.ca/en/canadian-heritage/services/important-commemorative-days.html",
        "https://www.ontario.ca/page/ontarios-celebrations-and-commemorations",
    ]
    
    connection_string = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
    
    try:
        # Initialize database connection
        db = EventsDatabase(connection_string)
        
        # Run the scraper
        scrape_events(urls, connection_string)
        
        # Export events to JSON
        export_events_to_json(db)
        
        # Print statistics
        stats = db.get_events_statistics()
        
        print("\nScraping completed. Database statistics:")
        print(f"Total events: {stats['total_events']}")
        print("\nEvents by category:")
        for category, count in stats['events_by_category'].items():
            print(f"{category}: {count} events")
        
        if stats['date_range']['earliest'] and stats['date_range']['latest']:
            print(f"\nDate range: {stats['date_range']['earliest'].strftime('%Y-%m-%d')} "
                  f"to {stats['date_range']['latest'].strftime('%Y-%m-%d')}")
        
        if stats['last_update']:
            print(f"Last update: {stats['last_update'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        print("\nEvents have been exported to events_export.json")
        
    except Exception as e:
        logging.error(f"Error in main execution: {e}")
        raise
    finally:
        db.client.close()

if __name__ == "__main__":
    main()
