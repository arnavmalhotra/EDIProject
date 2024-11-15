from pymongo import MongoClient
from datetime import datetime

def test_mongodb():
    # Connect to MongoDB
    client = MongoClient("mongodb://localhost:27017/")
    db = client.events_db
    events_collection = db.events
    
    # Print total number of documents
    print(f"Total events: {events_collection.count_documents({})}")
    
    # Insert a test document
    test_event = {
        "name": "Test Event",
        "start_date": datetime.now(),
        "end_date": datetime.now(),
        "additional_details": "This is a test event",
        "source_url": "http://test.com"
    }
    
    result = events_collection.insert_one(test_event)
    print(f"Inserted test event with ID: {result.inserted_id}")
    
    # Retrieve and print all documents
    print("\nAll events in database:")
    for event in events_collection.find():
        print(f"Event: {event}")

if __name__ == "__main__":
    test_mongodb()