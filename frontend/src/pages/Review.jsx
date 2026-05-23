import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getJob, getQuestions, updateQuestion } from "../api/client.js";
import QuestionCard from "../components/QuestionCard.jsx";

const OPTION_KEYS = ["A", "B", "C", "D"];

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
    return <p className="text-sm text-slate-400">Loading questions…</p>;
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div className="rounded-lg border border-amber-700/60 bg-amber-900/30 px-4 py-3 text-sm text-amber-100">
          {error}
        </div>
        <Link
          to="/"
          className="inline-flex items-center justify-center rounded-lg bg-sky-500 px-5 py-2.5 text-sm font-medium text-white shadow transition hover:bg-sky-400"
        >
          Go to your workspace
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">Extracted questions</h1>
          {job && (
            <p className="mt-1 text-sm text-slate-400">
              <span className="mr-2 inline-flex items-center rounded-full border border-slate-700 bg-slate-800 px-2 py-0.5 text-xs uppercase tracking-wider text-slate-300">
                {job.subject}
              </span>
              <span className="mr-2 text-xs text-slate-500">provider · {job.provider}</span>
              <span className="text-xs text-slate-500">{questions.length} questions</span>
            </p>
          )}
        </div>
        <Link
          to={`/job/${id}`}
          className="text-xs text-sky-400 hover:underline"
        >
          ← Back to job
        </Link>
      </header>

      {questions.length === 0 ? (
        <p className="text-sm text-slate-400">No questions were extracted from this PDF.</p>
      ) : (
        <ol className="space-y-6">
          {questions.map((q, idx) => (
            <li key={q.id}>
              {editingId === q.id ? (
                <QuestionEditor
                  question={q}
                  index={idx + 1}
                  onCancel={() => setEditingId(null)}
                  onSave={(payload) => saveQuestion(q.id, payload)}
                />
              ) : (
                <QuestionCard
                  question={q}
                  index={idx + 1}
                  onEdit={() => setEditingId(q.id)}
                  savedAt={savedAtById[q.id]}
                />
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function QuestionEditor({ question, index, onSave, onCancel }) {
  const [form, setForm] = useState({
    question_text: question.question_text || "",
    option_a: question.option_a || "",
    option_b: question.option_b || "",
    option_c: question.option_c || "",
    option_d: question.option_d || "",
    correct_answer: question.correct_answer || "",
    solution: question.solution || "",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState(null);

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setErr(null);
    try {
      await onSave({
        ...form,
        correct_answer: form.correct_answer || null,
      });
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="rounded-2xl border border-sky-700/60 bg-slate-900/80 p-6 shadow"
    >
      <h2 className="text-sm font-semibold uppercase tracking-wider text-sky-300">
        Editing question {index}
      </h2>

      <label className="mt-4 block">
        <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
          Question text
        </span>
        <textarea
          value={form.question_text}
          onChange={(e) => update("question_text", e.target.value)}
          rows={3}
          className="mt-1 block w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
        />
      </label>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {OPTION_KEYS.map((key) => (
          <label key={key} className="block">
            <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
              Option {key}
            </span>
            <input
              value={form[`option_${key.toLowerCase()}`]}
              onChange={(e) => update(`option_${key.toLowerCase()}`, e.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
            />
          </label>
        ))}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
            Correct answer
          </span>
          <select
            value={form.correct_answer || ""}
            onChange={(e) => update("correct_answer", e.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
          >
            <option value="">— none —</option>
            {OPTION_KEYS.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label className="mt-4 block">
        <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
          Solution (use &lt;br&gt; to separate steps)
        </span>
        <textarea
          value={form.solution}
          onChange={(e) => update("solution", e.target.value)}
          rows={4}
          className="mt-1 block w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
        />
      </label>

      {err && (
        <div className="mt-4 rounded-lg border border-rose-700/60 bg-rose-900/30 px-4 py-2 text-sm text-rose-200">
          {err}
        </div>
      )}

      <div className="mt-6 flex gap-3">
        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-sky-500 px-4 py-2 text-sm font-medium text-white shadow transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
        >
          {saving ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-slate-500"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
