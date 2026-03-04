import { useState, useEffect } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, FileQuestion, LogOut, Sun, Moon, ChevronUp, User } from 'lucide-react'
import useAuthStore from '../store/authStore'
import useThemeStore from '../store/themeStore'

// Generate a consistent color from a string
function stringToColor(str) {
  const colors = [
    'bg-violet-500', 'bg-blue-500', 'bg-emerald-500',
    'bg-rose-500',   'bg-amber-500', 'bg-cyan-500',
    'bg-pink-500',   'bg-indigo-500','bg-teal-500',
  ]
  let hash = 0
  for (let i = 0; i < (str || '').length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash)
  }
  return colors[Math.abs(hash) % colors.length]
}

function Avatar({ name, size = 'md' }) {
  const color = stringToColor(name)
  const letter = (name || '?')[0].toUpperCase()
  const sz = size === 'sm' ? 'w-7 h-7 text-xs' : 'w-9 h-9 text-sm'
  return (
    <div className={`${sz} ${color} rounded-full flex items-center justify-center text-white font-bold shrink-0 select-none`}>
      {letter}
    </div>
  )
}

export default function Layout() {
  const { user, logout, fetchMe } = useAuthStore()

  useEffect(() => { fetchMe() }, [])
  const { dark, toggle } = useThemeStore()
  const [showUserCard, setShowUserCard] = useState(false)

  const handleLogout = () => { logout() }

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-950">
      {/* Sidebar */}
      <aside className="w-64 bg-white dark:bg-slate-900 border-r border-slate-100 dark:border-slate-800 flex flex-col shadow-sm">

        {/* Logo */}
        <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800">
          <img
            src="/logo.jpg"
            alt="Ansvara"
            className="h-8 w-auto object-contain"
          />
          
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          <NavLink to="/" end className={({ isActive }) =>
            `nav-link ${isActive ? 'nav-link-active' : 'nav-link-inactive'}`}>
            <LayoutDashboard size={16} /> Dashboard
          </NavLink>
          <NavLink to="/workspace" className={({ isActive }) =>
            `nav-link ${isActive ? 'nav-link-active' : 'nav-link-inactive'}`}>
            <FileQuestion size={16} /> New Questionnaire
          </NavLink>
        </nav>

        {/* Bottom */}
        <div className="px-3 py-3 border-t border-slate-100 dark:border-slate-800 space-y-1">
          {/* Theme toggle */}
          <button onClick={toggle}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 transition-all">
            {dark
              ? <Sun size={16} className="text-amber-400" />
              : <Moon size={16} />}
            {dark ? 'Light Mode' : 'Dark Mode'}
          </button>

          {/* User card toggle */}
          <div className="relative">
            <button
              onClick={() => setShowUserCard(v => !v)}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 transition-all"
            >
              <Avatar name={user?.name} />
              <div className="flex-1 min-w-0 text-left">
                <div className="text-sm font-semibold text-slate-700 dark:text-slate-200 truncate">
                  {user?.name || 'User'}
                </div>
                <div className="text-xs text-slate-400 truncate">{user?.email || ''}</div>
              </div>
              <ChevronUp size={14} className={`text-slate-400 transition-transform ${showUserCard ? '' : 'rotate-180'}`} />
            </button>

            {/* Popup card */}
            {showUserCard && (
              <div className="absolute bottom-full left-0 right-0 mb-1 bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 rounded-2xl shadow-xl p-4 z-50">
                <div className="flex items-center gap-3 mb-4">
                  <Avatar name={user?.name} size="md" />
                  <div className="min-w-0">
                    <div className="font-bold text-slate-800 dark:text-white text-sm truncate">{user?.name}</div>
                    <div className="text-xs text-slate-400 truncate">{user?.email}</div>
                  </div>
                </div>
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-semibold text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950 transition-colors"
                >
                  <LogOut size={15} /> Sign Out
                </button>
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto" onClick={() => setShowUserCard(false)}>
        <Outlet />
      </main>
    </div>
  )
}
