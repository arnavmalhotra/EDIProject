from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime, date
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client.events_db
events_collection = db.events

def serialize_event(event):
    """Convert MongoDB document to JSON-serializable format."""
    event['_id'] = str(event['_id'])
    if isinstance(event.get('start_date'), datetime):
        event['start_date'] = event['start_date'].isoformat()
    if isinstance(event.get('end_date'), datetime):
        event['end_date'] = event['end_date'].isoformat()
    if isinstance(event.get('created_at'), datetime):
        event['created_at'] = event['created_at'].isoformat()
    if isinstance(event.get('last_updated'), datetime):
        event['last_updated'] = event['last_updated'].isoformat()
    return event

@app.get("/")
async def root():
    """Root endpoint to verify API is running."""
    try:
        event_count = events_collection.count_documents({})
        return {
            "status": "API is running",
            "total_events": event_count,
            "database_connection": "successful"
        }
    except Exception as e:
        logger.error(f"Error in root endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/events")
async def get_all_events():
    """Get all events from the database."""
    try:
        events = list(events_collection.find().sort("start_date", 1))
        return {"events": [serialize_event(event) for event in events]}
    except Exception as e:
        logger.error(f"Error fetching all events: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/events/date/{date}")
async def get_events_by_date(date: str):
    """Get events for a specific date."""
    try:
        target_date = datetime.fromisoformat(date)
        events = list(events_collection.find({
            "start_date": {"$lte": target_date},
            "end_date": {"$gte": target_date}
        }).sort("start_date", 1))
        
        return {"events": [serialize_event(event) for event in events]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date}")
    except Exception as e:
        logger.error(f"Error fetching events by date: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/events/month/{year}/{month}")
async def get_events_by_month(year: int, month: int):
    """Get all events for a specific month."""
    try:
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        # Modified query to include events that overlap with the month
        events = list(events_collection.find({
            "$or": [
                # Events that start in this month
                {
                    "start_date": {
                        "$gte": start_date,
                        "$lt": end_date
                    }
                },
                # Events that end in this month
                {
                    "end_date": {
                        "$gte": start_date,
                        "$lt": end_date
                    }
                },
                # Events that span the entire month
                {
                    "start_date": {"$lte": start_date},
                    "end_date": {"$gte": end_date}
                }
            ]
        }).sort("start_date", 1))
        
        return {"events": [serialize_event(event) for event in events]}
    except Exception as e:
        logger.error(f"Error fetching events by month: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/events/upcoming")
async def get_upcoming_events(days: int = 30):
    """Get upcoming events."""
    try:
        current_date = datetime.now()
        end_date = datetime.now().replace(hour=23, minute=59, second=59)
        
        events = list(events_collection.find({
            "end_date": {"$gte": current_date}
        }).sort("start_date", 1).limit(days))
        
        return {"events": [serialize_event(event) for event in events]}
    except Exception as e:
        logger.error(f"Error fetching upcoming events: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="debug")