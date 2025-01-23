from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime
from typing import Optional
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = MongoClient("mongodb://localhost:27017/")
db = client.events_db
events_collection = db.events

def serialize_event(event):
    event['_id'] = str(event['_id'])
    for field in ['start_date', 'end_date', 'created_at', 'last_updated']:
        if isinstance(event.get(field), datetime):
            event[field] = event[field].isoformat()
    return event

@app.get("/")
async def root(
    event_id: Optional[str] = None,
    date: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    upcoming_days: Optional[int] = Query(None, alias="days")
):
    try:
        # Get single event by ID
        if event_id:
            event = events_collection.find_one({"_id": event_id})
            if not event:
                raise HTTPException(status_code=404, detail="Event not found")
            return {"event": serialize_event(event)}

        # Get events by specific date
        if date:
            try:
                target_date = datetime.fromisoformat(date)
                events = list(events_collection.find({
                    "start_date": {"$lte": target_date},
                    "end_date": {"$gte": target_date}
                }).sort("start_date", 1))
                return {"events": [serialize_event(event) for event in events]}
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid date format: {date}")

        # Get events by month
        if year is not None and month is not None:
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, month + 1, 1)
            
            events = list(events_collection.find({
                "$or": [
                    {"start_date": {"$gte": start_date, "$lt": end_date}},
                    {"end_date": {"$gte": start_date, "$lt": end_date}},
                    {"start_date": {"$lte": start_date}, "end_date": {"$gte": end_date}}
                ]
            }).sort("start_date", 1))
            return {"events": [serialize_event(event) for event in events]}

        # Get upcoming events
        if upcoming_days is not None:
            current_date = datetime.now()
            events = list(events_collection.find({
                "end_date": {"$gte": current_date}
            }).sort("start_date", 1).limit(upcoming_days))
            return {"events": [serialize_event(event) for event in events]}

        # Default: get all events and API status
        event_count = events_collection.count_documents({})
        events = list(events_collection.find().sort("start_date", 1))
        return {
            "status": "API is running",
            "total_events": event_count,
            "database_connection": "successful",
            "events": [serialize_event(event) for event in events]
        }

    except Exception as e:
        logger.error(f"Error in root endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3600, log_level="debug")
