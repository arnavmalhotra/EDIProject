import axios from 'axios';

const customAxios = axios.create({
  baseURL: 'https://dedi.eecs.yorku.ca'
});

export const api = {
  getAllEvents: async () => {
    try {
      const response = await customAxios.get('/api');
      return response.data.events || [];
    } catch (error) {
      console.error('Error fetching all events:', error);
      return [];
    }
  },

  getEventsByDate: async (date) => {
    try {
      const formattedDate = date.toISOString().split('T')[0];
      const response = await customAxios.get('/api', { 
        params: { date: formattedDate }
      });
      return response.data.events || [];
    } catch (error) {
      console.error('Error fetching events by date:', error);
      return [];
    }
  },

  getEventsByMonth: async (year, month) => {
    try {
      const response = await customAxios.get('/api', { 
        params: { year, month }
      });
      return response.data.events || [];
    } catch (error) {
      console.error('Error fetching events by month:', error);
      return [];
    }
  },

  getUpcomingEvents: async (days = 30) => {
    try {
      const response = await customAxios.get('/api', {
        params: { days }
      });
      return response.data.events || [];
    } catch (error) {
      console.error('Error fetching upcoming events:', error);
      return [];
    }
  },

  getEventById: async (id) => {
    try {
      const response = await customAxios.get('/api', {
        params: { event_id: id }
      });
      return response.data.event || null;
    } catch (error) {
      console.error('Error fetching event details:', error);
      throw error;
    }
  },

  checkAPIStatus: async () => {
    try {
      const response = await customAxios.get('/api');
      return {
        status: response.data.status,
        total_events: response.data.total_events,
        database_connection: response.data.database_connection
      };
    } catch (error) {
      console.error('Failed to connect:', error.message);
      throw error;
    }
  }
};
