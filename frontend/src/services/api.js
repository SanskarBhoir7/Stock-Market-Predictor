import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const BACKEND_ROOT = API_URL.replace(/\/api\/v1\/?$/, '');

const api = axios.create({
  baseURL: API_URL,
});

const rootApi = axios.create({
  baseURL: BACKEND_ROOT,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

rootApi.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const authService = {
  login: async (username, password) => {
    // FastAPI OAuth2PasswordRequestForm expects form-urlencoded data rather than JSON
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const response = await api.post('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    
    if (response.data.access_token) {
      localStorage.setItem('token', response.data.access_token);
    }
    return response.data;
  },

  register: async (email, username, password) => {
    const response = await api.post('/auth/register', {
      email,
      username,
      password,
    });
    return response.data;
  },

  logout: () => {
    localStorage.removeItem('token');
  },

  getCurrentUser: async () => {
    const response = await api.get('/auth/me');
    return response.data;
  },
};

export const marketService = {
  getHealthStatus: async () => {
    const response = await rootApi.get('/health');
    return response.data;
  },
  getSearchSuggestions: async (query, limit = 8) => {
    const response = await api.get(`/market/search-suggestions?q=${encodeURIComponent(query)}&limit=${limit}`);
    return response.data;
  },
  getTickerData: async (ticker) => {
    const response = await api.get(`/market/data?ticker=${ticker}`);
    return response.data;
  },
  getHistoricalData: async (ticker, period = '6mo', interval = '1d') => {
    const response = await api.get(`/market/historical?ticker=${ticker}&period=${period}&interval=${interval}`);
    return response.data;
  },
  getNewsData: async (ticker) => {
    const response = await api.get(`/market/news?ticker=${ticker}`);
    return response.data;
  },
  getPredictionData: async (ticker, currentPrice, sentiment, horizon = '1d') => {
    const response = await api.get(`/market/prediction?ticker=${ticker}&current_price=${currentPrice}&sentiment=${sentiment}&horizon=${horizon}`);
    return response.data;
  }
};

export default api;
