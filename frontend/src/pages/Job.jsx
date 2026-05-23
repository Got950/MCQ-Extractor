import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import ExtractionStatusBar from "../components/ExtractionStatusBar.jsx";
import { getJob, retryJob } from "../api/client.js";

const POLL_ACTIVE_MS = 1500;
const POLL_IDLE_MS = 5000;

export default function Job() {
  const { id } = useParams();
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const [retrying, setRetrying] = useState(false);
  const [pollKey, setPollKey] = useState(0);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (!job || job.status === "done" || job.status === "failed") return;
    const t = setInterval(() => setNow(Date.now()), 10000);
    return () => clearInterval(t);
  }, [job?.status, job?.id]);

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
          const delay =
            data.status === "processing" || data.status === "queued" ? POLL_ACTIVE_MS : POLL_IDLE_MS;
          timer = setTimeout(tick, delay);
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
        timer = setTimeout(tick, POLL_IDLE_MS);
      }
    }

    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [id, pollKey]);

  const inProgress = job && job.status !== "done" && job.status !== "failed";

  const elapsedMinutes = job?.created_at
    ? Math.floor((now - new Date(job.created_at).getTime()) / 60000)
    : 0;

  return (
    <div className="card">
      <h1 className="text-2xl font-semibold tracking-tight text-gray-900">Extraction job</h1>
      <p className="mt-1 text-xs text-gray-400">Job ID · {id}</p>

      {error && !job && (
        <div className="mt-6 space-y-4">
          <div className="alert-warning">{error}</div>
          <Link to="/" className="btn-primary">
            Go to workspace
          </Link>
        </div>
      )}

      {error && job && <div className="alert-error mt-6">{error}</div>}

      {!job && !error ? (
        <div className="mt-8">
          <ExtractionStatusBar status="queued" />
          <p className="mt-4 text-sm text-gray-500">Loading job status…</p>
        </div>
      ) : !job ? null : (
        <>
          <div className="mt-8">
            <ExtractionStatusBar
              status={job.status}
              progressCurrent={job.progress_current ?? 0}
              progressTotal={job.progress_total ?? 0}
              progressLabel={job.progress_label}
              elapsedMinutes={inProgress ? elapsedMinutes : undefined}
              questionCount={job.status === "done" ? job.question_count : undefined}
            />
          </div>

          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            <Meta label="Subject" value={job.subject} />
            <Meta label="Language" value={job.language} />
            <Meta label="Provider" value={job.provider} />
          </div>

          {inProgress && (
            <p className="mt-4 text-sm text-gray-500">
              Please keep this page open. Chemistry or large exam PDFs often take{" "}
              <strong className="font-medium text-gray-700">5–15 minutes</strong> on the first
              run. Progress updates as each page is processed.
              {elapsedMinutes >= 8 && (
                <span className="mt-2 block text-amber-800">
                  Still running after {elapsedMinutes} minutes — if it exceeds 20 minutes,
                  use Retry extraction or try a shorter PDF.
                </span>
              )}
            </p>
          )}

          {job.status === "failed" && job.error_message && (
            <div className="mt-6 space-y-4">
              <div className="alert-error">{job.error_message}</div>
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
                className="btn-primary"
              >
                {retrying ? "Retrying…" : "Retry extraction"}
              </button>
              <p className="text-xs text-gray-500">
                Uses your current API key. Upload a new PDF from home if you changed files.
              </p>
            </div>
          )}

          {job.status === "done" && (
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to={`/review/${job.id}`} className="btn-success">
                View {job.question_count} extracted questions
              </Link>
              <Link to="/" className="btn-secondary">
                Upload another PDF
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
    <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
      <p className="label-field">{label}</p>
      <p className="mt-1 text-sm font-medium text-gray-900">{value}</p>
    </div>
  );
}
