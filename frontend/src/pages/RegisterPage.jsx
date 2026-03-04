import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Sparkles, Loader2, Eye, EyeOff, CheckCircle2, XCircle, Sun, Moon, AlertCircle } from 'lucide-react'
import useAuthStore from '../store/authStore'
import useThemeStore from '../store/themeStore'

function Rule({ ok, label }) {
  return (
    <div className={`flex items-center gap-1.5 text-xs font-medium ${ok ? 'text-green-600 dark:text-green-400' : 'text-slate-400 dark:text-slate-500'}`}>
      {ok ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
      {label}
    </div>
  )
}

function validate(pw) {
  return {
    length: pw.length >= 8,
    upper:  /[A-Z]/.test(pw),
    lower:  /[a-z]/.test(pw),
    number: /[0-9]/.test(pw),
  }
}

export default function RegisterPage() {
  const [name, setName]         = useState('')
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw]     = useState(false)
  const [touched, setTouched]   = useState(false)
  const [error, setError]       = useState('')
  const { register, isLoading } = useAuthStore()
  const { dark, toggle }        = useThemeStore()
  const navigate                = useNavigate()

  const rules    = validate(password)
  const allValid = Object.values(rules).every(Boolean)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setTouched(true)
    setError('')
    if (!allValid) { setError('Password does not meet all requirements'); return }
    try {
      await register(email, name, password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed')
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
          <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-600 rounded-2xl mb-5 shadow-lg">
            <Sparkles size={30} className="text-white" />
          </div>
          <h1 className="font-display text-3xl font-bold text-slate-900 dark:text-white">Create account</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-2 text-sm font-medium">Get started with QuestionnAIre</p>
        </div>

        <div className="card shadow-xl shadow-slate-100 dark:shadow-none">
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="flex items-center gap-2 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 rounded-xl px-4 py-3 text-sm font-medium">
                <AlertCircle size={16} className="shrink-0" />{error}
              </div>
            )}
            <div>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-1.5">Full Name</label>
              <input type="text" className="input" value={name}
                onChange={e => setName(e.target.value)} placeholder="Jane Smith" required />
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-1.5">Email</label>
              <input type="email" className="input" value={email}
                onChange={e => setEmail(e.target.value)} placeholder="you@company.com" required autoComplete="email" />
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-1.5">Password</label>
              <div className="relative">
                <input type={showPw ? 'text' : 'password'}
                  className={`input pr-10 ${touched && !allValid ? 'input-error' : ''}`}
                  value={password}
                  onChange={e => { setPassword(e.target.value); setTouched(true); setError('') }}
                  placeholder="Create a strong password" required autoComplete="new-password" />
                <button type="button" onClick={() => setShowPw(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {(touched || password) && (
                <div className="mt-2.5 grid grid-cols-2 gap-1.5 bg-slate-50 dark:bg-slate-800 rounded-xl p-3">
                  <Rule ok={rules.length} label="Min 8 characters" />
                  <Rule ok={rules.upper}  label="Uppercase letter" />
                  <Rule ok={rules.lower}  label="Lowercase letter" />
                  <Rule ok={rules.number} label="Number (0–9)" />
                </div>
              )}
            </div>
            <button type="submit" className="btn-primary w-full justify-center py-3 text-base" disabled={isLoading}>
              {isLoading && <Loader2 size={17} className="animate-spin" />}
              {isLoading ? 'Creating account...' : 'Create Account'}
            </button>
          </form>
          <div className="mt-5 pt-5 border-t border-slate-100 dark:border-slate-800 text-center">
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Already have an account?{' '}
              <Link to="/login" className="text-primary-600 dark:text-primary-400 font-semibold hover:underline">Sign in</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
