import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import ExtractionStatusBar from "../components/ExtractionStatusBar.jsx";
import { useAuth } from "../auth/AuthContext.jsx";
import { getProviders, listJobs, uploadPdf } from "../api/client.js";

const MAX_BYTES = 50 * 1024 * 1024;
const SUBJECTS = ["Physics", "Chemistry", "Mathematics"];

export default function Upload() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const cardRef = useRef(null);

  const [file, setFile] = useState(null);
  const [subject, setSubject] = useState("Mathematics");
  const [provider, setProvider] = useState("gemini");
  const [providers, setProviders] = useState({ gemini: false, ollama: false });
  const [providersLoaded, setProvidersLoaded] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [recentJobs, setRecentJobs] = useState([]);

  useEffect(() => {
    listJobs()
      .then(setRecentJobs)
      .catch(() => setRecentJobs([]));
  }, [user?.upload_count]);

  useEffect(() => {
    getProviders()
      .then((data) => {
        setProviders(data);
        if (!data.gemini && data.ollama) setProvider("ollama");
        setProvidersLoaded(true);
      })
      .catch((err) => {
        setError(err.message);
        setProvidersLoaded(true);
      });
  }, []);

  useEffect(() => {
    if (cardRef.current && window.anime) {
      window.anime({
        targets: cardRef.current,
        translateY: [8, 0],
        opacity: [0, 1],
        easing: "easeOutQuad",
        duration: 400,
      });
    }
  }, []);

  function handleFile(selected) {
    setError(null);
    if (!selected) {
      setFile(null);
      return;
    }
    if (selected.type !== "application/pdf" && !selected.name.toLowerCase().endsWith(".pdf")) {
      setError("Only PDF files are accepted.");
      setFile(null);
      return;
    }
    if (selected.size > MAX_BYTES) {
      setError("File exceeds the 50 MB limit.");
      setFile(null);
      return;
    }
    setFile(selected);
  }

  async function onSubmit(event) {
    event.preventDefault();
    setError(null);
    if (!file) {
      setError("Please choose a PDF to upload.");
      return;
    }
    if (!providers[provider]) {
      setError(`Provider "${provider}" is not configured on the server.`);
      return;
    }
    setSubmitting(true);
    try {
      const result = await uploadPdf({ file, subject, language: "English", provider });
      await refresh();
      navigate(`/job/${result.id}`, { state: { fileName: file.name } });
    } catch (err) {
      setError(err.message || "Upload failed.");
      setSubmitting(false);
    }
  }

  const noProviders = providersLoaded && !providers.gemini && !providers.ollama;

  return (
    <div ref={cardRef} className="card">
      <h1 className="text-2xl font-semibold tracking-tight text-gray-900">Upload a PDF</h1>
      <p className="mt-2 text-sm text-gray-600">
        Extract multiple-choice questions with AI, review math rendering, and export-ready
        edits. Upload as many PDFs as you need — your workspace stays private.
      </p>

      {submitting && (
        <div className="mt-8">
          <ExtractionStatusBar status="uploading" fileName={file?.name} />
        </div>
      )}

      {noProviders && (
        <div className="alert-warning mt-6">
          No LLM providers are configured on the server. Set <code className="font-mono">GEMINI_API_KEY</code>{" "}
          or <code className="font-mono">OLLAMA_HOST</code> in the backend environment.
        </div>
      )}

      <form className={`space-y-6 ${submitting ? "mt-6" : "mt-8"}`} onSubmit={onSubmit}>
        <DropZone
          file={file}
          dragOver={dragOver}
          disabled={submitting}
          inputRef={fileInputRef}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            handleFile(e.dataTransfer.files?.[0]);
          }}
          onPick={() => !submitting && fileInputRef.current?.click()}
          onChange={(e) => handleFile(e.target.files?.[0])}
        />

        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Subject">
            <select
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              disabled={submitting}
              className="input-field"
            >
              {SUBJECTS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Language">
            <input
              value="English"
              disabled
              className="input-field cursor-not-allowed bg-gray-50 text-gray-500"
            />
          </Field>

          <Field label="Provider">
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              disabled={submitting}
              className="input-field"
            >
              <option value="gemini" disabled={!providers.gemini}>
                Gemini {providers.gemini ? "" : "(not configured)"}
              </option>
              <option value="ollama" disabled={!providers.ollama}>
                Ollama {providers.ollama ? "" : "(not configured)"}
              </option>
            </select>
          </Field>
        </div>

        {error && <div className="alert-error">{error}</div>}

        <button
          type="submit"
          disabled={submitting || !file || noProviders}
          className="btn-primary"
        >
          {submitting ? "Uploading & starting…" : "Start extraction"}
        </button>
      </form>

      {recentJobs.length > 0 && (
        <section className="mt-10 border-t border-gray-200 pt-8">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
            Your workspace
            {user?.email ? (
              <span className="ml-2 font-normal normal-case text-gray-400">({user.email})</span>
            ) : null}
          </h2>
          <p className="mt-1 text-xs text-gray-400">
            Recent extractions — only visible to your account.
          </p>
          <ul className="mt-4 space-y-3">
            {recentJobs.map((job) => (
              <li
                key={job.id}
                className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-4 transition hover:border-gray-300 hover:bg-white"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium text-gray-900">{job.subject}</p>
                  <JobStatusPill status={job.status} />
                </div>
                {job.status === "done" && (
                  <p className="mt-1 text-xs text-gray-500">{job.question_count} questions</p>
                )}
                {job.status === "processing" && job.progress_total > 0 && (
                  <div className="mt-3">
                    <div className="h-1.5 overflow-hidden rounded-full bg-gray-200">
                      <div
                        className="h-full rounded-full bg-zinc-800 transition-all"
                        style={{
                          width: `${Math.round(
                            ((job.progress_current || 0) / job.progress_total) * 100,
                          )}%`,
                        }}
                      />
                    </div>
                    <p className="mt-1 text-xs text-gray-500">
                      {job.progress_current} / {job.progress_total}
                      {job.progress_label ? ` · ${job.progress_label}` : ""}
                    </p>
                  </div>
                )}
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => navigate(`/job/${job.id}`)}
                    className="btn-secondary py-1.5 text-xs"
                  >
                    {job.status === "done" || job.status === "failed" ? "View job" : "View progress"}
                  </button>
                  {job.status === "done" && job.question_count > 0 && (
                    <button
                      type="button"
                      onClick={() => navigate(`/review/${job.id}`)}
                      className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700"
                    >
                      Review questions
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function JobStatusPill({ status }) {
  const styles = {
    pending: "bg-gray-200 text-gray-700",
    queued: "bg-gray-200 text-gray-700",
    processing: "bg-amber-100 text-amber-900",
    done: "bg-emerald-100 text-emerald-800",
    failed: "bg-red-100 text-red-800",
  };
  return (
    <span
      className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${styles[status] || styles.pending}`}
    >
      {status}
    </span>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="label-field">{label}</span>
      <span className="mt-1 block">{children}</span>
    </label>
  );
}

function DropZone({
  file,
  dragOver,
  disabled,
  inputRef,
  onDragOver,
  onDragLeave,
  onDrop,
  onPick,
  onChange,
}) {
  return (
    <div
      onDragOver={disabled ? undefined : onDragOver}
      onDragLeave={onDragLeave}
      onDrop={disabled ? undefined : onDrop}
      onClick={onPick}
      className={[
        "flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition",
        disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer",
        dragOver
          ? "border-zinc-900 bg-zinc-50 text-zinc-900"
          : "border-gray-300 bg-gray-50 text-gray-600 hover:border-gray-400 hover:bg-white",
      ].join(" ")}
    >
      <input
        ref={inputRef}
        id="pdf-file"
        name="pdf-file"
        type="file"
        accept="application/pdf"
        className="hidden"
        disabled={disabled}
        onChange={onChange}
      />
      {file ? (
        <>
          <p className="text-sm font-semibold text-gray-900">{file.name}</p>
          <p className="mt-1 text-xs text-gray-500">
            {(file.size / (1024 * 1024)).toFixed(2)} MB · click or drop to replace
          </p>
        </>
      ) : (
        <>
          <p className="text-sm font-semibold text-gray-800">Drag and drop a PDF here</p>
          <p className="mt-1 text-xs text-gray-500">or click to browse · 50 MB max</p>
        </>
      )}
    </div>
  );
}
