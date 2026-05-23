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
    <div className="flex min-h-full flex-col">
      <header className="border-b border-gray-200 bg-white shadow-sm">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-2" title="Upload PDF">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-900 text-sm font-bold text-white">
              M
            </span>
            <span className="text-lg font-semibold tracking-tight text-gray-900">
              MCQ Extractor
            </span>
          </Link>
          <div className="flex items-center gap-4 text-xs">
            <span className="hidden text-gray-400 sm:inline">
              AI-powered question extraction
            </span>
            {user ? (
              <div className="flex items-center gap-3">
                <span className="max-w-[180px] truncate text-gray-600 sm:max-w-none">
                  {user.email}
                </span>
                <button type="button" onClick={signOut} className="btn-secondary py-1.5">
                  Sign out
                </button>
              </div>
            ) : (
              <Link to="/login" className="btn-primary py-2">
                Sign in
              </Link>
            )}
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-10">
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
      <footer className="border-t border-gray-200 bg-white py-6 text-center text-xs text-gray-400">
        <div className="mx-auto max-w-5xl px-6">
          Math rendered via MathJax · Inline math wrapped in \( ... \)
        </div>
      </footer>
    </div>
  );
}

function NotFound() {
  return (
    <div className="card">
      <h1 className="text-xl font-semibold text-gray-900">Page not found</h1>
      <p className="mt-2 text-sm text-gray-600">
        <Link to="/" className="font-medium text-zinc-900 underline-offset-2 hover:underline">
          Back to workspace
        </Link>
      </p>
    </div>
  );
}
