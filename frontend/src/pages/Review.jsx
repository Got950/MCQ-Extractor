import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getJob, getQuestions, updateQuestion } from "../api/client.js";
import QuestionCard from "../components/QuestionCard.jsx";

export default function Review() {
  const { id } = useParams();
  const [job, setJob] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [savedAtById, setSavedAtById] = useState({});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [jobData, qs] = await Promise.all([getJob(id), getQuestions(id)]);
        if (cancelled) return;
        setJob(jobData);
        setQuestions(qs);
      } catch (err) {
        if (!cancelled) {
          if (err.status === 404) {
            setError(
              "These questions are not in your account. Open your workspace from the home page — each user only sees their own upload.",
            );
          } else {
            setError(err.message);
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  const saveQuestion = useCallback(async (questionId, payload) => {
    const updated = await updateQuestion(questionId, payload);
    setQuestions((prev) => prev.map((q) => (q.id === updated.id ? updated : q)));
    setEditingId(null);
    setSavedAtById((prev) => ({ ...prev, [questionId]: Date.now() }));
    return updated;
  }, []);

  if (loading) {
    return <p className="text-sm text-gray-500">Loading questions…</p>;
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div className="alert-warning">{error}</div>
        <Link to="/" className="btn-primary">
          Go to workspace
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-gray-900">
            Extracted questions
          </h1>
          {job && (
            <p className="mt-2 flex flex-wrap items-center gap-2 text-sm text-gray-600">
              <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-gray-700">
                {job.subject}
              </span>
              <span className="text-xs text-gray-500">· {job.provider}</span>
              <span className="text-xs font-medium text-gray-700">
                {questions.length} questions
              </span>
            </p>
          )}
        </div>
        <Link
          to={`/job/${id}`}
          className="text-sm font-medium text-zinc-900 underline-offset-2 hover:underline"
        >
          ← Back to job
        </Link>
      </header>

      {questions.length === 0 ? (
        <p className="text-sm text-gray-500">No questions were extracted from this PDF.</p>
      ) : (
        <ol className="space-y-6">
          {questions.map((q, idx) => (
            <li key={q.id}>
              <QuestionCard
                question={q}
                index={idx + 1}
                editing={editingId === q.id}
                onEdit={() => setEditingId(q.id)}
                onCancel={() => setEditingId(null)}
                onSave={(payload) => saveQuestion(q.id, payload)}
                savedAt={savedAtById[q.id]}
              />
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

