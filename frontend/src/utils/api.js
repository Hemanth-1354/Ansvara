import axios from 'axios'

base_url = process.env.NEXT_PUBLIC_API_URL
// # Set this in your .env file, e.g. REACT_APP_API_URL=http://localhost:8000
const api = axios.create({
  baseURL: `${base_url}/api`,
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





// // import axios from 'axios'

// // const api = axios.create({
// //   baseURL: process.env.NEXT_PUBLIC_API_URL, // Use your backend
// //   timeout: 900000, // 15 minutes
// // })

// api.interceptors.request.use(config => {
//   const token = localStorage.getItem('token')
//   if (token) config.headers.Authorization = `Bearer ${token}`
//   return config
// })

// api.interceptors.response.use(
//   res => res,
//   err => Promise.reject(err)
// )

// export default api