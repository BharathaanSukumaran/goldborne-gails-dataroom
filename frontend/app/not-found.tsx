import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-paper px-6">
      <div className="max-w-md rounded-lg border border-line bg-white p-6 text-center shadow-panel">
        <p className="text-sm font-semibold uppercase tracking-[0.14em] text-moss">404</p>
        <h1 className="mt-2 text-2xl font-semibold text-ink">Page not found</h1>
        <p className="mt-3 text-sm leading-6 text-ink/64">
          The Goldborne Capital Intelligence Platform is available from the dataroom chat.
        </p>
        <Link
          className="mt-5 inline-flex rounded-md bg-moss px-4 py-2 text-sm font-medium text-white hover:bg-ink"
          href="/"
        >
          Return to dataroom
        </Link>
      </div>
    </main>
  );
}
