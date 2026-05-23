import { useEffect, useRef } from "react";

const OPTION_KEYS = ["A", "B", "C", "D"];

function typesetCard(cardEl) {
  if (cardEl && window.MathJax?.typesetPromise) {
    window.MathJax.typesetPromise([cardEl]).catch(() => {
      /* ignore typeset errors */
    });
  }
}

export default function QuestionCard({ question, index, onEdit, savedAt }) {
  const cardRef = useRef(null);

  useEffect(() => {
    typesetCard(cardRef.current);
  }, [question, savedAt]);

  return (
    <article
      ref={cardRef}
      className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow"
    >
      <div className="flex items-start justify-between gap-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          Question {index}
        </h2>
        <button
          type="button"
          onClick={onEdit}
          className="rounded-md border border-slate-700 px-3 py-1 text-xs font-medium text-slate-200 transition hover:border-sky-500 hover:text-sky-300"
        >
          Edit
        </button>
      </div>

      <div
        className="prose prose-invert mt-4 max-w-none text-slate-100"
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
                "flex gap-3 rounded-lg border px-4 py-2 text-sm",
                correct
                  ? "border-emerald-600/60 bg-emerald-900/30 text-emerald-100"
                  : "border-slate-800 bg-slate-900 text-slate-200",
              ].join(" ")}
            >
              <span className="font-semibold">{key}.</span>
              <div
                className="flex-1"
                dangerouslySetInnerHTML={{ __html: value || "" }}
              />
              {correct && (
                <span className="text-xs uppercase tracking-wider text-emerald-300">
                  correct
                </span>
              )}
            </li>
          );
        })}
      </ul>

      {question.solution && question.solution.trim().length > 0 && (
        <div className="mt-4 rounded-lg border border-slate-800 bg-slate-950/50 p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Solution
          </div>
          <div
            className="mt-2 text-sm text-slate-200"
            dangerouslySetInnerHTML={{ __html: question.solution }}
          />
        </div>
      )}
    </article>
  );
}
