import { create } from 'zustand'

const getInitial = () => {
  const saved = localStorage.getItem('theme')
  if (saved) return saved === 'dark'
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

const apply = (dark) => {
  document.documentElement.classList.toggle('dark', dark)
  localStorage.setItem('theme', dark ? 'dark' : 'light')
}

// Apply immediately on load
apply(getInitial())

const useThemeStore = create((set) => ({
  dark: getInitial(),
  toggle: () => set((s) => {
    const next = !s.dark
    apply(next)
    return { dark: next }
  })
}))

export default useThemeStore
