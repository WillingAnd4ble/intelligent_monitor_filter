import Link from "next/link";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-landing-hero">
      <header className="mx-auto flex max-w-[1120px] items-center justify-between px-7 py-5">
        <Link href="/" className="font-semibold text-ink-primary no-underline">
          arxiv<strong className="text-sage-700">lens</strong>
        </Link>
        <div className="flex items-center gap-3">
          <Link
            href="/login"
            className="text-sm font-medium text-ink-secondary no-underline hover:text-sage-700"
          >
            Log in
          </Link>
          <Link
            href="/register"
            className="rounded-md bg-sage-500 px-5 py-2.5 text-sm font-semibold text-white no-underline hover:bg-sage-700"
          >
            Get started
          </Link>
        </div>
      </header>

      <section className="mx-auto max-w-[720px] px-7 pb-20 pt-[72px] text-center">
        <p className="mb-6 inline-block rounded-full border border-sage-200 bg-sage-50 px-3.5 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-sage-700">
          Powered by LLM agents
        </p>
        <h1 className="text-balance text-[clamp(2rem,5vw,3rem)] font-bold leading-tight tracking-tight text-ink-primary">
          Your personal research intelligence layer for arXiv.
        </h1>
        <p className="mx-auto mt-5 max-w-[520px] text-lg leading-relaxed text-ink-secondary">
          Stop drowning in papers. Set your goal in plain language, let agents
          scrape and rank new submissions, and read only what matters to you.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link
            href="/register"
            className="rounded-md bg-sage-500 px-6 py-3 text-[15px] font-semibold text-white no-underline hover:bg-sage-700"
          >
            Get started
          </Link>
          <Link
            href="/dashboard"
            className="rounded-md border border-stone-200 bg-white px-6 py-3 text-[15px] font-semibold text-ink-primary no-underline shadow-sm hover:bg-stone-50"
          >
            View demo feed
          </Link>
        </div>
      </section>

      <section
        className="mx-auto max-w-[1120px] border-t border-stone-200 px-7 py-14"
        aria-labelledby="how-heading"
      >
        <h2
          id="how-heading"
          className="mb-10 text-center text-xl font-semibold tracking-tight text-sage-700"
        >
          How it works
        </h2>
        <div className="grid gap-7 sm:grid-cols-2 lg:grid-cols-3">
          {[
            {
              n: "01",
              t: "Set your goal",
              d: "Describe what you care about in natural language — topics, methods, or problems you follow.",
            },
            {
              n: "02",
              t: "Agents filter",
              d: "Daily pipelines pull arXiv categories you choose, score papers, and explain why each one fits.",
            },
            {
              n: "03",
              t: "Read & save",
              d: "Triage the feed, accept or reject with feedback, build a library with deeper explanations on demand.",
            },
          ].map((step) => (
            <div
              key={step.n}
              className="rounded-lg border border-stone-200 bg-white p-6 shadow-card"
            >
              <div className="mb-2.5 font-mono text-xs font-semibold text-amber-warm">
                {step.n}
              </div>
              <h3 className="text-[1.05rem] font-semibold text-ink-primary">
                {step.t}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-secondary">
                {step.d}
              </p>
            </div>
          ))}
        </div>
      </section>

      <footer className="mx-auto max-w-[1120px] border-t border-stone-200 px-7 py-10 text-center text-sm text-ink-muted">
        arXiv Lens
      </footer>
    </div>
  );
}
