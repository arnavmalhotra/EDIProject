// src/pages/EventDetail/EventDetail.jsx
// Add images next to event names, description stays static every year. Implement manual scraping, only thing that changes is the date.
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../../services/api';
import './EventDetail.css';

const EventDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchAllEvents = async () => {
      try {
        setLoading(true);
        const allEvents = await api.getAllEvents();
        setEvents(allEvents);
        setError(null);

        if (id) {
          setTimeout(() => {
            const element = document.getElementById(`event-${id}`);
            if (element) {
              element.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
          }, 100);
        }
      } catch (err) {
        console.error('Error fetching events:', err);
        setError('Failed to load events');
      } finally {
        setLoading(false);
      }
    };

    fetchAllEvents();
  }, [id]);

  if (loading) {
    return <div className="loading">Loading event details...</div>;
  }

  if (error) {
    return (
      <div className="event-detail-page">
        <div className="event-card error-card">
          <div className="error">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="event-detail-page">
      <div className="floating-button-container">
        <button onClick={() => navigate('/')} className="floating-return-button">
          Return to Calendar
        </button>
      </div>

      <div className="event-detail-header">
        <h1>Event Details</h1>
      </div>

      {events.map((event) => (
        <div 
          key={event._id} 
          id={`event-${event._id}`} 
          className="event-card"
        >
          <div className="event-header-extra">
            <h2>{event.name}</h2>
            <div className="event-category">{event.category}</div>
          </div>
          
          <div className="event-content">
            <div className="event-dates">
              <div className="date-item">
                <strong>Start Date:</strong>
                <span>{new Date(event.start_date).toLocaleDateString()}</span>
              </div>
              <div className="date-item">
                <strong>End Date:</strong>
                <span>{new Date(event.end_date).toLocaleDateString()}</span>
              </div>
            </div>

            {event.additional_information?.historical_background && (
              <div className="event-section">
                <h3>Historical Background</h3>
                <p>{event.additional_information.historical_background}</p>
              </div>
            )}

            {event.additional_information?.significance && (
              <div className="event-section">
                <h3>Significance</h3>
                <p>{event.additional_information.significance}</p>
              </div>
            )}

            {event.additional_information?.observance_details && (
              <div className="event-section">
                <h3>How It's Observed</h3>
                <p>{event.additional_information.observance_details}</p>
              </div>
            )}

            {event.additional_information?.modern_celebration && (
              <div className="event-section">
                <h3>Modern Celebration</h3>
                <p>{event.additional_information.modern_celebration}</p>
              </div>
            )}

            {event.additional_information?.impact_and_legacy && (
              <div className="event-section">
                <h3>Impact and Legacy</h3>
                <p>{event.additional_information.impact_and_legacy}</p>
              </div>
            )}

            {event.additional_details && (
              <div className="event-section">
                <h3>Additional Details</h3>
                <p>{event.additional_details}</p>
              </div>
            )}

            {event.alternate_names && event.alternate_names.length > 0 && (
              <div className="event-section">
                <h3>Also Known As</h3>
                <p>{event.alternate_names.join(', ')}</p>
              </div>
            )}

            {event.source_urls && (
              <div className="event-section">
                <h3>Sources</h3>
                <div className="source-links">
                  {Array.isArray(event.source_urls) ? (
                    event.source_urls.map((url, index) => (
                      <a 
                        key={index} 
                        href={url} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="source-link"
                      >
                        Source {index + 1}
                      </a>
                    ))
                  ) : (
                    <a 
                      href={event.source_urls} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="source-link"
                    >
                      Source
                    </a>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};

export default EventDetail;
