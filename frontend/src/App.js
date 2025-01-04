// src/App.js
import React, { useState, useEffect, Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';
import Calendar from './components/Calendar/Calendar';
import EventList from './components/EventList/EventList';
import Navbar from './components/Navbar/Navbar';
import ErrorBoundary from './components/ErrorBoundary/ErrorBoundary';
import { api } from './services/api';
import './App.css';

// Lazy load the EventDetail component
const EventDetail = React.lazy(() => import('./pages/EventDetail/EventDetail'));

const LoadingFallback = () => (
  <div className="loading">Loading...</div>
);

const CalendarView = ({ 
  selectedDate, 
  monthEvents, 
  selectedDateEvents, 
  loading, 
  error, 
  handleDateChange 
}) => (
  <>
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
            value={selectedDate || new Date()}
            onChange={handleDateChange}
            events={monthEvents || []}
          />
        </div>
        <div className="events-section">
          <EventList
            events={selectedDateEvents || []}
            selectedDate={selectedDate || new Date()}
            loading={loading}
          />
        </div>
      </div>
    )}
  </>
);

const App = () => {
  const [selectedDate, setSelectedDate] = useState(() => new Date());
  const [monthEvents, setMonthEvents] = useState([]);
  const [selectedDateEvents, setSelectedDateEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const checkAPI = async () => {
      try {
        const status = await api.checkAPIStatus();
        if (!status) {
          setError('Unable to connect to the API');
        }
      } catch (err) {
        setError('Unable to connect to the API');
      }
    };
    checkAPI();
  }, []);

  useEffect(() => {
    const fetchMonthEvents = async () => {
      if (!selectedDate) return;
      
      setLoading(true);
      try {
        const year = selectedDate.getFullYear();
        const month = selectedDate.getMonth() + 1;
        const events = await api.getEventsByMonth(year, month);
        setMonthEvents(events || []);
        setError(null);
      } catch (err) {
        console.error('Error loading month events:', err);
        setError('Failed to load events');
        setMonthEvents([]);
      } finally {
        setLoading(false);
      }
    };

    fetchMonthEvents();
  }, [selectedDate]);

  useEffect(() => {
    const fetchDateEvents = async () => {
      if (!selectedDate) return;

      try {
        const events = await api.getEventsByDate(selectedDate);
        setSelectedDateEvents(events || []);
      } catch (err) {
        console.error('Error loading date events:', err);
        setSelectedDateEvents([]);
      }
    };

    fetchDateEvents();
  }, [selectedDate]);

  const handleDateChange = (date) => {
    if (date && date instanceof Date && !isNaN(date)) {
      setSelectedDate(date);
    }
  };

  return (
    <div className="app">
      <Navbar />
      <main className="main-content">
        <Routes>
          <Route 
            path="/" 
            element={
              <CalendarView
                selectedDate={selectedDate}
                monthEvents={monthEvents}
                selectedDateEvents={selectedDateEvents}
                loading={loading}
                error={error}
                handleDateChange={handleDateChange}
              />
            } 
          />
          <Route 
            path="/event/:id" 
            element={
              <Suspense fallback={<LoadingFallback />}>
                <EventDetail />
              </Suspense>
            } 
          />
        </Routes>
      </main>
    </div>
  );
};

export default App;