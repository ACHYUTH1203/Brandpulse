const W = 1000;
const H = 280;
const PAD = { top: 16, right: 60, bottom: 32, left: 60 };
const CHART_W = W - PAD.left - PAD.right;
const CHART_H = H - PAD.top - PAD.bottom;

type Row = {
  date: string;
  spend: number;
  conversions: number;
};

export function InsightChart({
  data,
  periodStart,
  periodEnd,
}: {
  data: Row[];
  periodStart: string;
  periodEnd: string;
}) {
  const series = data.slice(-30);
  if (series.length === 0) {
    return (
      <div className="grid h-60 place-items-center text-sm text-zinc-400">
        No data
      </div>
    );
  }

  const maxSpend = Math.max(1, ...series.map((d) => d.spend));
  const maxConv = Math.max(1, ...series.map((d) => d.conversions));

  const x = (i: number) =>
    PAD.left +
    (series.length === 1 ? CHART_W / 2 : (i / (series.length - 1)) * CHART_W);
  const ySpend = (v: number) => PAD.top + CHART_H - (v / maxSpend) * CHART_H;
  const yConv = (v: number) => PAD.top + CHART_H - (v / maxConv) * CHART_H;

  const spendArea = () => {
    const start = `M ${x(0)},${PAD.top + CHART_H}`;
    const line = series.map((d, i) => `L ${x(i)},${ySpend(d.spend)}`).join(" ");
    const end = `L ${x(series.length - 1)},${PAD.top + CHART_H} Z`;
    return `${start} ${line} ${end}`;
  };
  const spendLine = () =>
    "M " + series.map((d, i) => `${x(i)},${ySpend(d.spend)}`).join(" L ");
  const convLine = () =>
    "M " + series.map((d, i) => `${x(i)},${yConv(d.conversions)}`).join(" L ");

  const inWindow = series
    .map((d, i) => ({
      i,
      inside: d.date >= periodStart && d.date <= periodEnd,
    }))
    .filter((p) => p.inside)
    .map((p) => p.i);
  const windowStartX = inWindow.length > 0 ? x(inWindow[0]) : null;
  const windowEndX =
    inWindow.length > 0 ? x(inWindow[inWindow.length - 1]) : null;

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((p) => p * maxSpend);
  const xTickIndices = Array.from({ length: 6 }, (_, i) =>
    Math.round((i / 5) * (series.length - 1)),
  );

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        height="auto"
        preserveAspectRatio="xMidYMid meet"
        className="block"
        role="img"
        aria-label="Spend vs conversions, last 30 days, leak window highlighted"
      >
        <defs>
          <linearGradient id="ins-spend" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.45} />
            <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0} />
          </linearGradient>
        </defs>
        {windowStartX !== null && windowEndX !== null && (
          <rect
            x={windowStartX}
            y={PAD.top}
            width={Math.max(2, windowEndX - windowStartX)}
            height={CHART_H}
            fill="#ef4444"
            fillOpacity={0.08}
            stroke="#ef4444"
            strokeOpacity={0.35}
            strokeDasharray="4 3"
            strokeWidth={1}
          />
        )}
        {yTicks.map((v, i) => (
          <g key={`y-${i}`}>
            <line
              x1={PAD.left}
              y1={ySpend(v)}
              x2={W - PAD.right}
              y2={ySpend(v)}
              stroke="#e4e4e7"
              strokeDasharray="3 3"
              strokeWidth={1}
            />
            <text
              x={PAD.left - 10}
              y={ySpend(v) + 4}
              fontSize={12}
              fill="#71717a"
              textAnchor="end"
              fontFamily="var(--font-geist-sans), system-ui, sans-serif"
            >
              ${(v / 1000).toFixed(1)}k
            </text>
          </g>
        ))}
        {[0, 0.5, 1].map((p, i) => (
          <text
            key={`yr-${i}`}
            x={W - PAD.right + 10}
            y={ySpend(maxSpend * p) + 4}
            fontSize={12}
            fill="#71717a"
            textAnchor="start"
            fontFamily="var(--font-geist-sans), system-ui, sans-serif"
          >
            {Math.round(maxConv * p)}
          </text>
        ))}
        {xTickIndices.map((i) => (
          <text
            key={`x-${i}`}
            x={x(i)}
            y={H - PAD.bottom + 18}
            fontSize={12}
            fill="#71717a"
            textAnchor="middle"
            fontFamily="var(--font-geist-sans), system-ui, sans-serif"
          >
            {series[i].date.slice(5)}
          </text>
        ))}
        <path d={spendArea()} fill="url(#ins-spend)" />
        <path
          d={spendLine()}
          fill="none"
          stroke="#8b5cf6"
          strokeWidth={2.25}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        <path
          d={convLine()}
          fill="none"
          stroke="#fb923c"
          strokeWidth={2.25}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        <line
          x1={PAD.left}
          y1={PAD.top + CHART_H}
          x2={W - PAD.right}
          y2={PAD.top + CHART_H}
          stroke="#e4e4e7"
          strokeWidth={1}
        />
      </svg>
    </div>
  );
}
