// src/components/Calendar/Calendar.jsx
import React from 'react';
import ReactCalendar from 'react-calendar';
import 'react-calendar/dist/Calendar.css';
import './Calendar.css';

const Calendar = ({ value, onChange, events }) => {
  const tileClassName = ({ date, view }) => {
    if (view === 'month') {
      const hasEvent = events.some(event => {
        const startDate = new Date(event.start_date);
        const endDate = new Date(event.end_date);
        return date >= startDate && date <= endDate;
      });
      return hasEvent ? 'has-event' : null;
    }
  };

  return (
    <div className="calendar-container">
      <ReactCalendar
        value={value}
        onChange={onChange}
        tileClassName={tileClassName}
        minDetail="month"
        className="custom-calendar"
      />
    </div>
  );
};

// Only one default export per file
export default Calendar;

// If you need to export other things, use named exports:
export const someHelper = () => {
  // helper function
};