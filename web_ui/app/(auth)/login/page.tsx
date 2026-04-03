"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { getAuthErrorMessage } from "@/lib/auth-errors";
import { login } from "@/lib/api";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/dashboard";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      await login({ email, password });
      router.push(next.startsWith("/") ? next : "/dashboard");
      router.refresh();
    } catch (e) {
      setError(getAuthErrorMessage(e, "Invalid email or password."));
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="rounded-lg border border-stone-200 bg-white p-8 shadow-card">
      <h1 className="text-xl font-semibold text-sage-700">Log in</h1>
      <p className="mt-1 text-sm text-ink-secondary">
        New here?{" "}
        <Link href="/register" className="font-medium text-amber-warm">
          Create an account
        </Link>
      </p>
      <form className="mt-6 space-y-4" onSubmit={onSubmit}>
        <div>
          <label htmlFor="email" className="text-sm font-medium text-ink-primary">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-md border border-stone-200 px-3 py-2 text-sm outline-none ring-sage-500 focus:ring-2"
          />
        </div>
        <div>
          <label
            htmlFor="password"
            className="text-sm font-medium text-ink-primary"
          >
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-md border border-stone-200 px-3 py-2 text-sm outline-none ring-sage-500 focus:ring-2"
          />
        </div>
        {error && <p className="text-sm text-red-800">{error}</p>}
        <button
          type="submit"
          disabled={pending}
          className="w-full rounded-md bg-sage-500 py-2.5 text-sm font-semibold text-white hover:bg-sage-700 disabled:opacity-60"
        >
          {pending ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="rounded-lg border border-stone-200 bg-white p-8 text-sm text-ink-muted shadow-card">
          Loading…
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
