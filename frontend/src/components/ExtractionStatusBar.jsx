const STEPS = [
  { key: "upload", label: "Upload PDF" },
  { key: "queue", label: "Queued" },
  { key: "extract", label: "AI extraction" },
  { key: "done", label: "Complete" },
];

function stepIndex(status) {
  switch (status) {
    case "uploading":
      return 0;
    case "pending":
    case "queued":
      return 1;
    case "processing":
      return 2;
    case "done":
      return 3;
    case "failed":
      return 2;
    default:
      return 0;
  }
}

function progressPercent(status, current, total) {
  if (status === "done") return 100;
  if (status === "failed") return 0;
  if (status === "uploading") return 12;
  if (status === "queued" || status === "pending") return 28;
  if (status === "processing" && total > 0) {
    const pct = Math.round((Math.max(current, 0) / total) * 100);
    return Math.min(99, Math.max(35, pct));
  }
  return null;
}

function statusMessage(status, { progressLabel, progressCurrent, progressTotal, fileName }) {
  switch (status) {
    case "uploading":
      return fileName ? `Uploading ${fileName}…` : "Uploading your PDF…";
    case "pending":
    case "queued":
      return "PDF received. Waiting for the extraction worker…";
    case "processing":
      if (progressTotal > 0) {
        return `Extracting questions (${progressCurrent} of ${progressTotal})${
          progressLabel ? ` — ${progressLabel}` : ""
        }…`;
      }
      return (
        progressLabel ||
        "AI is reading your PDF and extracting MCQs. Large files can take 5–15 minutes."
      );
    case "done":
      return "Extraction finished. You can review and edit questions.";
    case "failed":
      return "Extraction could not be completed.";
    default:
      return "Preparing…";
  }
}

export default function ExtractionStatusBar({
  status,
  fileName,
  progressCurrent = 0,
  progressTotal = 0,
  progressLabel,
  questionCount,
  elapsedMinutes,
  className = "",
}) {
  const active = stepIndex(status);
  const percent = progressPercent(status, progressCurrent, progressTotal);
  const indeterminate =
    status === "uploading" || (status === "processing" && (!progressTotal || percent === null));
  const failed = status === "failed";

  return (
    <div
      className={`rounded-xl border bg-white p-6 shadow-sm ${failed ? "border-red-200" : "border-gray-200"} ${className}`}
      role="status"
      aria-live="polite"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-gray-900">Extraction progress</h2>
        {status === "done" && questionCount != null && (
          <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800">
            {questionCount} questions found
          </span>
        )}
        {failed && (
          <span className="rounded-full bg-red-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-red-700">
            Failed
          </span>
        )}
        {!failed && status !== "done" && !indeterminate && percent != null && (
          <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-600">
            {percent}%
          </span>
        )}
        {!failed && status !== "done" && elapsedMinutes != null && elapsedMinutes >= 1 && (
          <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800">
            {elapsedMinutes} min elapsed
          </span>
        )}
      </div>

      <p className="mt-2 text-sm text-gray-600">
        {statusMessage(status, {
          progressLabel,
          progressCurrent,
          progressTotal,
          fileName,
        })}
      </p>

      <div className="mt-4 h-2.5 overflow-hidden rounded-full bg-gray-100">
        {indeterminate && status !== "done" && !failed ? (
          <div className="status-bar-indeterminate h-full w-1/3 rounded-full bg-zinc-800" />
        ) : (
          <div
            className={`h-full rounded-full transition-all duration-500 ease-out ${
              failed ? "bg-red-500" : status === "done" ? "bg-emerald-600" : "bg-zinc-800"
            }`}
            style={{ width: `${failed ? 100 : percent ?? 0}%` }}
          />
        )}
      </div>

      <ol className="mt-6 grid gap-2 sm:grid-cols-4">
        {STEPS.map((step, i) => {
          const done = i < active || status === "done";
          const current = i === active && status !== "done" && !failed;
          const stepFailed = failed && i === active;

          return (
            <li
              key={step.key}
              className={[
                "flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium",
                done && !stepFailed
                  ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                  : current
                    ? stepFailed
                      ? "border-red-200 bg-red-50 text-red-900"
                      : "border-zinc-300 bg-zinc-50 text-zinc-900 ring-1 ring-zinc-200"
                    : "border-gray-100 bg-gray-50 text-gray-400",
              ].join(" ")}
            >
              <span
                className={[
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-bold",
                  done && !stepFailed
                    ? "bg-emerald-600 text-white"
                    : current
                      ? stepFailed
                        ? "bg-red-600 text-white"
                        : "bg-zinc-900 text-white"
                      : "bg-gray-200 text-gray-500",
                ].join(" ")}
              >
                {done && !stepFailed ? "✓" : i + 1}
              </span>
              <span className="truncate">{step.label}</span>
            </li>
          );
        })}
      </ol>

      <style>{`
        @keyframes status-slide {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(350%); }
        }
        .status-bar-indeterminate {
          animation: status-slide 1.4s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
}
