import { useEffect, useRef, useState } from "react";

const OPTION_KEYS = ["A", "B", "C", "D"];
const SUBJECT_OPTIONS = ["Physics", "Chemistry", "Mathematics", "General"];

function typesetCard(cardEl) {
  if (cardEl && window.MathJax?.typesetPromise) {
    window.MathJax.typesetPromise([cardEl]).catch(() => {});
  }
}

function subjectBadgeClass(subject) {
  switch (subject) {
    case "Physics":
      return "bg-blue-500/10 text-blue-400 border border-blue-500/20";
    case "Chemistry":
      return "bg-green-500/10 text-green-400 border border-green-500/20";
    case "Mathematics":
      return "bg-purple-500/10 text-purple-400 border border-purple-500/20";
    default:
      return "bg-slate-500/10 text-slate-400 border border-slate-500/20";
  }
}

function SubjectBadge({ subject }) {
  const label = SUBJECT_OPTIONS.includes(subject) ? subject : "General";
  return (
    <span
      className={[
        "rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide",
        subjectBadgeClass(label),
      ].join(" ")}
    >
      {label}
    </span>
  );
}

export default function QuestionCard({
  question,
  index,
  onEdit,
  savedAt,
  editing = false,
  onSave,
  onCancel,
}) {
  if (editing) {
    return (
      <QuestionCardEditor
        question={question}
        index={index}
        onSave={onSave}
        onCancel={onCancel}
      />
    );
  }

  const cardRef = useRef(null);

  useEffect(() => {
    typesetCard(cardRef.current);
  }, [question, savedAt]);

  return (
    <article ref={cardRef} className="card !p-6">
      <div className="flex items-start justify-between gap-4">
        <h2 className="label-field">Question {index}</h2>
        <div className="flex shrink-0 items-center gap-2">
          <SubjectBadge subject={question.subject} />
          <button type="button" onClick={onEdit} className="btn-secondary py-1 text-xs">
            Edit
          </button>
        </div>
      </div>

      <div
        className="prose prose-sm mt-4 max-w-none text-gray-900"
        dangerouslySetInnerHTML={{ __html: question.question_text || "" }}
      />

      <ul className="mt-4 space-y-2">
        {OPTION_KEYS.map((key) => {
          const value = question[`option_${key.toLowerCase()}`];
          const correct = question.correct_answer === key;
          return (
            <li
              key={key}
              className={[
                "flex gap-3 rounded-lg border px-4 py-2.5 text-sm",
                correct
                  ? "border-emerald-300 bg-emerald-50 text-emerald-950"
                  : "border-gray-200 bg-gray-50 text-gray-800",
              ].join(" ")}
            >
              <span className="font-bold text-gray-900">{key}.</span>
              <div className="flex-1" dangerouslySetInnerHTML={{ __html: value || "" }} />
              {correct && (
                <span className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
                  correct
                </span>
              )}
            </li>
          );
        })}
      </ul>

      {question.solution && question.solution.trim().length > 0 && (
        <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 p-4">
          <div className="label-field">Solution</div>
          <div
            className="prose prose-sm mt-2 max-w-none text-gray-800"
            dangerouslySetInnerHTML={{ __html: question.solution }}
          />
        </div>
      )}
    </article>
  );
}

function QuestionCardEditor({ question, index, onSave, onCancel }) {
  const [form, setForm] = useState({
    question_text: question.question_text || "",
    option_a: question.option_a || "",
    option_b: question.option_b || "",
    option_c: question.option_c || "",
    option_d: question.option_d || "",
    correct_answer: question.correct_answer || "",
    solution: question.solution || "",
    subject: SUBJECT_OPTIONS.includes(question.subject) ? question.subject : "General",
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
    <form onSubmit={submit} className="card !p-6 ring-2 ring-zinc-200">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-700">
        Editing question {index}
      </h2>

      <label className="mt-4 block">
        <span className="label-field">Question text</span>
        <textarea
          value={form.question_text}
          onChange={(e) => update("question_text", e.target.value)}
          rows={3}
          className="input-field mt-1"
        />
      </label>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {OPTION_KEYS.map((key) => (
          <label key={key} className="block">
            <span className="label-field">Option {key}</span>
            <input
              value={form[`option_${key.toLowerCase()}`]}
              onChange={(e) => update(`option_${key.toLowerCase()}`, e.target.value)}
              className="input-field mt-1"
            />
          </label>
        ))}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="label-field">Correct answer</span>
          <select
            value={form.correct_answer || ""}
            onChange={(e) => update("correct_answer", e.target.value)}
            className="input-field mt-1"
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
        <span className="label-field">Solution (use &lt;br&gt; to separate steps)</span>
        <textarea
          value={form.solution}
          onChange={(e) => update("solution", e.target.value)}
          rows={4}
          className="input-field mt-1"
        />
      </label>

      <label className="mt-4 block">
        <span className="label-field">Subject</span>
        <select
          value={form.subject}
          onChange={(e) => update("subject", e.target.value)}
          className="input-field mt-1"
        >
          {SUBJECT_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>

      {err && <div className="alert-error mt-4">{err}</div>}

      <div className="mt-6 flex gap-3">
        <button type="submit" disabled={saving} className="btn-primary">
          {saving ? "Saving…" : "Save"}
        </button>
        <button type="button" onClick={onCancel} className="btn-secondary">
          Cancel
        </button>
      </div>
    </form>
  );
}

/** @deprecated Use QuestionCard with editing={true} instead. */
export function QuestionEditor(props) {
  return <QuestionCardEditor {...props} />;
}
