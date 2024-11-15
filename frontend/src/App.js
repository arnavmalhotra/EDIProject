// src/App.js
import React, { useState, useEffect } from 'react';
import Calendar from './components/Calendar/Calendar';
import EventList from './components/EventList/EventList';
import Navbar from './components/Navbar/Navbar';
import { api } from './services/api';
import './App.css';

const App = () => {
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [monthEvents, setMonthEvents] = useState([]);
  const [selectedDateEvents, setSelectedDateEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Check API status on mount
  useEffect(() => {
    const checkAPI = async () => {
      const status = await api.checkAPIStatus();
      if (!status) {
        setError('Unable to connect to the API');
      }
    };
    checkAPI();
  }, []);

  // Fetch events for the current month
  useEffect(() => {
    const fetchMonthEvents = async () => {
      setLoading(true);
      try {
        const year = selectedDate.getFullYear();
        const month = selectedDate.getMonth() + 1;
        const events = await api.getEventsByMonth(year, month);
        console.log('Month events loaded:', events);
        setMonthEvents(events);
        setError(null);
      } catch (err) {
        console.error('Error loading month events:', err);
        setError('Failed to load events');
      } finally {
        setLoading(false);
      }
    };

    fetchMonthEvents();
  }, [selectedDate]);

  // Fetch events for selected date
  useEffect(() => {
    const fetchDateEvents = async () => {
      try {
        const events = await api.getEventsByDate(selectedDate);
        console.log('Selected date events:', events);
        setSelectedDateEvents(events);
      } catch (err) {
        console.error('Error loading date events:', err);
      }
    };

    fetchDateEvents();
  }, [selectedDate]);

  const handleDateChange = (date) => {
    console.log('Date selected:', date);
    setSelectedDate(date);
  };

  return (
    <div className="app">
      <Navbar />
      <main className="main-content">
        <div className="app-description">
          Calendar showing important dates and events for the Lassonde community.
        </div>
        {error && <div className="error-message">{error}</div>}
        {loading ? (
          <div className="loading">Loading events...</div>
        ) : (
          <div className="calendar-layout">
            <div className="calendar-section">
              <Calendar
                value={selectedDate}
                onChange={handleDateChange}
                events={monthEvents}
              />
            </div>
            <div className="events-section">
              <EventList
                events={selectedDateEvents}
                selectedDate={selectedDate}
                loading={loading}
              />
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default App;