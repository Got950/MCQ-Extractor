import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getJob, retryJob } from "../api/client.js";

const POLL_MS = 5000;

export default function Job() {
  const { id } = useParams();
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const [retrying, setRetrying] = useState(false);
  const [pollKey, setPollKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timer = null;

    async function tick() {
      try {
        const data = await getJob(id);
        if (cancelled) return;
        setJob(data);
        setError(null);
        if (data.status !== "done" && data.status !== "failed") {
          timer = setTimeout(tick, POLL_MS);
        }
      } catch (err) {
        if (cancelled) return;
        setJob(null);
        if (err.status === 404) {
          setError(
            "This extraction belongs to another account (or the link is old). " +
              "Sign in with the account that uploaded it, or open your own jobs from the home page.",
          );
          return;
        }
        setError(err.message);
        if (err.status === 401) return;
        timer = setTimeout(tick, POLL_MS);
      }
    }

    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [id, pollKey]);

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-xl">
      <h1 className="text-2xl font-semibold text-slate-100">Extraction job</h1>
      <p className="mt-1 text-xs text-slate-500">Job ID · {id}</p>

      {error && !job && (
        <div className="mt-6 space-y-4">
          <div className="rounded-lg border border-amber-700/60 bg-amber-900/30 px-4 py-3 text-sm text-amber-100">
            {error}
          </div>
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-lg bg-sky-500 px-5 py-2.5 text-sm font-medium text-white shadow transition hover:bg-sky-400"
          >
            Go to your uploads
          </Link>
        </div>
      )}

      {error && job && (
        <div className="mt-6 rounded-lg border border-rose-700/60 bg-rose-900/30 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      )}

      {!job && !error ? (
        <p className="mt-8 text-sm text-slate-400">Loading job status…</p>
      ) : !job ? null : (
        <>
          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            <Meta label="Subject" value={job.subject} />
            <Meta label="Language" value={job.language} />
            <Meta label="Provider" value={job.provider} />
          </div>

          <div className="mt-8">
            <StatusBadge status={job.status} />
            <p className="mt-3 text-sm text-slate-400">
              {job.status === "processing" && job.progress_total
                ? `Processing section ${job.progress_current} of ${job.progress_total}${
                    job.progress_label ? ` (${job.progress_label})` : ""
                  }…`
                : describeStatus(job.status)}
            </p>
          </div>

          {job.status === "failed" && job.error_message && (
            <div className="mt-6 space-y-4">
              <div className="rounded-lg border border-rose-700/60 bg-rose-900/30 px-4 py-3 text-sm text-rose-200">
                {job.error_message}
              </div>
              <button
                type="button"
                disabled={retrying}
                onClick={async () => {
                  setRetrying(true);
                  setError(null);
                  try {
                    const data = await retryJob(id);
                    setJob(data);
                    setPollKey((k) => k + 1);
                  } catch (err) {
                    setError(err.message);
                  } finally {
                    setRetrying(false);
                  }
                }}
                className="inline-flex items-center justify-center rounded-lg bg-sky-500 px-5 py-2.5 text-sm font-medium text-white shadow transition hover:bg-sky-400 disabled:opacity-50"
              >
                {retrying ? "Retrying…" : "Retry extraction"}
              </button>
              <p className="text-xs text-slate-500">
                Uses your current API key. Upload a new PDF from home if you changed files.
              </p>
            </div>
          )}

          {job.status === "done" && (
            <div className="mt-8">
              <Link
                to={`/review/${job.id}`}
                className="inline-flex items-center justify-center rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-medium text-white shadow transition hover:bg-emerald-400"
              >
                View {job.question_count} extracted questions
              </Link>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Meta({ label, value }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-3">
      <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 text-sm text-slate-100">{value}</p>
    </div>
  );
}

function StatusBadge({ status }) {
  const styles = {
    pending: "border-slate-600 bg-slate-800 text-slate-200",
    queued: "border-slate-600 bg-slate-800 text-slate-200",
    processing: "border-sky-600/60 bg-sky-900/40 text-sky-200",
    done: "border-emerald-600/60 bg-emerald-900/40 text-emerald-200",
    failed: "border-rose-600/60 bg-rose-900/40 text-rose-200",
  };
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium uppercase tracking-wider ${styles[status] || styles.pending}`}
    >
      <span className="inline-block h-2 w-2 rounded-full bg-current" />
      {status}
    </span>
  );
}

function describeStatus(status) {
  switch (status) {
    case "pending":
    case "queued":
      return "Job queued. Waiting to start.";
    case "processing":
      return "LLM is parsing the PDF. This usually takes 20–90 seconds.";
    case "done":
      return "Extraction complete. You can review and edit the questions.";
    case "failed":
      return "Extraction failed. See the error message below.";
    default:
      return "";
  }
}
