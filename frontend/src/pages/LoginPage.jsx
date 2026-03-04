import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Loader2, Eye, EyeOff, Sun, Moon, AlertCircle } from 'lucide-react'
import useAuthStore from '../store/authStore'
import useThemeStore from '../store/themeStore'

export default function LoginPage() {
  const [email, setEmail]     = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw]   = useState(false)
  const [error, setError]     = useState('')
  const { login, isLoading }  = useAuthStore()
  const { dark, toggle }      = useThemeStore()
  const navigate              = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await login(email, password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid email or password')
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 via-white to-slate-100 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 flex items-center justify-center p-4 transition-colors duration-200">
      <button onClick={toggle}
        className="fixed top-4 right-4 p-2.5 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-500 dark:text-amber-400 hover:scale-105 transition-all shadow-sm">
        {dark ? <Sun size={18} /> : <Moon size={18} />}
      </button>

      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          {/* Logo + Name side by side */}
          <div className="inline-flex items-center gap-3 mb-5">
            <img src="/logo-final.webp" alt="Ansvara" className="w-14 h-14 rounded-2xl object-cover shadow-lg" />
            <span className="font-display text-3xl font-bold text-slate-900 dark:text-white">Ansvara</span>
          </div>
          <h1 className="font-display text-2xl font-bold text-slate-900 dark:text-white">Welcome back</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-2 text-sm font-medium">Sign in to continue</p>
        </div>

        <div className="card shadow-xl shadow-slate-100 dark:shadow-none">
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="flex items-center gap-2 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 rounded-xl px-4 py-3 text-sm font-medium">
                <AlertCircle size={16} className="shrink-0" />
                {error}
              </div>
            )}
            <div>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-1.5">Email</label>
              <input type="email" className={`input ${error ? 'input-error' : ''}`}
                value={email} onChange={e => { setEmail(e.target.value); setError('') }}
                placeholder="you@company.com" required autoComplete="email" />
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-1.5">Password</label>
              <div className="relative">
                <input type={showPw ? 'text' : 'password'}
                  className={`input pr-10 ${error ? 'input-error' : ''}`}
                  value={password} onChange={e => { setPassword(e.target.value); setError('') }}
                  placeholder="••••••••" required autoComplete="current-password" />
                <button type="button" onClick={() => setShowPw(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
            <button type="submit" className="btn-primary w-full justify-center py-3 text-base" disabled={isLoading}>
              {isLoading && <Loader2 size={17} className="animate-spin" />}
              {isLoading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>
          <div className="mt-5 pt-5 border-t border-slate-100 dark:border-slate-800 text-center">
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Don't have an account?{' '}
              <Link to="/register" className="text-primary-600 dark:text-primary-400 font-semibold hover:underline">Create one</Link>
            </p>
          </div>
        </div>
        <p className="text-center text-xs text-slate-400 dark:text-slate-600 mt-6 font-medium">Powered by Groq · LLaMA 3.1</p>
      </div>
    </div>
  )
}
