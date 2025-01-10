import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize MongoDB connection
MONGO_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)
db = client.events_db
events_collection = db.events

# Define the images directory
IMAGES_DIR = r"C:\Users\Arnav\Desktop\Code\EDIProject\frontend\public\images"

def check_missing_images():
    """Check which events are missing images."""
    # Get all events from database
    events = events_collection.find({})
    
    # Keep track of missing images
    missing_images = []
    total_events = 0
    
    # Check each event
    for event in events:
        total_events += 1
        event_name = event["name"]
        image_path = event.get("image_url", "").lstrip("/")  # Remove leading slash
        
        if not image_path:
            print(f"Warning: No image path defined for {event_name}")
            missing_images.append(event_name)
            continue
            
        # Get the full path where the image should be
        image_full_path = os.path.join(r"C:\Users\Arnav\Desktop\Code\EDIProject\frontend\public", image_path)
        
        # Check if image exists
        if not os.path.exists(image_full_path):
            missing_images.append(event_name)
    
    # Print results
    print("\n=== Missing Images Report ===")
    print(f"Total events checked: {total_events}")
    print(f"Number of events missing images: {len(missing_images)}")
    
    if missing_images:
        print("\nEvents missing images:")
        for idx, event_name in enumerate(sorted(missing_images), 1):
            print(f"{idx}. {event_name}")
    else:
        print("\nAll events have images!")

def main():
    """Main execution function."""
    try:
        print(f"Checking for images in: {IMAGES_DIR}")
        check_missing_images()
        
    except Exception as e:
        print(f"\nError during check: {e}")
        
    finally:
        client.close()
        print("\nDatabase connection closed")

if __name__ == "__main__":
    main()