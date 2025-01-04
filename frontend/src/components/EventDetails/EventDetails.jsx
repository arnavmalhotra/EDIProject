// src/components/EventDetails/EventDetails.jsx
import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import './EventDetails.css';

const EventDetails = ({ events = [] }) => {
  const { eventId } = useParams();
  const navigate = useNavigate();
  
  const event = events.find(e => e._id === eventId);

  if (!event) {
    return (
      <div className="event-details-page">
        <div className="event-details-container">
          <h1>Event Not Found</h1>
          <button className="back-button" onClick={() => navigate('/')}>
            Back to Calendar
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="event-details-page">
      <div className="event-details-container">
        <button className="back-button" onClick={() => navigate('/')}>
          Back to Calendar
        </button>
        
        <h1>{event.name}</h1>
        
        <div className="event-dates">
          <div className="date-block">
            <h3>Start Date</h3>
            <p>{new Date(event.start_date).toLocaleDateString('en-US', {
              weekday: 'long',
              year: 'numeric',
              month: 'long',
              day: 'numeric'
            })}</p>
          </div>
          <div className="date-block">
            <h3>End Date</h3>
            <p>{new Date(event.end_date).toLocaleDateString('en-US', {
              weekday: 'long',
              year: 'numeric',
              month: 'long',
              day: 'numeric'
            })}</p>
          </div>
        </div>

        {event.additional_details && (
          <div className="details-section">
            <h2>Additional Details</h2>
            <p>{event.additional_details}</p>
          </div>
        )}

        {event.alternate_names && event.alternate_names.length > 1 && (
          <div className="details-section">
            <h2>Also Known As</h2>
            <p>{event.alternate_names.filter(name => name !== event.name).join(', ')}</p>
          </div>
        )}

        {event.source_url && (
          <div className="details-section">
            <h2>Sources</h2>
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
          </div>
        )}
      </div>
    </div>
  );
};

export default EventDetails;