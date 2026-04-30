import type { Recommendation } from "@/lib/api";

export function RecommendationCard({
  index,
  rec,
}: {
  index: number;
  rec: Recommendation;
}) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="flex items-start gap-3">
        <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-violet-50 text-sm font-semibold text-violet-700">
          {index}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-zinc-900">{rec.title}</p>
          <p className="mt-2 text-sm text-zinc-700">{rec.action}</p>
          <p className="mt-3 text-xs italic text-zinc-500">{rec.rationale}</p>
        </div>
      </div>
    </div>
  );
}
