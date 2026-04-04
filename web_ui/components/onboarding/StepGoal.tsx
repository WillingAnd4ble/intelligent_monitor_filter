"use client";

type Props = {
  goal: string;
  onChange: (v: string) => void;
};

export function StepGoal({ goal, onChange }: Props) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-sage-700">
          What are you looking for?
        </h2>
        <p className="mt-1 text-sm text-ink-secondary">
          Describe what you&rsquo;re working on and what papers would be valuable
          to you. Be specific &mdash; the system uses this to evaluate every
          paper.
        </p>
      </div>

      <textarea
        className="w-full rounded-md border border-stone-200 px-3 py-2 text-sm outline-none ring-sage-500 focus:ring-2"
        rows={6}
        value={goal}
        onChange={(e) => onChange(e.target.value)}
        placeholder="I'm researching efficient fine-tuning methods for LLMs, particularly LoRA variants and their application to domain-specific tasks. I'm interested in papers that show practical improvements with limited compute."
      />
    </div>
  );
}
