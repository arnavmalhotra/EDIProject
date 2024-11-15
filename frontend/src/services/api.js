// src/services/api.js
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8080/api';

export const api = {
  getAllEvents: async () => {
    try {
      console.log('Fetching all events...');
      const response = await axios.get(`${API_BASE_URL}/events`);
      console.log('Events received:', response.data);
      return response.data.events || [];
    } catch (error) {
      console.error('Error fetching all events:', error);
      console.log('Error response:', error.response);
      return [];
    }
  },

  getEventsByDate: async (date) => {
    try {
      const formattedDate = date.toISOString().split('T')[0];
      console.log('Fetching events for date:', formattedDate);
      const response = await axios.get(`${API_BASE_URL}/events/date/${formattedDate}`);
      console.log('Date events received:', response.data);
      return response.data.events || [];
    } catch (error) {
      console.error('Error fetching events by date:', error);
      console.log('Error response:', error.response);
      return [];
    }
  },

  getEventsByMonth: async (year, month) => {
    try {
      console.log(`Fetching events for ${year}-${month}`);
      const response = await axios.get(`${API_BASE_URL}/events/month/${year}/${month}`);
      console.log('Month events received:', response.data);
      return response.data.events || [];
    } catch (error) {
      console.error('Error fetching events by month:', error);
      console.log('Error response:', error.response);
      return [];
    }
  },

  getUpcomingEvents: async (days = 30) => {
    try {
      console.log(`Fetching upcoming events for next ${days} days`);
      const response = await axios.get(`${API_BASE_URL}/events/upcoming?days=${days}`);
      console.log('Upcoming events received:', response.data);
      return response.data.events || [];
    } catch (error) {
      console.error('Error fetching upcoming events:', error);
      console.log('Error response:', error.response);
      return [];
    }
  },

  checkAPIStatus: async () => {
    try {
      const response = await axios.get('http://localhost:8080/');
      console.log('API Status:', response.data);
      return response.data;
    } catch (error) {
      console.error('Error checking API status:', error);
      return null;
    }
  }
};