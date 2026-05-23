import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { login, register } from "../api/client.js";
import { useAuth } from "../auth/AuthContext.jsx";

export default function Login() {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  // Always land on home — job/review URLs are per-account and break if bookmarked from another user.
  const redirectTo = "/";

  async function onSubmit(event) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const fn = mode === "login" ? login : register;
      const { access_token } = await fn(email.trim().toLowerCase(), password);
      await signIn(access_token, { remember });
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const isLogin = mode === "login";

  return (
    <div className="mx-auto max-w-md">
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-8 shadow-xl">
        <h1 className="text-2xl font-semibold text-slate-100">
          {isLogin ? "Sign in" : "Create account"}
        </h1>
        <p className="mt-1 text-sm text-slate-400">
          {isLogin
            ? "Use your email and password to access your jobs."
            : "Register to start extracting MCQs from PDFs."}
        </p>

        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          <label className="block text-sm">
            <span className="text-slate-300">Email</span>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950/50 px-3 py-2 text-slate-100 focus:border-sky-500 focus:outline-none"
            />
          </label>

          <label className="block text-sm">
            <span className="text-slate-300">Password</span>
            <input
              type="password"
              required
              minLength={isLogin ? 1 : 8}
              autoComplete={isLogin ? "current-password" : "new-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950/50 px-3 py-2 text-slate-100 focus:border-sky-500 focus:outline-none"
            />
            {!isLogin && (
              <span className="mt-1 block text-xs text-slate-500">
                At least 8 characters.
              </span>
            )}
          </label>

          <label className="flex items-center gap-2 text-xs text-slate-400">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="h-4 w-4"
            />
            Remember me on this device
          </label>

          {error && (
            <div className="rounded-md border border-rose-700/60 bg-rose-900/30 px-3 py-2 text-sm text-rose-200">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-md bg-sky-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
          >
            {busy ? "Please wait…" : isLogin ? "Sign in" : "Create account"}
          </button>
        </form>

        <div className="mt-4 text-center text-sm text-slate-400">
          {isLogin ? "New here?" : "Already have an account?"}{" "}
          <button
            type="button"
            onClick={() => {
              setError(null);
              if (isLogin) {
                setMode("register");
                navigate("/login", { replace: true, state: {} });
              } else {
                setMode("login");
              }
            }}
            className="text-sky-400 hover:underline"
          >
            {isLogin ? "Create one" : "Sign in"}
          </button>
        </div>

        <p className="mt-6 text-xs text-slate-500">
          <Link to="/" className="hover:underline">
            ← Back home
          </Link>
        </p>
      </div>
    </div>
  );
}
