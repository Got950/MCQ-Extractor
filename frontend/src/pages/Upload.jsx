import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

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

  const canUpload = user?.can_upload !== false;

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
        translateY: [12, 0],
        opacity: [0, 1],
        easing: "easeOutQuad",
        duration: 450,
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
      navigate(`/job/${result.id}`);
    } catch (err) {
      setError(err.message || "Upload failed.");
    } finally {
      setSubmitting(false);
    }
  }

  const noProviders = providersLoaded && !providers.gemini && !providers.ollama;

  return (
    <div ref={cardRef} className="rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-xl">
      <h1 className="text-2xl font-semibold text-slate-100">Upload a PDF</h1>
      <p className="mt-2 text-sm text-slate-400">
        We will extract every MCQ, render math properly, and let you review and edit.
        Each account gets one upload. Only you can see your extracted questions.
      </p>

      {!canUpload && (
        <div className="mt-6 rounded-lg border border-sky-700/60 bg-sky-900/30 px-4 py-3 text-sm text-sky-100">
          You have used your one upload for this account. Open your job below to review
          questions, or sign in with another account to upload again.
        </div>
      )}

      {noProviders && (
        <div className="mt-6 rounded-lg border border-amber-700/60 bg-amber-900/30 px-4 py-3 text-sm text-amber-200">
          No LLM providers are configured on the server. Set <code>GEMINI_API_KEY</code> or
          <code> OLLAMA_HOST</code> in the backend <code>.env</code> and restart.
        </div>
      )}

      <form className="mt-8 space-y-6" onSubmit={onSubmit}>
        <DropZone
          file={file}
          dragOver={dragOver}
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
          onPick={() => fileInputRef.current?.click()}
          onChange={(e) => handleFile(e.target.files?.[0])}
        />

        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Subject">
            <select
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="block w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
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
              className="block w-full cursor-not-allowed rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-sm text-slate-400"
            />
          </Field>

          <Field label="Provider">
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="block w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
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

        {error && (
          <div className="rounded-lg border border-rose-700/60 bg-rose-900/30 px-4 py-3 text-sm text-rose-200">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting || !file || noProviders || !canUpload}
          className="inline-flex items-center justify-center rounded-lg bg-sky-500 px-5 py-2.5 text-sm font-medium text-white shadow transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
        >
          {submitting ? "Uploading..." : "Start extraction"}
        </button>
      </form>

      {recentJobs.length > 0 && (
        <section className="mt-10 border-t border-slate-800 pt-8">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
            Your workspace
            {user?.email ? (
              <span className="ml-2 font-normal normal-case text-slate-500">({user.email})</span>
            ) : null}
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Only your uploads appear here. Other accounts cannot see these jobs.
          </p>
          <ul className="mt-4 space-y-3">
            {recentJobs.map((job) => (
              <li
                key={job.id}
                className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-4"
              >
                <p className="text-sm font-medium text-slate-100">
                  {job.subject} · <span className="uppercase text-slate-400">{job.status}</span>
                  {job.status === "done" ? ` · ${job.question_count} questions` : ""}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => navigate(`/job/${job.id}`)}
                    className="rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-200 transition hover:border-sky-600"
                  >
                    Job status
                  </button>
                  {job.status === "done" && job.question_count > 0 && (
                    <button
                      type="button"
                      onClick={() => navigate(`/review/${job.id}`)}
                      className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-emerald-500"
                    >
                      View {job.question_count} questions
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {recentJobs.length === 0 && user && !canUpload && (
        <p className="mt-8 text-sm text-slate-500">No extractions yet for this account.</p>
      )}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="block text-xs font-medium uppercase tracking-wider text-slate-400">
        {label}
      </span>
      <span className="mt-1 block">{children}</span>
    </label>
  );
}

function DropZone({ file, dragOver, inputRef, onDragOver, onDragLeave, onDrop, onPick, onChange }) {
  return (
    <div
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      onClick={onPick}
      className={[
        "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition",
        dragOver
          ? "border-sky-400 bg-sky-500/10 text-sky-100"
          : "border-slate-700 bg-slate-900/50 text-slate-300 hover:border-slate-500",
      ].join(" ")}
    >
      <input
        ref={inputRef}
        id="pdf-file"
        name="pdf-file"
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={onChange}
      />
      {file ? (
        <>
          <p className="text-sm font-medium text-slate-100">{file.name}</p>
          <p className="mt-1 text-xs text-slate-400">
            {(file.size / (1024 * 1024)).toFixed(2)} MB · click or drop to replace
          </p>
        </>
      ) : (
        <>
          <p className="text-sm font-medium">Drag and drop a PDF here</p>
          <p className="mt-1 text-xs text-slate-400">or click to browse · 50 MB max</p>
        </>
      )}
    </div>
  );
}
