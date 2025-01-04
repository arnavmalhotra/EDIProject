// src/components/EventList/EventList.jsx
import React from 'react';
import { Link } from 'react-router-dom';
import './EventList.css';

const EventCard = ({ event }) => {
  return (
    <div className="event-card">
      <div className="event-header">
        <h3>{event.name}</h3>
      </div>
      <div className="event-dates">
        <span>Start: {new Date(event.start_date).toLocaleDateString()}</span>
        <br />
        <span>End: {new Date(event.end_date).toLocaleDateString()}</span>
      </div>
      <div className="event-actions">
<Link 
  to={`/event/${event._id}`} 
  className="more-info-button"
>
  More Information
</Link>
      </div>
    </div>
  );
};

const EventList = ({ events, selectedDate, loading }) => {
  if (loading) {
    return <div className="loading">Loading events...</div>;
  }

  // Separate month-long events and regular events
  const monthLongEvents = events.filter(event => {
    const start = new Date(event.start_date);
    const end = new Date(event.end_date);
    return (
      start.getDate() === 1 && 
      end.getDate() >= 28 && 
      start.getMonth() === end.getMonth() &&
      start.getFullYear() === end.getFullYear()
    );
  });

  const regularEvents = events.filter(event => {
    const start = new Date(event.start_date);
    const end = new Date(event.end_date);
    return !(
      start.getDate() === 1 && 
      end.getDate() >= 28 &&
      start.getMonth() === end.getMonth() &&
      start.getFullYear() === end.getFullYear()
    );
  });

  return (
    <div className="event-list">
      <h2>
        Events for {selectedDate.toLocaleDateString('en-US', {
          year: 'numeric',
          month: 'long',
          day: 'numeric'
        })}
      </h2>
      
      {regularEvents.length > 0 && (
        <div className="regular-events">
          <h3>Events</h3>
          <div className="events-container">
            {regularEvents.map((event) => (
              <EventCard key={event._id} event={event} />
            ))}
          </div>
        </div>
      )}
      
      {monthLongEvents.length > 0 && (
        <div className="month-long-events">
          <h3>Month-Long Observances</h3>
          <div className="events-container">
            {monthLongEvents.map((event) => (
              <EventCard key={event._id} event={event} />
            ))}
          </div>
        </div>
      )}

      {events.length === 0 && (
        <p className="no-events">No events for this date</p>
      )}
    </div>
  );
};

export default EventList;