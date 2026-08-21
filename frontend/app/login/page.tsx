"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  const { user, loading, login, register } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // In single-user mode the backend resolves the owner without a login,
  // so /auth/me already succeeded and there is nothing to sign in to.
  // Anyone who lands here -- a bookmark, a stale redirect -- goes straight
  // to the dashboard rather than being shown a form that does nothing.
  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [loading, user, router]);

  if (loading || user) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-sm text-stone-400">
        Loading…
      </div>
    );
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(email, password, fullName);
      }
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[80vh] max-w-sm flex-col justify-center">
      <div className="mb-10 text-center">
        <p className="font-display text-3xl text-stone-900">Aperture</p>
        <p className="mt-3 text-sm text-stone-500">
          Prepare and post your work with more intention — never a promise of likes or followers.
        </p>
      </div>

      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        {mode === "register" && (
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-stone-500">
              Name
            </label>
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full rounded-lg border border-stone-300 bg-white px-3.5 py-2.5 text-sm outline-none focus:border-stone-900"
              placeholder="Your name"
            />
          </div>
        )}
        <div>
          <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-stone-500">
            Email
          </label>
          <input
            required
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg border border-stone-300 bg-white px-3.5 py-2.5 text-sm outline-none focus:border-stone-900"
            placeholder="you@example.com"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-stone-500">
            Password
          </label>
          <input
            required
            type="password"
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border border-stone-300 bg-white px-3.5 py-2.5 text-sm outline-none focus:border-stone-900"
            placeholder="••••••••"
          />
        </div>

        {error && <p className="text-sm text-red-700">{error}</p>}

        <Button type="submit" disabled={submitting} className="mt-2 w-full">
          {submitting ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
        </Button>
      </form>

      <button
        onClick={() => setMode(mode === "login" ? "register" : "login")}
        className="mt-6 text-center text-sm text-stone-500 hover:text-stone-900"
      >
        {mode === "login" ? "New here? Create an account" : "Already have an account? Sign in"}
      </button>
    </div>
  );
}
