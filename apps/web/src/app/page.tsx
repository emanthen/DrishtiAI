import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col bg-bone dark:bg-ink">
      {/* Nav */}
      <header className="flex items-center justify-between px-8 py-4 border-b border-hairline dark:border-hairline-dark">
        <span className="text-base font-medium text-ink dark:text-bone tracking-tight">
          DrishtiAI
        </span>
        <Link
          href="/login"
          className="rounded-md bg-signal px-4 py-1.5 text-sm font-medium text-white hover:opacity-90 transition-opacity"
        >
          Sign in
        </Link>
      </header>

      {/* Hero */}
      <section className="flex flex-col items-center justify-center flex-1 px-6 text-center py-24 gap-6">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-hairline dark:border-hairline-dark px-3 py-1 text-xs text-steel">
          <span className="h-1.5 w-1.5 rounded-full bg-confirm" />
          On-premises · No cloud dependency
        </span>

        <h1 className="text-4xl font-semibold text-ink dark:text-bone max-w-xl leading-tight tracking-tight">
          Automatic number plate recognition for your site
        </h1>

        <p className="text-base text-steel max-w-md leading-relaxed">
          DrishtiAI turns any IP camera into a real-time ANPR system. Watchlist
          alerts, parking management, gate automation — all processed on your
          hardware, under your control.
        </p>

        <div className="flex gap-3 mt-2">
          <Link
            href="/login"
            className="rounded-md bg-signal px-5 py-2.5 text-sm font-medium text-white hover:opacity-90 transition-opacity"
          >
            Open control room
          </Link>
          <a
            href="https://docs.drishtiai.com"
            className="rounded-md border border-hairline dark:border-hairline-dark px-5 py-2.5 text-sm font-medium text-steel hover:text-ink dark:hover:text-bone transition-colors"
          >
            Documentation
          </a>
        </div>
      </section>

      {/* Feature grid */}
      <section className="border-t border-hairline dark:border-hairline-dark px-8 py-16">
        <div className="max-w-4xl mx-auto grid grid-cols-1 sm:grid-cols-3 gap-8">
          <Feature
            icon="●"
            iconColor="text-signal"
            title="Live ANPR"
            body="Sub-second plate reads from multiple cameras simultaneously, with multi-frame voting for high accuracy."
          />
          <Feature
            icon="▲"
            iconColor="text-alert"
            title="Watchlist alerts"
            body="Blocked vehicles, VIP residents, permit holders — get notified the moment a watched plate appears."
          />
          <Feature
            icon="■"
            iconColor="text-confirm"
            title="Parking & gates"
            body="Automatic session tracking, tariff calculation, and ONVIF or webhook-based gate control."
          />
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-hairline dark:border-hairline-dark px-8 py-6 flex items-center justify-between">
        <span className="text-xs text-steel">© {new Date().getFullYear()} DrishtiAI</span>
        <span className="text-xs text-steel">On-premises ANPR platform</span>
      </footer>
    </main>
  );
}

function Feature({
  icon,
  iconColor,
  title,
  body,
}: {
  icon: string;
  iconColor: string;
  title: string;
  body: string;
}) {
  return (
    <div className="flex flex-col gap-3">
      <span className={`text-lg ${iconColor}`} aria-hidden>
        {icon}
      </span>
      <h3 className="text-sm font-semibold text-ink dark:text-bone">{title}</h3>
      <p className="text-sm text-steel leading-relaxed">{body}</p>
    </div>
  );
}
