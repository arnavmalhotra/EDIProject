// src/components/Calendar/Calendar.jsx
import React, { useRef, useEffect } from 'react';
import ReactCalendar from 'react-calendar';
import 'react-calendar/dist/Calendar.css';
import './Calendar.css';

const Calendar = ({ value, onChange, events }) => {
  const calendarRef = useRef(null);

  const tileClassName = ({ date, view }) => {
    if (view === 'month') {
      const hasEvent = events?.some(event => {
        const startDate = new Date(event.start_date);
        const endDate = new Date(event.end_date);
        const isMonthLongEvent =
          startDate.getDate() === 1 &&
          endDate.getDate() >= 28 &&
          startDate.getMonth() === endDate.getMonth() &&
          startDate.getFullYear() === endDate.getFullYear();
        return !isMonthLongEvent && date >= startDate && date <= endDate;
      });
      return hasEvent ? 'has-event' : null;
    }
  };

  const handleActiveStartDateChange = ({ activeStartDate }) => {
    if (!activeStartDate) return;
    const newDate = new Date(activeStartDate.getFullYear(), activeStartDate.getMonth(), 1);
    onChange(newDate);
  };

  useEffect(() => {
    // Ensure the calendar is mounted and refs are set
    if (calendarRef.current) {
      // Any initialization if needed
    }
  }, []);

  return (
    <div className="calendar-container">
      <ReactCalendar
        ref={calendarRef}
        value={value}
        onChange={onChange}
        tileClassName={tileClassName}
        minDetail="month"
        className="custom-calendar"
        onActiveStartDateChange={handleActiveStartDateChange}
      />
    </div>
  );
};

export default Calendar;
