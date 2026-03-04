import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 900000, // 15 minutes
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// NEVER wipe token in the interceptor — let explicit logout do it
api.interceptors.response.use(
  res => res,
  err => Promise.reject(err)
)

export default api
