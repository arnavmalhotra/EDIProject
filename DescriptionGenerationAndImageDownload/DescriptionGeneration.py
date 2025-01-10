import os
from datetime import datetime
import pytz
from pymongo import MongoClient
from dotenv import load_dotenv
import google.generativeai as genai
import time

# Load environment variables
load_dotenv()

# Initialize MongoDB connection
MONGO_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)
db = client.events_db
events_collection = db.events

# Initialize Gemini API
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel("gemini-1.5-flash")

def generate_event_description(event_name, category):
    """Generate an accurate description for an event using Gemini."""
    try:
        prompt = f"""Please provide a concise, accurate, and culturally sensitive description of the {event_name}, which is a {category} observance. 
        Include its significance, common practices, and any important historical context.
        Focus on being informative while respecting the religious/cultural significance.
        Keep the description between 100-150 words.
        You should also refrain from mentioning the date that the event is observed on.
        
        Your response should be direct, factual, and avoid any speculative language."""
        
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,
                top_p=0.8,
                top_k=40,
                max_output_tokens=300,
            )
        )
        
        return response.text.strip()
    
    except Exception as e:
        print(f"Error generating description for {event_name}: {e}")
        return None

def update_event_entries():
    """Update all events with descriptions."""
    events = events_collection.find({
        "additional_details": {"$exists": False}
    })    
    for event in events:
        event_name = event["name"]
        category = event["category"]
        print(f"\nProcessing: {event_name}")
        
        # Generate description if not present
        if "additional_details" not in event or "description" not in event.get("additional_details", {}):
            print("Generating description...")
            description = generate_event_description(event_name, category)
            if description:
                events_collection.update_one(
                    {"_id": event["_id"]},
                    {
                        "$set": {
                            "additional_details": description,
                            "last_updated": datetime.now(pytz.utc)
                        }
                    }
                )
                print("Description added successfully!")
        else:
            print("Description already exists, skipping...")
        
        # Add delay to respect API rate limits
        time.sleep(2)

def main():
    """Main execution function."""
    try:
        print("Starting description generation process...")
        update_event_entries()
        print("\nDescription generation completed successfully!")
        
    except Exception as e:
        print(f"\nError during description generation: {e}")
        
    finally:
        client.close()
        print("\nDatabase connection closed")

if __name__ == "__main__":
    main()