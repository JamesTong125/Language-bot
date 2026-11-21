import Link from "next/link";

export default function Landing() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center px-4 py-16">
      <h1 className="text-4xl font-bold tracking-tight text-stone-900 sm:text-5xl">
        Language learning bot
      </h1>
      <p className="mt-4 text-lg text-stone-700">
        Practise a language by role-playing real situations, like ordering at a café or asking
        for directions. Get gentle corrections after each message and build a vocabulary deck
        from your own mistakes.
      </p>
      <div className="mt-8 flex flex-wrap gap-3">
        <Link
          href="/register"
          className="inline-flex min-h-11 items-center rounded-lg bg-teal-700 px-5 py-2 font-semibold text-white hover:bg-teal-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700"
        >
          Get started
        </Link>
        <Link
          href="/login"
          className="inline-flex min-h-11 items-center rounded-lg border border-stone-300 bg-white px-5 py-2 font-semibold text-stone-800 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700"
        >
          Log in
        </Link>
      </div>
    </main>
  );
}
