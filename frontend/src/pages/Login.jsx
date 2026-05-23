import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

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
      <div className="card">
        <h1 className="text-2xl font-semibold tracking-tight text-gray-900">
          {isLogin ? "Sign in" : "Create account"}
        </h1>
        <p className="mt-1 text-sm text-gray-600">
          {isLogin
            ? "Access your private workspace and extraction history."
            : "Register to start extracting MCQs from academic PDFs."}
        </p>

        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          <label className="block text-sm">
            <span className="font-medium text-gray-700">Email</span>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input-field mt-1"
            />
          </label>

          <label className="block text-sm">
            <span className="font-medium text-gray-700">Password</span>
            <input
              type="password"
              required
              minLength={isLogin ? 1 : 8}
              autoComplete={isLogin ? "current-password" : "new-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-field mt-1"
            />
            {!isLogin && (
              <span className="mt-1 block text-xs text-gray-500">At least 8 characters.</span>
            )}
          </label>

          <label className="flex items-center gap-2 text-xs text-gray-600">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300"
            />
            Remember me on this device
          </label>

          {error && <div className="alert-error">{error}</div>}

          <button type="submit" disabled={busy} className="btn-primary w-full">
            {busy ? "Please wait…" : isLogin ? "Sign in" : "Create account"}
          </button>
        </form>

        <div className="mt-4 text-center text-sm text-gray-600">
          {isLogin ? "New here?" : "Already have an account?"}{" "}
          <button
            type="button"
            onClick={() => {
              setError(null);
              setMode(isLogin ? "register" : "login");
            }}
            className="font-semibold text-zinc-900 underline-offset-2 hover:underline"
          >
            {isLogin ? "Create one" : "Sign in"}
          </button>
        </div>
      </div>
    </div>
  );
}
