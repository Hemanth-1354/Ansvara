import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Loader2,
  FileText,
  Database,
  Sparkles,
  CheckCircle2,
  Trash2,
  Info,
} from "lucide-react";
import toast from "react-hot-toast";
import api from "../utils/api";
import FileDropzone from "../components/FileDropzone";

function StepBadge({ step, current, label }) {
  const done = current > step;
  const active = current === step;
  return (
    <div
      className={`flex items-center gap-2 text-sm font-semibold
      ${
        active
          ? "text-primary-600 dark:text-primary-400"
          : done
          ? "text-green-600 dark:text-green-400"
          : "text-slate-400 dark:text-slate-600"
      }`}
    >
      <div
        className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold
        ${
          active
            ? "bg-primary-600 text-white"
            : done
            ? "bg-green-500 text-white"
            : "bg-slate-200 dark:bg-slate-700 text-slate-500 dark:text-slate-400"
        }`}
      >
        {done ? "✓" : step}
      </div>
      {label}
    </div>
  );
}

export default function WorkspacePage() {
  const [step, setStep] = useState(1);
  const [questFile, setQuestFile] = useState(null);
  const [refFiles, setRefFiles] = useState([]);
  const [uploadedRefDocs, setUploadedRefDocs] = useState([]);
  const [uploadedQuestionnaire, setUploadedQuestionnaire] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api
      .get("/documents/")
      .then((r) => setUploadedRefDocs(r.data))
      .catch(() => {});
  }, []);

  const uploadQuestionnaire = async () => {
    if (!questFile) return toast.error("Please select a questionnaire file");
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", questFile);
      const res = await api.post("/questionnaires/upload", fd);
      setUploadedQuestionnaire(res.data);
      toast.success(`Parsed ${res.data.question_count} questions`);
      setStep(2);
    } catch (err) {
      toast.error(
        err.response?.data?.detail || "Upload failed — are you logged in?"
      );
    } finally {
      setUploading(false);
    }
  };

  const uploadRefDocs = async () => {
    if (refFiles.length === 0 && uploadedRefDocs.length === 0)
      return toast.error("Please upload at least one reference document");
    setUploading(true);
    try {
      for (const file of refFiles) {
        const fd = new FormData();
        fd.append("file", file);
        await api.post("/documents/upload", fd);
      }
      const res = await api.get("/documents/");
      setUploadedRefDocs(res.data);
      setRefFiles([]);
      toast.success("Reference documents ready");
      setStep(3);
    } catch (err) {
      toast.error("Failed to upload documents");
    } finally {
      setUploading(false);
    }
  };

  const deleteRefDoc = async (id) => {
    await api.delete(`/documents/${id}`);
    setUploadedRefDocs((prev) => prev.filter((d) => d.id !== id));
  };

  const generateAnswers = async () => {
    if (!uploadedQuestionnaire) return toast.error("No questionnaire uploaded");
    setGenerating(true);
    try {
      const res = await api.post("/answers/generate", {
        questionnaire_id: uploadedQuestionnaire.id,
      });
      if (res.status === 200) {
        toast.success(
          (t) => (
            <div className="flex items-center gap-3">
              <span className="font-medium">
                Generated {res.data.summary.answered} answers!
              </span>
              <button
                onClick={() => {
                  navigate(`/runs/${res.data.run_id}`);
                  toast.dismiss(t.id);
                }}
                className="btn-primary py-1.5 px-3 text-xs"
              >
                View
              </button>
            </div>
          ),
          {
            duration: 6000,
          }
        );
        setStep(1);
        setQuestFile(null);
        setUploadedQuestionnaire(null);
      } else {
        toast.error(res.data.detail || "Generation failed");
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      console.error("Generation failed:", err.response || err);
      if (detail) {
        toast.error(detail);
      } else {
        toast.error("An unknown error occurred during generation.");
      }
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="font-display text-2xl font-bold text-slate-800 dark:text-white">
          New Questionnaire Run
        </h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1 text-sm font-medium">
          Upload your questionnaire + reference docs → AI generates grounded
          answers with citations
        </p>
      </div>

      {/* Steps indicator */}
      <div className="flex items-center gap-4 mb-8 p-4 bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm">
        <StepBadge step={1} current={step} label="Questionnaire" />
        <div className="flex-1 h-px bg-slate-100 dark:bg-slate-800" />
        <StepBadge step={2} current={step} label="Reference Docs" />
        <div className="flex-1 h-px bg-slate-100 dark:bg-slate-800" />
        <StepBadge step={3} current={step} label="Generate" />
      </div>

      {/* Step 1 */}
      <div
        className={`card mb-4 ${
          step !== 1 ? "opacity-60 pointer-events-none" : ""
        }`}
      >
        <div className="flex items-center gap-2 mb-1">
          <FileText size={18} className="text-primary-600" />
          <h2 className="font-display font-bold text-slate-700 dark:text-slate-200">
            Step 1: Upload Questionnaire
          </h2>
        </div>
        <p className="text-xs text-slate-400 mb-4 ml-6">
          The file containing the <strong>questions</strong> you need to answer
          (e.g. a vendor security form)
        </p>

        {uploadedQuestionnaire ? (
          <div className="flex items-center gap-3 bg-green-50 dark:bg-green-900 text-green-700 dark:text-green-300 rounded-xl p-3 text-sm font-semibold">
            <CheckCircle2 size={16} />
            {uploadedQuestionnaire.filename}
            <span className="font-normal text-green-600 dark:text-green-400 ml-1">
              — {uploadedQuestionnaire.question_count} questions found
            </span>
          </div>
        ) : (
          <>
            <FileDropzone
              onDrop={(files) => files[0] && setQuestFile(files[0])}
              label="Drop your questionnaire here, or click to browse"
              files={questFile ? [questFile] : []}
              onRemove={() => setQuestFile(null)}
            />
            <button
              onClick={uploadQuestionnaire}
              disabled={!questFile || uploading}
              className="btn-primary mt-4"
            >
              {uploading && <Loader2 size={15} className="animate-spin" />}
              Upload & Parse Questions
            </button>
          </>
        )}
      </div>

      {/* Step 2 */}
      <div
        className={`card mb-4 ${
          step < 2 ? "opacity-40 pointer-events-none" : ""
        }`}
      >
        <div className="flex items-center gap-2 mb-1">
          <Database size={18} className="text-primary-600" />
          <h2 className="font-display font-bold text-slate-700 dark:text-slate-200">
            Step 2: Reference Documents
          </h2>
        </div>
        <p className="text-xs text-slate-400 mb-4 ml-6">
          Your company's source-of-truth docs the AI reads to{" "}
          <strong>answer</strong> the questions (policies, SOC reports,
          handbooks)
        </p>

        <div className="flex items-start gap-2 bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 rounded-xl p-3 text-xs font-medium mb-4">
          <Info size={13} className="shrink-0 mt-0.5" />
          Previously uploaded documents are reused automatically.
        </div>

        {uploadedRefDocs.length > 0 && (
          <div className="mb-4 space-y-2">
            <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
              Existing Docs
            </p>
            {uploadedRefDocs.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center gap-2 bg-slate-50 dark:bg-slate-800 rounded-xl px-3 py-2.5 text-sm"
              >
                <FileText size={14} className="text-primary-400 shrink-0" />
                <span className="flex-1 truncate text-slate-700 dark:text-slate-300 font-medium">
                  {doc.filename}
                </span>
                <span className="text-slate-400 text-xs">
                  {(doc.char_count / 1000).toFixed(1)}k chars
                </span>
                <button
                  onClick={() => deleteRefDoc(doc.id)}
                  className="text-slate-300 hover:text-red-500 transition-colors"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}

        <FileDropzone
          onDrop={(files) => setRefFiles((prev) => [...prev, ...files])}
          label="Add reference documents (PDFs, DOCX, TXT)"
          files={refFiles}
          onRemove={(i) =>
            setRefFiles((prev) => prev.filter((_, idx) => idx !== i))
          }
          multiple
        />
        <button
          onClick={uploadRefDocs}
          disabled={uploading}
          className="btn-primary mt-4"
        >
          {uploading && <Loader2 size={15} className="animate-spin" />}
          {refFiles.length > 0 ? "Upload & Continue" : "Continue →"}
        </button>
      </div>

      {/* Step 3 */}
      <div
        className={`card ${step < 3 ? "opacity-40 pointer-events-none" : ""}`}
      >
        <div className="flex items-center gap-2 mb-1">
          <Sparkles size={18} className="text-primary-600" />
          <h2 className="font-display font-bold text-slate-700 dark:text-slate-200">
            Step 3: Generate Answers
          </h2>
        </div>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-5 ml-6">
          AI reads your reference docs and answers each question with citations
          and confidence scores. This usually takes 10–30 seconds.
        </p>
        <button
          onClick={generateAnswers}
          disabled={generating}
          className="btn-primary w-full justify-center py-3 text-base"
        >
          {generating ? (
            <>
              <Loader2 size={18} className="animate-spin" /> Generating answers…
            </>
          ) : (
            <>
              <Sparkles size={18} /> Generate Answers with AI
            </>
          )}
        </button>
      </div>
    </div>
  );
}
