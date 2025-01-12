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

def find_events_without_additional_details():
    """
    Find events in the database that don't have the additional_details field.
    """
    # Find events where additional_details field is missing
    events_without_descriptions = events_collection.find({
        "additional_details": {"$exists": False}
    })
    
    # Convert to list and print results
    events_list = list(events_without_descriptions)
    
    print(f"Total events without additional_details: {len(events_list)}")
    
    for event in events_list:
        print(f"Event without additional_details: {event.get('name', 'Unnamed Event')}")

def find_events_without_concise_details():
    """
    Find events in the database that don't have the concise_details field.
    """
    # Find events where concise_details field is missing
    events_without_descriptions = events_collection.find({
        "concise_details": {"$exists": False}
    })
    
    # Convert to list and print results
    events_list = list(events_without_descriptions)
    
    print(f"Total events without concise_details: {len(events_list)}")
    
    for event in events_list:
        print(f"Event without concise_details: {event.get('name', 'Unnamed Event')}")

def main():
    try:
        find_events_without_additional_details()
        find_events_without_concise_details()

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
