import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { FileText, Clock, CheckCircle2, XCircle, Plus, BarChart3, ArrowRight, Trash2 } from 'lucide-react'
import api from '../utils/api'
import useAuthStore from '../store/authStore'

function StatCard({ icon: Icon, label, value, color, bg }) {
  return (
    <div className="card flex items-center gap-4">
      <div className={`w-12 h-12 rounded-2xl flex items-center justify-center ${bg}`}>
        <Icon size={22} className={color} />
      </div>
      <div>
        <div className="font-display text-2xl font-bold text-slate-800 dark:text-white">{value}</div>
        <div className="text-sm text-slate-500 dark:text-slate-400 font-medium">{label}</div>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const { user } = useAuthStore()
  const navigate = useNavigate()

  useEffect(() => {
    api.get('/answers/runs').then(r => {
      setRuns(r.data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const totalAnswered = runs.reduce((s, r) => s + (r.summary?.answered || 0), 0)
  const totalNotFound = runs.reduce((s, r) => s + (r.summary?.not_found || 0), 0)

  const handleDelete = async (runId) => {
    if (!window.confirm('Are you sure you want to delete this entire run? This action cannot be undone.')) return
    try {
      await api.delete(`/answers/runs/${runId}`)
      setRuns(prev => prev.filter(r => r.id !== runId))
      toast.success('Run deleted successfully')
    } catch {
      toast.error('Failed to delete run')
    }
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="font-display text-3xl font-bold text-slate-900 dark:text-white">
            Hello, {user?.name?.split(' ')[0]} 👋
          </h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1 text-sm font-medium">Your AI questionnaire activity</p>
        </div>
        <Link to="/workspace" className="btn-primary">
          <Plus size={16} />
          New Questionnaire
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <StatCard icon={FileText} label="Total Runs" value={runs.length} bg="bg-primary-50 dark:bg-primary-950" color="text-primary-600 dark:text-primary-400" />
        <StatCard icon={CheckCircle2} label="Questions Answered" value={totalAnswered} bg="bg-green-50 dark:bg-green-900" color="text-green-600 dark:text-green-400" />
        <StatCard icon={XCircle} label="Not Found" value={totalNotFound} bg="bg-red-50 dark:bg-red-900" color="text-red-500 dark:text-red-400" />
      </div>

      {/* Run History */}
      <div className="card">
        <div className="flex items-center gap-2 mb-6">
          <Clock size={16} className="text-slate-400" />
          <h2 className="font-display font-bold text-slate-700 dark:text-slate-200">Run History</h2>
        </div>

        {loading ? (
          <div className="text-center py-12 text-slate-400">Loading...</div>
        ) : runs.length === 0 ? (
          <div className="text-center py-14">
            <BarChart3 size={42} className="text-slate-200 dark:text-slate-700 mx-auto mb-4" />
            <p className="text-slate-400 dark:text-slate-500 text-sm font-medium mb-4">No runs yet. Upload a questionnaire to get started.</p>
            <Link to="/workspace" className="btn-primary inline-flex">
              <Plus size={16} /> Get Started
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 dark:border-slate-800 text-left">
                  {['Questionnaire', 'Total', 'Answered', 'Not Found', 'Date', ''].map(h => (
                    <th key={h} className="pb-3 font-semibold text-slate-500 dark:text-slate-400 text-xs uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50 dark:divide-slate-800">
                {runs.map(run => (
                  <tr key={run.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors group">
                    <td className="py-3.5 font-semibold text-slate-700 dark:text-slate-200">
                      {run.questionnaire_name || `Run #${run.id}`}
                    </td>
                    <td className="py-3.5 text-slate-500 dark:text-slate-400 font-medium">{run.summary?.total || 0}</td>
                    <td className="py-3.5"><span className="badge-found">{run.summary?.answered || 0}</span></td>
                    <td className="py-3.5"><span className="badge-notfound">{run.summary?.not_found || 0}</span></td>
                    <td className="py-3.5 text-slate-400 dark:text-slate-500 text-xs">
                      {new Date(run.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3.5 text-right">
                      <button
                        onClick={() => navigate(`/runs/${run.id}`)}
                        className="btn-secondary text-xs py-1.5 px-3 opacity-0 group-hover:opacity-100"
                      >
                        View <ArrowRight size={12} />
                      </button>
                      <button
                        onClick={() => handleDelete(run.id)}
                        className="btn-action-red text-xs py-1.5 px-3 opacity-0 group-hover:opacity-100 ml-2"
                      >
                        <Trash2 size={12} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
