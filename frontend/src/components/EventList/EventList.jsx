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
        <div className="event-actions">
          <button 
            className="more-info-btn"
            onClick={(e) => {
              e.stopPropagation(); // Prevents the card from expanding when clicking the button
              // Handle button click here
              console.log('More information clicked for event:', event.name);
            }}
          >
            More Information
          </button>
        </div>
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
          {event.source_url && (
            <div className="source-links">
              {Array.isArray(event.source_url) ? (
                event.source_url.map((url, index) => (
                  <a key={index} href={url} target="_blank" rel="noopener noreferrer">
                    Source {index + 1}
                  </a>
                ))
              ) : (
                <a href={event.source_url} target="_blank" rel="noopener noreferrer">
                  Source
                </a>
              )}
            </div>
          )}
          {event.alternate_names && event.alternate_names.length > 1 && (
            <div className="alternate-names">
              <p>Also known as: {event.alternate_names.filter(name => name !== event.name).join(', ')}</p>
            </div>
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