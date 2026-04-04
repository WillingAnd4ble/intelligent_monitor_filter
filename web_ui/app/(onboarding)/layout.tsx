export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-landing-hero px-4 py-12">
      <div className="w-full max-w-xl">{children}</div>
    </div>
  );
}
