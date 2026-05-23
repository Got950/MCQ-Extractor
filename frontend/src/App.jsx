import { Link, Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth/AuthContext.jsx";
import RequireAuth from "./auth/RequireAuth.jsx";
import Job from "./pages/Job.jsx";
import Login from "./pages/Login.jsx";
import Review from "./pages/Review.jsx";
import Upload from "./pages/Upload.jsx";

export default function App() {
  const { user, signOut } = useAuth();

  return (
    <div className="min-h-full">
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <Link to="/" className="text-lg font-semibold text-slate-100" title="Upload PDF">
            MCQ Extractor
          </Link>
          <div className="flex items-center gap-4 text-xs">
            <span className="hidden uppercase tracking-wider text-slate-400 sm:inline">
              FastAPI · Gemini · Ollama
            </span>
            {user ? (
              <div className="flex items-center gap-3">
                <span className="text-slate-300">{user.email}</span>
                <button
                  type="button"
                  onClick={signOut}
                  className="rounded-md border border-slate-700 px-3 py-1 text-slate-200 transition hover:border-sky-500 hover:text-sky-300"
                >
                  Sign out
                </button>
              </div>
            ) : (
              <Link
                to="/login"
                className="rounded-md bg-sky-500 px-3 py-1 font-medium text-white transition hover:bg-sky-400"
              >
                Sign in
              </Link>
            )}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-10">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <Upload />
              </RequireAuth>
            }
          />
          <Route
            path="/job/:id"
            element={
              <RequireAuth>
                <Job />
              </RequireAuth>
            }
          />
          <Route
            path="/review/:id"
            element={
              <RequireAuth>
                <Review />
              </RequireAuth>
            }
          />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <footer className="mx-auto max-w-5xl px-6 py-6 text-xs text-slate-500">
        Math rendered via MathJax. Inline math wrapped in \( ... \).
      </footer>
    </div>
  );
}

function NotFound() {
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900 p-6">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <p className="mt-2 text-sm text-slate-400">
        <Link to="/" className="text-sky-400 hover:underline">
          Back to upload
        </Link>
      </p>
    </div>
  );
}
