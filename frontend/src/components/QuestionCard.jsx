import { useEffect, useRef } from "react";

const OPTION_KEYS = ["A", "B", "C", "D"];

function typesetCard(cardEl) {
  if (cardEl && window.MathJax?.typesetPromise) {
    window.MathJax.typesetPromise([cardEl]).catch(() => {});
  }
}

export default function QuestionCard({ question, index, onEdit, savedAt }) {
  const cardRef = useRef(null);

  useEffect(() => {
    typesetCard(cardRef.current);
  }, [question, savedAt]);

  return (
    <article ref={cardRef} className="card !p-6">
      <div className="flex items-start justify-between gap-4">
        <h2 className="label-field">Question {index}</h2>
        <button type="button" onClick={onEdit} className="btn-secondary py-1 text-xs">
          Edit
        </button>
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
