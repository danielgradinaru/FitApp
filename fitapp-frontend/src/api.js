// src/api.js
import axios from 'axios';
import { supabase } from './lib/supabase';

const API_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
});

// Interceptor pentru a atasa token-ul Supabase automat
api.interceptors.request.use(
  async (config) => {
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      console.log('SESSION:', session);
      console.log('ACCESS TOKEN EXISTS:', !!session?.access_token);

      if (session?.access_token) {
        config.headers.Authorization = `Bearer ${session.access_token}`;
      }

      console.log('AUTH HEADER SET:', config.headers.Authorization);
    } catch (error) {
      console.error('Eroare la preluarea sesiunii Supabase:', error);
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// LOGIN / REGISTER se fac acum direct cu Supabase in frontend,
// deci nu mai exportam loginUser si registerUser din backend API.

export const processVideo = (file, exercise) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('exercise', exercise);

  return api.post('/analyze/process', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const saveResult = (data) => api.post('/analyze/save', data);

export const getStats = () => api.get('/stats');

export const getHistory = () => api.get('/history');

export const getUserProfile = () => api.get('/users/me');

export const deleteWorkout = (id) => api.delete(`/history/${id}`);

export default api;
