import { useEffect, useState } from "react";

const GLASS = "bg-white/[0.07] backdrop-blur-3xl backdrop-saturate-150 border border-white/[0.32]";
const INPUT = "w-full bg-white/[0.09] border border-white/[0.26] rounded-lg px-3 py-2.5 text-sm text-white placeholder-white/40 focus:outline-none focus:border-white/50 focus:ring-1 focus:ring-white/30";
const BUTTON = "w-full rounded-lg px-4 py-3 text-sm font-medium text-white bg-white/15 hover:bg-white/25 active:bg-white/20 transition border border-white/30";
const LINK = "text-xs text-white/50 hover:text-white/80 transition";

const AUTH_TOKEN_KEY = "neurolab_token";

export function getAuthToken() {
  try { return localStorage.getItem(AUTH_TOKEN_KEY); } catch { return null; }
}

export function clearAuthToken() {
  try { localStorage.removeItem(AUTH_TOKEN_KEY); } catch {}
}

export function authHeaders() {
  const token = getAuthToken();
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

export default function AuthGate({ children }) {
  const [state, setState] = useState("loading");
  const [user, setUser] = useState(null);
  const [mode, setMode] = useState("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    fetch("/auth/me", { credentials: "same-origin", headers: authHeaders() })
      .then((r) => {
        if (r.ok) return r.json();
        throw new Error("not authenticated");
      })
      .then((data) => {
        setUser(data);
        setState("unlocked");
      })
      .catch(() => setState("locked"));
  }, []);

  const resetForm = () => {
    setError("");
    setSuccess("");
    setPassword("");
    setConfirmPassword("");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    const endpoint = mode === "login" ? "/auth/login" : mode === "register" ? "/auth/register" : "/auth/reset-password";
    const body = { email: email.trim().toLowerCase(), password };
    if (mode === "register") body.name = name.trim();
    if (mode === "reset") {
      if (password !== confirmPassword) {
        setError("Passwords do not match");
        return;
      }
    }

    try {
      const r = await fetch(endpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await r.json().catch(() => ({}));
      if (r.status === 403 && data.detail === "Account pending approval") {
        setSuccess("Account created and is pending admin approval.");
        return;
      }
      if (!r.ok) {
        setError(data.detail || "Request failed");
        return;
      }
      if (mode === "register" && data.pending_approval) {
        setSuccess(data.message || "Account created and is pending admin approval.");
        return;
      }
      if (data.token) {
        try { localStorage.setItem(AUTH_TOKEN_KEY, data.token); } catch {}
      }
      if (mode === "reset") {
        setSuccess(data.message || "Password updated.");
        setPassword("");
        setConfirmPassword("");
        return;
      }
      window.location.reload();
    } catch (err) {
      setError(err?.message || "Network error");
    }
  };

  const logout = () => {
    clearAuthToken();
    fetch("/auth/logout", { method: "POST", credentials: "same-origin" })
      .then(() => window.location.reload());
  };

  if (state === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#121820] text-white">
        Loading…
      </div>
    );
  }

  if (state === "unlocked") {
    return (
      <>
        {children}
        <button
          type="button"
          onClick={logout}
          className={`fixed bottom-4 right-4 z-[70] pl-3 pr-4 py-2 rounded-full text-xs font-medium text-white/90 ${GLASS} hover:bg-white/10 transition flex items-center gap-2`}
          title={`Signed in as ${user?.email || ""}`}
        >
          <span className="w-5 h-5 rounded-full bg-white/20 flex items-center justify-center text-[10px]">
            {(user?.name || user?.email || "?").charAt(0).toUpperCase()}
          </span>
          Sign out
        </button>
      </>
    );
  }

  const title = mode === "login" ? "Sign in" : mode === "register" ? "Create account" : "Reset password";

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#121820] relative overflow-hidden px-4">
      <div className="absolute inset-0 -z-10 bg-gradient-to-br from-[#1a2533] to-[#121820]" />
      <form onSubmit={handleSubmit} className={`w-full max-w-sm rounded-2xl p-6 ${GLASS}`}>
        <h1 className="text-xl font-semibold mb-1 text-center text-white">NeuroLab</h1>
        <p className="text-sm text-white/70 mb-5 text-center">{title} to continue.</p>

        {error && (
          <p className="text-red-300 text-sm mb-3 text-center">{error}</p>
        )}

        {success && (
          <p className="text-green-300 text-sm mb-3 text-center">{success}</p>
        )}

        {mode === "register" && (
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={INPUT}
            placeholder="Your name"
            required
          />
        )}

        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className={`${INPUT} mt-3`}
          placeholder="Email"
          required
        />

        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className={`${INPUT} mt-3`}
          placeholder={mode === "reset" ? "New password" : "Password"}
          required
          minLength={12}
        />

        {mode === "reset" && (
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className={`${INPUT} mt-3`}
            placeholder="Confirm new password"
            required
            minLength={12}
          />
        )}

        {(mode === "register" || mode === "reset") && (
          <p className="text-xs text-white/40 mt-2 text-center">
            Password must be at least 12 characters with uppercase, lowercase, digit, and special character.
          </p>
        )}

        <button type="submit" className={`${BUTTON} mt-4`}>
          {mode === "reset" ? "Update password" : title}
        </button>

        <div className="mt-4 text-center flex flex-col gap-1">
          {mode === "login" ? (
            <>
              <button type="button" onClick={() => { setMode("register"); resetForm(); }} className={LINK}>
                Don’t have an account? Create one
              </button>
              <button type="button" onClick={() => { setMode("reset"); resetForm(); }} className={LINK}>
                Forgot password?
              </button>
            </>
          ) : mode === "register" ? (
            <button type="button" onClick={() => { setMode("login"); resetForm(); }} className={LINK}>
              Already have an account? Sign in
            </button>
          ) : (
            <button type="button" onClick={() => { setMode("login"); resetForm(); }} className={LINK}>
              Back to sign in
            </button>
          )}
        </div>

        <p className="text-xs text-white/40 mt-4 text-center">
          Patient data is linked to your account and backed up to your Google Drive automatically.
        </p>
      </form>
    </div>
  );
}
