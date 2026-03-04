import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, File, X } from 'lucide-react'

export default function FileDropzone({ onDrop, accept, label, files, onRemove, multiple = false }) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept,
    multiple
  })

  return (
    <div>
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
          isDragActive
            ? 'border-primary-500 bg-primary-50'
            : 'border-slate-200 hover:border-primary-400 hover:bg-slate-50'
        }`}
      >
        <input {...getInputProps()} />
        <Upload size={24} className="mx-auto text-slate-400 mb-2" />
        <p className="text-sm font-medium text-slate-600">
          {isDragActive ? 'Drop it here!' : label}
        </p>
        <p className="text-xs text-slate-400 mt-1">PDF, DOCX, TXT, XLSX supported</p>
      </div>

      {files && files.length > 0 && (
        <div className="mt-3 space-y-2">
          {files.map((f, i) => (
            <div key={i} className="flex items-center gap-2 bg-slate-50 rounded-lg px-3 py-2 text-sm">
              <File size={14} className="text-primary-500 shrink-0" />
              <span className="flex-1 truncate text-slate-700">{f.name}</span>
              {onRemove && (
                <button onClick={() => onRemove(i)} className="text-slate-400 hover:text-red-500">
                  <X size={14} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
