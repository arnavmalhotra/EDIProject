// src/utils/dateUtils.js
export const utcToLocal = (dateString) => {
    const date = new Date(dateString);
    return new Date(date.getTime() + date.getTimezoneOffset() * 60000);
  };
  
  export const formatLocalDate = (dateString) => {
    const date = utcToLocal(dateString);
    return date.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
    });
  };
  
  export const isSameDay = (date1, date2) => {
    const d1 = utcToLocal(date1);
    const d2 = utcToLocal(date2);
    return d1.getFullYear() === d2.getFullYear() &&
           d1.getMonth() === d2.getMonth() &&
           d1.getDate() === d2.getDate();
  };
  
  export const isDateInRange = (date, startDate, endDate) => {
    const compareDate = utcToLocal(date);
    const start = utcToLocal(startDate);
    const end = utcToLocal(endDate);
    return compareDate >= start && compareDate <= end;
  };
  
  export const getDaysBetween = (startDate, endDate) => {
    const start = utcToLocal(startDate);
    const end = utcToLocal(endDate);
    return Math.round((end - start) / (1000 * 60 * 60 * 24)) + 1;
  };