const W = 1000;
const H = 260;
const PAD = { top: 16, right: 24, bottom: 32, left: 60 };
const CHART_W = W - PAD.left - PAD.right;
const CHART_H = H - PAD.top - PAD.bottom;

type Row = { date: string; spend: number; revenue: number };

export function TrendChart({ data }: { data: Row[] }) {
  if (data.length === 0) {
    return (
      <div className="grid h-60 place-items-center text-sm text-zinc-400">
        No data
      </div>
    );
  }

  const maxV = Math.max(1, ...data.flatMap((d) => [d.spend, d.revenue]));
  const x = (i: number) =>
    PAD.left +
    (data.length === 1 ? CHART_W / 2 : (i / (data.length - 1)) * CHART_W);
  const y = (v: number) => PAD.top + CHART_H - (v / maxV) * CHART_H;

  const linePath = (key: "spend" | "revenue") =>
    "M " + data.map((d, i) => `${x(i)},${y(d[key])}`).join(" L ");

  const areaPath = (key: "spend" | "revenue") => {
    const start = `M ${x(0)},${PAD.top + CHART_H}`;
    const line = data.map((d, i) => `L ${x(i)},${y(d[key])}`).join(" ");
    const end = `L ${x(data.length - 1)},${PAD.top + CHART_H} Z`;
    return `${start} ${line} ${end}`;
  };

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((p) => p * maxV);

  const xTickIndices = Array.from({ length: 6 }, (_, i) =>
    Math.round((i / 5) * (data.length - 1)),
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
        aria-label="Daily spend vs revenue, last 30 days"
      >
        <defs>
          <linearGradient id="trend-spend" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.45} />
            <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="trend-revenue" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fb923c" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#fb923c" stopOpacity={0} />
          </linearGradient>
        </defs>
        {yTicks.map((v, i) => (
          <g key={i}>
            <line
              x1={PAD.left}
              y1={y(v)}
              x2={W - PAD.right}
              y2={y(v)}
              stroke="#e4e4e7"
              strokeDasharray="3 3"
              strokeWidth={1}
            />
            <text
              x={PAD.left - 10}
              y={y(v) + 4}
              fontSize={12}
              fill="#71717a"
              textAnchor="end"
              fontFamily="var(--font-geist-sans), system-ui, sans-serif"
            >
              ${(v / 1000).toFixed(1)}k
            </text>
          </g>
        ))}
        {xTickIndices.map((i) => (
          <text
            key={i}
            x={x(i)}
            y={H - PAD.bottom + 18}
            fontSize={12}
            fill="#71717a"
            textAnchor="middle"
            fontFamily="var(--font-geist-sans), system-ui, sans-serif"
          >
            {data[i].date.slice(5)}
          </text>
        ))}
        <path d={areaPath("spend")} fill="url(#trend-spend)" />
        <path
          d={linePath("spend")}
          fill="none"
          stroke="#8b5cf6"
          strokeWidth={2.25}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        <path d={areaPath("revenue")} fill="url(#trend-revenue)" />
        <path
          d={linePath("revenue")}
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
