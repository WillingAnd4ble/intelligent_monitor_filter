"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { getAuthErrorMessage } from "@/lib/auth-errors";
import { register } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      await register({ email, password });
      router.push("/dashboard");
      router.refresh();
    } catch (e) {
      setError(
        getAuthErrorMessage(e, "Could not register. Try a different email."),
      );
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="rounded-lg border border-stone-200 bg-white p-8 shadow-card">
      <h1 className="text-xl font-semibold text-sage-700">Create account</h1>
      <p className="mt-1 text-sm text-ink-secondary">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-amber-warm">
          Log in
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
            autoComplete="new-password"
            required
            minLength={8}
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
          {pending ? "Creating…" : "Register"}
        </button>
      </form>
    </div>
  );
}
