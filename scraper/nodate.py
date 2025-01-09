from pymongo import MongoClient
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Initialize MongoDB connection
MONGO_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)
db = client.events_db
events_collection = db.events

def find_events_without_date_fields():
    """
    Find events in the database that don't have start_date and end_date fields.
    """
    # Find events where start_date or end_date fields are missing
    events_without_dates = events_collection.find({
        "$or": [
            {"start_date": {"$exists": False}},
            {"end_date": {"$exists": False}}
        ]
    })
    
    # Convert to list and print results
    events_list = list(events_without_dates)
    
    print(f"Total events without start_date or end_date: {len(events_list)}")
    
    for event in events_list:
        print(f"{event['name']}")

def main():
    try:
        find_events_without_date_fields()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()