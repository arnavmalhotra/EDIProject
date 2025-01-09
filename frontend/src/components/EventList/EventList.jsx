// src/components/EventList/EventList.jsx
import React from 'react';
import { Link } from 'react-router-dom';
import './EventList.css';

// Helper function to format date ignoring timezone
const formatDate = (dateString) => {
  const date = new Date(dateString);
  return new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate()
  ).toLocaleDateString();
};

// Helper function to calculate days between dates
const getDaysBetween = (startDate, endDate) => {
  const start = new Date(startDate.getFullYear(), startDate.getMonth(), startDate.getDate());
  const end = new Date(endDate.getFullYear(), endDate.getMonth(), endDate.getDate());
  return Math.round((end - start) / (1000 * 60 * 60 * 24)) + 1;
};

const EventCard = ({ event }) => {
  return (
    <div className="event-card">
      <div className="event-header">
        <h3>{event.name}</h3>
      </div>
      <div className="event-dates">
        <span>Start: {formatDate(event.start_date)}</span>
        <br />
        <span>End: {formatDate(event.end_date)}</span>
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

  // Separate events into different categories based on duration
  const categorizedEvents = events.reduce((acc, event) => {
    const startDate = new Date(event.start_date);
    const endDate = new Date(event.end_date);
    const duration = getDaysBetween(startDate, endDate);

    // Regular events (less than 6 days)
    if (duration < 6) {
      acc.regular.push(event);
    }
    // Extended events (6 days or more)
    else {
      acc.extended.push(event);
    }

    return acc;
  }, { regular: [], extended: [] });

  // Format the date without timezone considerations
  const formattedDate = new Date(
    selectedDate.getFullYear(),
    selectedDate.getMonth(),
    selectedDate.getDate()
  ).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });

  return (
    <div className="event-list">
      <h2>Events for {formattedDate}</h2>
      
      {categorizedEvents.regular.length > 0 && (
        <div className="regular-events">
          <h3>Events</h3>
          <div className="events-container">
            {categorizedEvents.regular.map((event) => (
              <EventCard key={event._id} event={event} />
            ))}
          </div>
        </div>
      )}
      
      {categorizedEvents.extended.length > 0 && (
        <div className="extended-events">
          <h3>Extended Observances</h3>
          <div className="events-container">
            {categorizedEvents.extended.map((event) => (
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