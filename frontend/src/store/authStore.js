import { create } from 'zustand'
import api from '../utils/api'

const useAuthStore = create((set) => ({
  user: null,
  isLoading: false,

  login: async (email, password) => {
    set({ isLoading: true })
    try {
      const params = new URLSearchParams()
      params.append('username', email)
      params.append('password', password)
      const res = await api.post('/auth/login', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      })
      localStorage.setItem('token', res.data.access_token)
      set({ user: res.data.user, isLoading: false })
    } catch (err) {
      set({ isLoading: false })
      throw err
    }
  },

  register: async (email, name, password) => {
    set({ isLoading: true })
    try {
      const res = await api.post('/auth/register', { email, name, password })
      localStorage.setItem('token', res.data.access_token)
      set({ user: res.data.user, isLoading: false })
    } catch (err) {
      set({ isLoading: false })
      throw err
    }
  },

  // Called lazily inside Layout — never on app startup
  fetchMe: async () => {
    try {
      const res = await api.get('/auth/me')
      set({ user: res.data })
    } catch {
      // intentionally silent — do NOT touch localStorage here
    }
  },

  logout: () => {
    localStorage.removeItem('token')
    set({ user: null })
    window.location.replace('/login')
  }
}))

export default useAuthStore
