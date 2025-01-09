// src/components/Calendar/Calendar.jsx
import React, { useRef } from 'react';
import ReactCalendar from 'react-calendar';
import 'react-calendar/dist/Calendar.css';
import './Calendar.css';

// Helper function to strip time information and compare only dates
const isSameDay = (date1, date2) => {
  return date1.getFullYear() === date2.getFullYear() &&
         date1.getMonth() === date2.getMonth() &&
         date1.getDate() === date2.getDate();
};

// Helper function to compare if a date falls within a range
const isDateInRange = (date, startDate, endDate) => {
  const compareDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const start = new Date(startDate.getFullYear(), startDate.getMonth(), startDate.getDate());
  const end = new Date(endDate.getFullYear(), endDate.getMonth(), endDate.getDate());
  return compareDate >= start && compareDate <= end;
};

// Helper function to calculate days between dates
const getDaysBetween = (startDate, endDate) => {
  const start = new Date(startDate.getFullYear(), startDate.getMonth(), startDate.getDate());
  const end = new Date(endDate.getFullYear(), endDate.getMonth(), endDate.getDate());
  return Math.round((end - start) / (1000 * 60 * 60 * 24)) + 1;
};

const Calendar = ({ value, onChange, events }) => {
  const calendarRef = useRef(null);

  const tileClassName = ({ date, view }) => {
    if (view === 'month') {
      const hasEvent = events?.some(event => {
        const startDate = new Date(event.start_date);
        const endDate = new Date(event.end_date);
        const duration = getDaysBetween(startDate, endDate);
        
        // Only highlight events that are less than 6 days
        return duration < 6 && isDateInRange(date, startDate, endDate);
      });
      return hasEvent ? 'has-event' : null;
    }
  };

  const handleDateChange = (date) => {
    // Create new date object with only year, month, day components
    const newDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    onChange(newDate);
  };

  const handleActiveStartDateChange = ({ activeStartDate }) => {
    if (!activeStartDate) return;
    // Create new date object with only year, month components
    const newDate = new Date(activeStartDate.getFullYear(), activeStartDate.getMonth(), 1);
    onChange(newDate);
  };

  return (
    <div className="calendar-container">
      <ReactCalendar
        ref={calendarRef}
        value={value}
        onChange={handleDateChange}
        tileClassName={tileClassName}
        minDetail="month"
        className="custom-calendar"
        onActiveStartDateChange={handleActiveStartDateChange}
      />
    </div>
  );
};

export default Calendar;