import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  CheckCircle2, XCircle, Edit3, RefreshCw, Download,
  ChevronDown, ChevronUp, Loader2, ArrowLeft, FileText,
  BookOpen, Sparkles, Save, X
} from 'lucide-react'
import toast from 'react-hot-toast'
import api from '../utils/api'
import ConfidenceBar from '../components/ConfidenceBar'

function SummaryBanner({ summary }) {
  return (
    <div className="grid grid-cols-3 gap-4 mb-6">
      {[
        { label: 'Total Questions', value: summary?.total || 0, color: 'text-slate-700', bg: 'bg-slate-50' },
        { label: 'Answered', value: summary?.answered || 0, color: 'text-green-700', bg: 'bg-green-50' },
        { label: 'Not Found', value: summary?.not_found || 0, color: 'text-red-600', bg: 'bg-red-50' },
      ].map(({ label, value, color, bg }) => (
        <div key={label} className={`${bg} rounded-xl p-4 text-center`}>
          <div className={`text-2xl font-bold ${color}`}>{value}</div>
          <div className="text-xs text-slate-500 mt-1">{label}</div>
        </div>
      ))}
    </div>
  )
}

function AnswerCard({ answer, onEdit, onRegenerate, selected, onSelect }) {
  const [expanded, setExpanded] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState('')

  const handleSave = () => {
    onEdit({ ...answer, answer_text: editText })
    setEditing(false)
  }

  return (
    <div className={`border rounded-xl overflow-hidden transition-all ${
      selected ? 'border-primary-300 ring-1 ring-primary-200' : 'border-slate-100'
    } bg-white`}>
      {/* Header */}
      <div className="p-4">
        <div className="flex items-start gap-3">
          <input
            type="checkbox"
            checked={selected}
            onChange={e => onSelect(answer.id, e.target.checked)}
            className="mt-1 accent-primary-600"
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-2">
              <span className="text-xs font-bold text-slate-400">Q{answer.question_index + 1}</span>
              {answer.is_found ? (
                <span className="badge-found"><CheckCircle2 size={10} /> Answered</span>
              ) : (
                <span className="badge-notfound"><XCircle size={10} /> Not Found</span>
              )}
              {answer.edited && <span className="badge-edited"><Edit3 size={10} /> Edited</span>}
            </div>
            <p className="text-sm font-semibold text-slate-700 mb-3">{answer.question_text}</p>

            {/* Confidence */}
            {answer.is_found && answer.confidence != null && (
              <div className="mb-3">
                <div className="text-xs text-slate-400 mb-1">Confidence</div>
                <ConfidenceBar value={answer.confidence} />
              </div>
            )}

            {/* Answer */}
            {editing ? (
              <div>
                <textarea
                  value={editText}
                  onChange={e => setEditText(e.target.value)}
                  className="input w-full text-sm min-h-[100px]"
                />
                <div className="flex gap-2 mt-2">
                  <button onClick={handleSave} className="btn-primary text-xs py-1.5 px-3">
                    <Save size={14} /> Save
                  </button>
                  <button onClick={() => setEditing(false)} className="btn-secondary text-xs py-1.5 px-3">
                    <X size={14} /> Cancel
                  </button>
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-600 whitespace-pre-wrap">{answer.answer_text}</p>
            )}
          </div>

          {/* Actions */}
          <div className="flex gap-1 shrink-0">
            {!editing && (
              <button
                onClick={() => { setEditing(true); setEditText(answer.answer_text || '') }}
                className="p-1.5 text-slate-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg"
                title="Edit"
              >
                <Edit3 size={14} />
              </button>
            )}
            <button
              onClick={() => setExpanded(e => !e)}
              className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-50 rounded-lg"
              title="Show evidence"
            >
              {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          </div>
        </div>

        {/* Collapsible: Citations & Evidence */}
        {expanded && (
          <div className="mt-4 pt-4 border-t border-slate-100 ml-7">
            {answer.citations?.length > 0 && (
              <div className="mb-4">
                <div className="flex items-center gap-2 mb-2">
                  <BookOpen size={14} className="text-slate-400" />
                  <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Citations</h4>
                </div>
                <div className="space-y-2">
                  {answer.citations.map((c, i) => (
                    <div key={i} className="bg-slate-50 p-2 rounded-lg text-xs">
                      <p className="font-semibold text-slate-600">{c.doc_name}</p>
                      <p className="text-slate-500 italic">...{c.snippet}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {answer.evidence_snippets?.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles size={14} className="text-slate-400" />
                  <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Evidence Snippets</h4>
                </div>
                <div className="space-y-2">
                  {answer.evidence_snippets.map((s, i) => (
                    <p key={i} className="text-xs text-slate-500 bg-slate-50 p-2 rounded-lg">...{s}...</p>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default function RunDetailPage() {
  const { runId } = useParams()
  const navigate = useNavigate()
  const [run, setRun] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selectedIds, setSelectedIds] = useState([])
  const [regenerating, setRegenerating] = useState(false)
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    api.get(`/answers/runs/${runId}`)
      .then(r => {
        setRun(r.data)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [runId])

  const handleSelect = (id, isSelected) => {
    setSelectedIds(prev => isSelected ? [...prev, id] : prev.filter(i => i !== id))
  }

  const handleSelectAll = (e) => {
    setSelectedIds(e.target.checked ? run.answers.map(a => a.id) : [])
  }

  const handleEdit = async (editedAnswer) => {
    try {
      await api.patch(`/answers/answers/${editedAnswer.id}`, { answer_text: editedAnswer.answer_text })
      setRun(prev => ({
        ...prev,
        answers: prev.answers.map(a => a.id === editedAnswer.id ? { ...editedAnswer, edited: true } : a)
      }))
      toast.success('Answer updated')
    } catch {
      toast.error('Failed to update answer')
    }
  }

  const handleRegenerate = async () => {
    setRegenerating(true)
    try {
      await api.post(`/answers/runs/${runId}/regenerate`, { answer_ids: selectedIds })
      const res = await api.get(`/answers/runs/${runId}`)
      setRun(res.data)
      setSelectedIds([])
      toast.success(`Regenerated ${selectedIds.length} answers`)
    } catch {
      toast.error('Failed to regenerate')
    } finally {
      setRegenerating(false)
    }
  }

  const handleExport = async (format) => {
    setExporting(true)
    try {
      const res = await api.get(`/answers/runs/${runId}/export?format=${format}`, { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')
      link.href = url
      const filename = res.headers['content-disposition'].split('filename=')[1].replace(/"/g, '')
      link.setAttribute('download', filename)
      document.body.appendChild(link)
      link.click()
      link.remove()
      toast.success(`Exported to ${format.toUpperCase()}`)
    } catch {
      toast.error(`Failed to export to ${format.toUpperCase()}`)
    } finally {
      setExporting(false)
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-screen">
      <Loader2 size={32} className="animate-spin text-primary-500" />
    </div>
  )

  if (!run) return null

  return (
    <div className="p-8 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <button onClick={() => navigate('/')} className="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-600 mb-2">
            <ArrowLeft size={14} /> Back to Dashboard
          </button>
          <h1 className="text-xl font-bold text-slate-800">
            {run.questionnaire_name || `Run #${run.id}`}
          </h1>
          <p className="text-sm text-slate-400 mt-0.5">
            {new Date(run.created_at).toLocaleString()}
          </p>
        </div>

        {/* Export buttons */}
        <div className="flex gap-2">
          {selectedIds.length > 0 && (
            <button onClick={handleRegenerate} disabled={regenerating} className="btn-secondary">
              {regenerating ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
              Regenerate ({selectedIds.length})
            </button>
          )}
          <button onClick={() => handleExport('docx')} disabled={exporting} className="btn-secondary">
            <Download size={15} /> DOCX
          </button>
          <button onClick={() => handleExport('pdf')} disabled={exporting} className="btn-primary">
            <Download size={15} /> PDF
          </button>
        </div>
      </div>

      <SummaryBanner summary={run.summary} />

      {/* All answers */}
      <div className="space-y-4">
        <div className="flex items-center gap-3 px-4">
          <input
            type="checkbox"
            checked={selectedIds.length > 0 && selectedIds.length === run.answers.length}
            onChange={handleSelectAll}
            className="accent-primary-600"
          />
          <label className="text-sm font-semibold text-slate-600">Select All</label>
        </div>

        {run.answers.map(answer => (
          <AnswerCard
            key={answer.id}
            answer={answer}
            onEdit={handleEdit}
            onRegenerate={handleRegenerate}
            selected={selectedIds.includes(answer.id)}
            onSelect={handleSelect}
          />
        ))}
      </div>
    </div>
  )
}
