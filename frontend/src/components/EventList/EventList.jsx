// src/components/EventList/EventList.jsx
import React, { useState } from 'react';
import './EventList.css';

const EventCard = ({ event }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div 
      className={`event-card ${expanded ? 'expanded' : ''}`}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="event-header">
        <h3>{event.name}</h3>
        <span className="expand-icon">{expanded ? '−' : '+'}</span>
      </div>
      <div className="event-dates">
        <span>Start: {new Date(event.start_date).toLocaleDateString()}</span>
        <br />
        <span>End: {new Date(event.end_date).toLocaleDateString()}</span>
      </div>
      {expanded && (
        <div className="event-details">
          {event.additional_details && (
            <p>{event.additional_details}</p>
          )}
          <p>Source: {event.source_url}</p>
          {event.created_at && (
            <p className="meta-info">Created: {new Date(event.created_at).toLocaleDateString()}</p>
          )}
          {event.last_updated && (
            <p className="meta-info">Last Updated: {new Date(event.last_updated).toLocaleDateString()}</p>
          )}
        </div>
      )}
    </div>
  );
};

const EventList = ({ events, selectedDate, loading }) => {
  if (loading) {
    return <div className="loading">Loading events...</div>;
  }

  return (
    <div className="event-list">
      <h2>
        Events for {selectedDate.toLocaleDateString('en-US', {
          year: 'numeric',
          month: 'long',
          day: 'numeric'
        })}
      </h2>
      <div className="events-container">
        {events && events.length > 0 ? (
          events.map((event) => (
            <EventCard key={event._id} event={event} />
          ))
        ) : (
          <p className="no-events">No events for this date</p>
        )}
      </div>
    </div>
  );
};

export default EventList;