import axios from "axios";

// Automatically includes /api for all requests
const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_URL}/api`, // ✅ /api included here
  timeout: 900000,
});

api.interceptors.request.use(config => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  res => res,
  err => Promise.reject(err)
);

export default api;