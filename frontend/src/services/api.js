import axios from 'axios';

// Connect Axios to our FastAPI Local Server running on port 8000
const API_URL = 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_URL,
});

api.interceptors.request.use((config) => {
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
  getSearchSuggestions: async (query, limit = 8) => {
    const response = await api.get(`/market/search-suggestions?q=${encodeURIComponent(query)}&limit=${limit}`);
    return response.data;
  },
  getTickerData: async (ticker) => {
    const response = await api.get(`/market/data?ticker=${ticker}`);
    return response.data;
  },
  getHistoricalData: async (ticker, period = '6mo') => {
    const response = await api.get(`/market/historical?ticker=${ticker}&period=${period}`);
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
