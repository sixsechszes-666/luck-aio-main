import { useState, useEffect, useMemo } from "react";
import { Search, ExternalLink, Loader2, BarChart3, PieChart as PieChartIcon, TrendingUp, ArrowUpDown, Clock, Calendar, Box } from "lucide-react";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/StatusBadge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type DailyAccount, type DailySummary } from "@/data/mockData";
import { apiGetDaily, apiGetDailyTimeline, apiGetBonusTracker, type TimelineEntry, type BonusTrackerEntry } from "@/services/api";
import { cn } from "@/lib/utils";
import { useTheme } from "@/contexts/ThemeContext";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie,
  AreaChart, Area,
  LineChart, Line,
  CartesianGrid,
} from "recharts";

const emptySummary: DailySummary = { totalAccounts: 0, successCount: 0, errorCount: 0, chestUnavailable: 0, avgDrop: 0, totalProfit: 0, totalSolProfit: 0, solRate: 0, totalBalanceUsd: 0, totalBalanceSol: 0, totalChestAmount: 0, plannedTomorrow: 0 };

const Metric = ({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: boolean }) => (
  <div className={cn("bw-card rounded-sm p-5", accent && "border-white/10")}>
    <p className="bw-label mb-2 text-xs">{label}</p>
    <p className={cn("text-2xl font-semibold bw-value", accent ? "text-white" : "text-[#ddd]")}>{value}</p>
    {sub && <p className="text-xs text-[#999] mt-1.5 mono">{sub}</p>}
  </div>
);

const FilterBtn = ({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) => (
  <button onClick={onClick} className={cn(
    "px-3 py-1.5 rounded-sm mono text-xs tracking-widest uppercase transition-all",
    active ? "bg-white text-black" : "text-[#aaa] hover:text-white border border-[#1e1e1e] hover:border-[#333]"
  )}>{children}</button>
);

const ChartTooltipContent = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bw-card rounded-sm p-2.5 border-white/10 shadow-xl">
      <p className="mono text-[0.6rem] text-[#888] mb-1">{label}</p>
      {payload.map((entry: any, i: number) => (
        <p key={i} className="mono text-xs text-white font-semibold">
          {entry.name}: {typeof entry.value === "number" ? (entry.value >= 0 ? "+" : "") + entry.value.toFixed(4) : entry.value}
        </p>
      ))}
    </div>
  );
};

const DonutLabel = ({ viewBox, value, label }: any) => {
  const { cx, cy } = viewBox;
  return (
    <text x={cx} y={cy} textAnchor="middle" dominantBaseline="central">
      <tspan x={cx} y={cy - 6} fill="#fff" fontSize="18" fontWeight="700" fontFamily="'JetBrains Mono', monospace">{value}</tspan>
      <tspan x={cx} y={cy + 12} fill="#777" fontSize="9" fontFamily="'JetBrains Mono', monospace" letterSpacing="0.1em">{label}</tspan>
    </text>
  );
};

export const DailyTasksTab = () => {
  const { isColor } = useTheme();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"ALL" | "SUCCESS" | "ERROR">("ALL");
  const [accounts, setAccounts] = useState<DailyAccount[]>([]);
  const [summary, setSummary] = useState<DailySummary>(emptySummary);
  const [loading, setLoading] = useState(true);
  const [showCharts, setShowCharts] = useState(true);
  const [subTab, setSubTab] = useState<"results" | "timeline" | "bonuses">("results");
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineError, setTimelineError] = useState<string | null>(null);
  const [bonuses, setBonuses] = useState<BonusTrackerEntry[]>([]);
  const [bonusSummary, setBonusSummary] = useState({ total_accounts: 0, weekly_available: 0, monthly_available: 0, no_data: 0 });
  const [bonusLoading, setBonusLoading] = useState(false);
  const [bonusSearch, setBonusSearch] = useState("");
  const [bonusSortField, setBonusSortField] = useState<'weekly' | 'monthly'>('weekly');
  const [sortConfig, setSortConfig] = useState<{key: string, direction: 'asc'|'desc'} | null>(null);

  useEffect(() => {
    setLoading(true);
    apiGetDaily().then((res) => {
      if (res.data && res.summary) {
        setAccounts(res.data.map((r: any) => ({ udDir: r.UD_DIR, workerId: r.WORKER_ID, result: r.RESULT, startBalance: r.START_BALANCE || 0, endBalance: r.END_BALANCE || 0, balanceDifference: r.BALANCE_DIFFERENCE || 0, solBalanceDifference: r.SOL_BALANCE_DIFFERENCE || 0, chestAmount: r.CHEST_AMOUNT || 0, link: r.LINK || "" })));
        setSummary({ totalAccounts: res.summary.total_accounts, successCount: res.summary.success_count, errorCount: res.summary.error_count, chestUnavailable: res.summary.chest_unavailable, avgDrop: res.summary.avg_drop, totalProfit: res.summary.total_profit, totalSolProfit: res.summary.total_sol_profit, solRate: res.summary.sol_rate, totalBalanceUsd: res.summary.total_balance_usd, totalBalanceSol: res.summary.total_balance_sol, totalChestAmount: res.summary.total_chest_amount || 0, plannedTomorrow: res.summary.planned_tomorrow || 0 });
      }
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (subTab !== "timeline") return;
    setTimelineLoading(true);
    setTimelineError(null);
    apiGetDailyTimeline()
      .then((data) => setTimeline(data))
      .catch((err) => setTimelineError(String(err)))
      .finally(() => setTimelineLoading(false));
  }, [subTab]);

  useEffect(() => {
    if (subTab !== "bonuses") return;
    setBonusLoading(true);
    apiGetBonusTracker()
      .then((res) => {
        setBonuses(res.data || []);
        setBonusSummary(res.summary || { total_accounts: 0, weekly_available: 0, monthly_available: 0, no_data: 0 });
      })
      .catch(() => {})
      .finally(() => setBonusLoading(false));
  }, [subTab]);

  const filtered = useMemo(() => {
    let resultArr = accounts.filter((a) => {
      const m = a.udDir.toString().includes(search);
      if (filter === "ALL") return m; if (filter === "SUCCESS") return m && a.result.includes("SUCCESS"); return m && !a.result.includes("SUCCESS");
    });
    if (sortConfig !== null) {
      resultArr.sort((a, b) => {
        let aVal = a[sortConfig.key as keyof DailyAccount] as any;
        let bVal = b[sortConfig.key as keyof DailyAccount] as any;
        if (typeof aVal === 'string' && typeof bVal === 'string') {
          return sortConfig.direction === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
        }
        if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
        if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
        return 0;
      });
    }
    return resultArr;
  }, [accounts, search, filter, sortConfig]);

  const profitChartData = useMemo(() => {
    return [...accounts]
      .sort((a, b) => b.balanceDifference - a.balanceDifference)
      .slice(0, 30)
      .map((a) => ({
        name: `#${a.udDir}`,
        profit: Number(a.balanceDifference.toFixed(4)),
        isPositive: a.balanceDifference >= 0,
      }));
  }, [accounts]);

  const donutData = useMemo(() => {
    const s = summary.successCount;
    const e = summary.errorCount;
    const c = summary.chestUnavailable;
    const other = summary.totalAccounts - s - e - c;
    return [
      { name: "Success", value: s, fill: isColor ? "#22c55e" : "#ffffff" },
      { name: "Error", value: e, fill: isColor ? "#ef4444" : "#555555" },
      { name: "Chest N/A", value: c, fill: isColor ? "#f59e0b" : "#333333" },
      ...(other > 0 ? [{ name: "Other", value: other, fill: isColor ? "#1e2a50" : "#1e1e1e" }] : []),
    ].filter(d => d.value > 0);
  }, [summary, isColor]);

  const balanceData = useMemo(() => {
    return [...accounts]
      .sort((a, b) => b.endBalance - a.endBalance)
      .slice(0, 25)
      .map((a) => ({
        name: `#${a.udDir}`,
        start: Number(a.startBalance.toFixed(2)),
        end: Number(a.endBalance.toFixed(2)),
      }));
  }, [accounts]);

  const chestChartData = useMemo(() => {
    return [...accounts]
      .filter(a => a.chestAmount > 0)
      .sort((a, b) => b.chestAmount - a.chestAmount)
      .map(a => ({
        name: `#${a.udDir}`,
        chest: Number(a.chestAmount.toFixed(2)),
      }));
  }, [accounts]);

  const solAreaData = useMemo(() => {
    return [...accounts]
      .filter(a => a.solBalanceDifference !== 0)
      .sort((a, b) => a.udDir - b.udDir)
      .map((a) => ({
        name: `#${a.udDir}`,
        sol: Number(a.solBalanceDifference.toFixed(6)),
      }));
  }, [accounts]);

  const successRate = summary.totalAccounts > 0 ? ((summary.successCount / summary.totalAccounts) * 100).toFixed(1) : "0";

  if (loading) return <div className="flex items-center justify-center py-20 text-[#999]"><Loader2 className="h-5 w-5 animate-spin mr-2" /><span className="bw-label text-sm">Loading...</span></div>;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center gap-2">
        <button onClick={() => setSubTab("results")} className={cn(
          "flex items-center gap-1.5 px-3 py-1.5 rounded-sm mono text-xs tracking-widest uppercase transition-all",
          subTab === "results" ? "bg-white text-black" : "text-[#aaa] border border-[#1e1e1e] hover:border-[#333] hover:text-white"
        )}><BarChart3 className="h-3.5 w-3.5" /> Results</button>
        <button onClick={() => setSubTab("timeline")} className={cn(
          "flex items-center gap-1.5 px-3 py-1.5 rounded-sm mono text-xs tracking-widest uppercase transition-all",
          subTab === "timeline" ? "bg-white text-black" : "text-[#aaa] border border-[#1e1e1e] hover:border-[#333] hover:text-white"
        )}><Calendar className="h-3.5 w-3.5" /> Timeline</button>
        <button onClick={() => setSubTab("bonuses")} className={cn(
          "flex items-center gap-1.5 px-3 py-1.5 rounded-sm mono text-xs tracking-widest uppercase transition-all",
          subTab === "bonuses" ? "bg-white text-black" : "text-[#aaa] border border-[#1e1e1e] hover:border-[#333] hover:text-white"
        )}><Clock className="h-3.5 w-3.5" /> Bonuses</button>
      </div>

      {subTab === "timeline" && (
        <div className="space-y-6 animate-fade-in">
          {timelineLoading ? (
            <div className="flex items-center justify-center py-20 text-[#999]">
              <Loader2 className="h-5 w-5 animate-spin mr-2" />
              <span className="bw-label text-sm">Loading timeline...</span>
            </div>
          ) : timelineError ? (
            <div className="bw-card rounded-sm p-8 flex flex-col items-center justify-center min-h-[300px] text-center">
              <Calendar className="h-8 w-8 text-[#444] mb-4" />
              <h3 className="text-base font-semibold text-[#ccc] mb-2 tech-font">API Error</h3>
              <p className="text-[#666] text-xs mono max-w-md break-all">{timelineError}</p>
              <p className="text-[#555] text-xs mono mt-2">Check Flask server logs or restart the dashboard</p>
            </div>
          ) : timeline.length === 0 ? (
            <div className="bw-card rounded-sm p-8 flex flex-col items-center justify-center min-h-[300px] text-center">
              <Calendar className="h-8 w-8 text-[#444] mb-4" />
              <h3 className="text-base font-semibold text-[#ccc] mb-2 tech-font">No Timeline Data</h3>
              <p className="text-[#666] text-sm mono">Run daily tasks to populate the timeline</p>
            </div>
          ) : (<>
            {/* Summary cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <Metric label="Days Tracked" value={String(timeline.length)} />
              <Metric label="Total Profit" value={`+$${timeline.reduce((s, d) => s + d.profit_usd, 0).toFixed(2)}`} accent />
              <Metric label="Total SOL" value={`+${timeline.reduce((s, d) => s + d.profit_sol, 0).toFixed(4)}`} />
              <Metric label="Best Day" value={`+$${Math.max(...timeline.map(d => d.profit_usd)).toFixed(2)}`} accent />
            </div>

            {/* Charts grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

              {/* Profit USD trend */}
              <div className="bw-card rounded-sm p-5">
                <div className="flex items-center gap-2 mb-4">
                  <TrendingUp className="h-3.5 w-3.5 text-[#666]" />
                  <span className="bw-label">Daily Profit (USD)</span>
                </div>
                <div className="h-[220px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={timeline} margin={{ left: 10, right: 10, top: 10, bottom: 0 }}>
                      <defs>
                        <linearGradient id="profitGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={isColor ? "rgba(34,197,94,0.4)" : "rgba(255,255,255,0.25)"} stopOpacity={0.8} />
                          <stop offset="95%" stopColor={isColor ? "rgba(34,197,94,0)" : "rgba(255,255,255,0)"} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" vertical={false} />
                      <XAxis dataKey="date" tick={{ fill: '#888', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} axisLine={{ stroke: '#1e1e1e' }} tickLine={false} />
                      <YAxis tick={{ fill: '#888', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v.toFixed(0)}`} />
                      <Tooltip content={<ChartTooltipContent />} />
                      <Area type="monotone" dataKey="profit_usd" name="Profit USD" stroke={isColor ? "#22c55e" : "rgba(255,255,255,0.6)"} strokeWidth={1.5} fill="url(#profitGrad)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* SOL Profit trend */}
              <div className="bw-card rounded-sm p-5">
                <div className="flex items-center gap-2 mb-4">
                  <TrendingUp className="h-3.5 w-3.5 text-[#666]" />
                  <span className="bw-label">Daily Profit (SOL)</span>
                </div>
                <div className="h-[220px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={timeline} margin={{ left: 10, right: 10, top: 10, bottom: 0 }}>
                      <defs>
                        <linearGradient id="solTlGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={isColor ? "rgba(59,214,198,0.4)" : "rgba(255,255,255,0.25)"} stopOpacity={0.8} />
                          <stop offset="95%" stopColor={isColor ? "rgba(59,214,198,0)" : "rgba(255,255,255,0)"} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" vertical={false} />
                      <XAxis dataKey="date" tick={{ fill: '#888', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} axisLine={{ stroke: '#1e1e1e' }} tickLine={false} />
                      <YAxis tick={{ fill: '#888', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v.toFixed(3)}`} />
                      <Tooltip content={<ChartTooltipContent />} />
                      <Area type="monotone" dataKey="profit_sol" name="Profit SOL" stroke={isColor ? "#3bd6c6" : "rgba(255,255,255,0.6)"} strokeWidth={1.5} fill="url(#solTlGrad)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Avg Drop per day */}
              <div className="bw-card rounded-sm p-5">
                <div className="flex items-center gap-2 mb-4">
                  <BarChart3 className="h-3.5 w-3.5 text-[#666]" />
                  <span className="bw-label">Avg Drop per Day</span>
                </div>
                <div className="h-[220px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={timeline} margin={{ left: 10, right: 10, top: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" vertical={false} />
                      <XAxis dataKey="date" tick={{ fill: '#888', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} axisLine={{ stroke: '#1e1e1e' }} tickLine={false} />
                      <YAxis tick={{ fill: '#888', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v.toFixed(3)}`} />
                      <Tooltip content={<ChartTooltipContent />} />
                      <Bar dataKey="avg_drop" name="Avg Drop" radius={[2, 2, 0, 0]} maxBarSize={20}>
                        {timeline.map((entry, i) => (
                          <Cell key={i} fill={entry.avg_drop >= 0
                            ? (isColor ? "rgba(34,197,94,0.7)" : "rgba(255,255,255,0.55)")
                            : (isColor ? "rgba(239,68,68,0.6)" : "rgba(255,255,255,0.15)")} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Balance USD over time */}
              <div className="bw-card rounded-sm p-5">
                <div className="flex items-center gap-2 mb-4">
                  <ArrowUpDown className="h-3.5 w-3.5 text-[#666]" />
                  <span className="bw-label">Total Balance USD</span>
                </div>
                <div className="h-[220px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={timeline} margin={{ left: 10, right: 10, top: 10, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" vertical={false} />
                      <XAxis dataKey="date" tick={{ fill: '#888', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} axisLine={{ stroke: '#1e1e1e' }} tickLine={false} />
                      <YAxis tick={{ fill: '#888', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`} />
                      <Tooltip content={<ChartTooltipContent />} />
                      <Line type="monotone" dataKey="balance_usd" name="Balance USD" stroke={isColor ? "rgba(75,124,255,0.9)" : "rgba(255,255,255,0.6)"} strokeWidth={1.5} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Balance SOL over time */}
              <div className="bw-card rounded-sm p-5">
                <div className="flex items-center gap-2 mb-4">
                  <ArrowUpDown className="h-3.5 w-3.5 text-[#666]" />
                  <span className="bw-label">Total Balance SOL</span>
                </div>
                <div className="h-[220px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={timeline} margin={{ left: 10, right: 10, top: 10, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" vertical={false} />
                      <XAxis dataKey="date" tick={{ fill: '#888', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} axisLine={{ stroke: '#1e1e1e' }} tickLine={false} />
                      <YAxis tick={{ fill: '#888', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v.toFixed(2)}`} />
                      <Tooltip content={<ChartTooltipContent />} />
                      <Line type="monotone" dataKey="balance_sol" name="Balance SOL" stroke={isColor ? "#3bd6c6" : "rgba(255,255,255,0.6)"} strokeWidth={1.5} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Total Chest over time */}
              {timeline.some(d => (d.total_chest || 0) > 0) && (
                <div className="bw-card rounded-sm p-5 lg:col-span-2">
                  <div className="flex items-center gap-2 mb-4">
                    <Box className="h-3.5 w-3.5 text-[#666]" />
                    <span className="bw-label">Total Chest Amount over Time</span>
                  </div>
                  <div className="h-[220px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={timeline} margin={{ left: 10, right: 10, top: 10, bottom: 0 }}>
                        <defs>
                          <linearGradient id="chestTlGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={isColor ? "rgba(251,191,36,0.4)" : "rgba(255,255,255,0.25)"} stopOpacity={0.8} />
                            <stop offset="95%" stopColor={isColor ? "rgba(251,191,36,0)" : "rgba(255,255,255,0)"} stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" vertical={false} />
                        <XAxis dataKey="date" tick={{ fill: '#888', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} axisLine={{ stroke: '#1e1e1e' }} tickLine={false} />
                        <YAxis tick={{ fill: '#888', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v.toFixed(0)}`} />
                        <Tooltip content={<ChartTooltipContent />} />
                        <Area type="monotone" dataKey="total_chest" name="Total Chest $" stroke={isColor ? "rgba(251,191,36,0.9)" : "rgba(255,255,255,0.6)"} strokeWidth={1.5} fill="url(#chestTlGrad)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
            </div>

            {/* Date table */}
            <div className="bw-card rounded-sm p-5">
              <div className="flex items-center gap-2 mb-4">
                <Calendar className="h-3.5 w-3.5 text-[#666]" />
                <span className="bw-label">Run History · {timeline.length} days</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs mono">
                  <thead>
                    <tr className="border-b border-[#1a1a1a]">
                      {["Date", "File", "Profit USD", "Profit SOL", "Balance USD", "Balance SOL", "Avg Drop", "Chest $"].map(h => (
                        <th key={h} className="text-left text-[#666] font-medium py-2 pr-4 uppercase tracking-widest text-[0.6rem]">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[...timeline].reverse().map((row, i) => (
                      <tr key={i} className="border-b border-[#111] hover:bg-white/[0.02] transition-colors">
                        <td className="py-2.5 pr-4 font-semibold text-white">{row.date}</td>
                        <td className="py-2.5 pr-4 text-[#555]">{row.file}</td>
                        <td className={cn("py-2.5 pr-4 font-semibold", row.profit_usd > 0 ? "text-white/80" : "text-[#888]")}>
                          {row.profit_usd >= 0 ? "+" : ""}${row.profit_usd.toFixed(2)}
                        </td>
                        <td className="py-2.5 pr-4 text-[#aaa]">+{row.profit_sol.toFixed(4)}</td>
                        <td className="py-2.5 pr-4 text-[#ccc]">${row.balance_usd.toFixed(2)}</td>
                        <td className="py-2.5 pr-4 text-[#aaa]">{row.balance_sol.toFixed(4)}</td>
                        <td className={cn("py-2.5 pr-4", row.avg_drop >= 0 ? "text-white/70" : "text-[#888]")}>
                          {row.avg_drop >= 0 ? "+" : ""}${row.avg_drop.toFixed(4)}
                        </td>
                        <td className="py-2.5 pr-4">
                          {(row.total_chest || 0) > 0
                            ? <span className={cn("mono text-xs font-semibold px-1.5 py-0.5 rounded-sm", isColor ? "text-yellow-300/90" : "text-white/70")}>${(row.total_chest || 0).toFixed(2)}</span>
                            : <span className="text-[#555]">—</span>
                          }
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>)}
        </div>
      )}

      {/* ─────── BONUSES SUB-TAB ─────── */}
      {subTab === "bonuses" && (
        <div className="space-y-6 animate-fade-in">
          {bonusLoading ? (
            <div className="flex items-center justify-center py-20 text-[#999]">
              <Loader2 className="h-5 w-5 animate-spin mr-2" />
              <span className="bw-label text-sm">Loading bonuses...</span>
            </div>
          ) : bonuses.length === 0 ? (
            <div className="bw-card rounded-sm p-8 flex flex-col items-center justify-center min-h-[300px] text-center">
              <Clock className="h-8 w-8 text-[#444] mb-4" />
              <h3 className="text-base font-semibold text-[#ccc] mb-2 tech-font">No Bonus Data</h3>
              <p className="text-[#666] text-sm mono">Run daily tasks to track weekly and monthly bonus countdowns</p>
            </div>
          ) : (
            <>
              {/* Summary cards */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <Metric label="Tracked" value={String(bonusSummary.total_accounts)} />
                <Metric label="Weekly Ready" value={String(bonusSummary.weekly_available)} accent />
                <Metric label="Monthly Ready" value={String(bonusSummary.monthly_available)} accent />
                <Metric label="No Data Yet" value={String(bonusSummary.no_data)} />
              </div>

              {/* Sort + Search controls */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="bw-label text-xs">Sort:</span>
                <button onClick={() => setBonusSortField('weekly')} className={cn(
                  "px-3 py-1.5 rounded-sm mono text-xs tracking-widest uppercase transition-all",
                  bonusSortField === 'weekly' ? 'bg-white text-black' : 'text-[#aaa] border border-[#1e1e1e] hover:border-[#333] hover:text-white'
                )}>Weekly</button>
                <button onClick={() => setBonusSortField('monthly')} className={cn(
                  "px-3 py-1.5 rounded-sm mono text-xs tracking-widest uppercase transition-all",
                  bonusSortField === 'monthly' ? 'bg-white text-black' : 'text-[#aaa] border border-[#1e1e1e] hover:border-[#333] hover:text-white'
                )}>Monthly</button>
                <div className="relative ml-auto">
                  <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#999]" />
                  <Input placeholder="Search ID..." value={bonusSearch} onChange={(e) => setBonusSearch(e.target.value)}
                    className="pl-8 bg-[#0d0d0d] border-[#1e1e1e] text-white placeholder:text-[#777] text-sm h-8 w-40 rounded-sm mono" />
                </div>
              </div>

              {/* Bonus table */}
              <div className="bw-card rounded-sm p-5">
                <div className="flex items-center gap-2 mb-4">
                  <Clock className="h-3.5 w-3.5 text-[#666]" />
                  <span className="bw-label">Bonus Countdowns · {bonuses.length} accounts</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs mono">
                    <thead>
                      <tr className="border-b border-[#1a1a1a]">
                        {["Account", "Weekly Bonus", "Next Weekly", "Monthly Bonus", "Next Monthly"].map(h => (
                          <th key={h} className="text-left text-[#666] font-medium py-2 pr-4 uppercase tracking-widest text-[0.6rem]">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {[...bonuses]
                        .filter(b => !bonusSearch || b.ud_dir.includes(bonusSearch))
                        .sort((a, b) => {
                          // «доступен сейчас!» идёт первым, «нет данных» — последним
                          const score = (cd: string) =>
                            cd === 'доступен сейчас!' ? 0 : cd === 'нет данных' ? 999 : 1;
                          const field = bonusSortField === 'weekly' ? 'weekly_countdown' : 'monthly_countdown';
                          const diff = score(a[field]) - score(b[field]);
                          if (diff !== 0) return diff;
                          // tie-break by next_at timestamp
                          const na = bonusSortField === 'weekly' ? a.next_weekly_at : a.next_monthly_at;
                          const nb = bonusSortField === 'weekly' ? b.next_weekly_at : b.next_monthly_at;
                          if (!na) return 1; if (!nb) return -1;
                          return na.localeCompare(nb);
                        })
                        .map((b) => {
                          const wAvail = b.weekly_countdown === 'доступен сейчас!';
                          const mAvail = b.monthly_countdown === 'доступен сейчас!';
                          const wNoData = b.weekly_countdown === 'нет данных';
                          const mNoData = b.monthly_countdown === 'нет данных';
                          return (
                            <tr key={b.ud_dir} className="border-b border-[#111] hover:bg-white/[0.02] transition-colors">
                              <td className="py-2.5 pr-4 font-semibold text-white">#{b.ud_dir}</td>
                              <td className="py-2.5 pr-4">
                                <span className={cn(
                                  "px-2 py-0.5 rounded-sm text-xs font-semibold",
                                  wAvail ? (isColor ? 'bg-green-500/20 text-green-400' : 'bg-white/15 text-white') :
                                  wNoData ? 'text-[#555]' :
                                  isColor ? 'text-yellow-300/80' : 'text-[#aaa]'
                                )}>
                                  {wAvail ? '✅ ' : wNoData ? '— ' : '⏳ '}{b.weekly_countdown}
                                </span>
                              </td>
                              <td className="py-2.5 pr-4 text-[#555]">
                                {b.next_weekly_at ? new Date(b.next_weekly_at).toLocaleDateString('ru-RU', { day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit' }) : '—'}
                              </td>
                              <td className="py-2.5 pr-4">
                                <span className={cn(
                                  "px-2 py-0.5 rounded-sm text-xs font-semibold",
                                  mAvail ? (isColor ? 'bg-blue-500/20 text-blue-400' : 'bg-white/15 text-white') :
                                  mNoData ? 'text-[#555]' :
                                  isColor ? 'text-sky-300/80' : 'text-[#aaa]'
                                )}>
                                  {mAvail ? '✅ ' : mNoData ? '— ' : '⏳ '}{b.monthly_countdown}
                                </span>
                              </td>
                              <td className="py-2.5 pr-4 text-[#555]">
                                {b.next_monthly_at ? new Date(b.next_monthly_at).toLocaleDateString('ru-RU', { day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit' }) : '—'}
                              </td>
                            </tr>
                          );
                        })}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {subTab === "results" && <>
      {/* Metrics Row 1 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Metric label="Accounts" value={String(summary.totalAccounts)} />
        <Metric label="Success" value={`${summary.successCount}`} sub={`${successRate}%`} accent />
        <Metric label="Errors" value={`${summary.errorCount}`} sub={`Chest: ${summary.chestUnavailable}`} />
        <Metric label="Avg Drop" value={`${summary.avgDrop >= 0 ? "+" : ""}$${summary.avgDrop.toFixed(4)}`} />
      </div>
      {/* Metrics Row 2 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Metric label="Total Profit" value={`+$${summary.totalProfit.toFixed(2)}`} sub={`+${summary.totalSolProfit.toFixed(4)} SOL`} accent />
        <Metric label="SOL Rate" value={`$${summary.solRate.toFixed(2)}`} />
        <Metric label="Balance USD" value={`$${summary.totalBalanceUsd.toFixed(2)}`} />
        <Metric label="Balance SOL" value={`${summary.totalBalanceSol.toFixed(4)}`} accent />
      </div>
      {/* Metrics Row 3 — Chest */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Metric label="Total Chest 💰" value={`$${summary.totalChestAmount.toFixed(2)}`} accent />
        <Metric label="Planned Tomorrow (+1%)" value={`+$${summary.plannedTomorrow.toFixed(2)}`} sub={`${summary.totalChestAmount.toFixed(2)} × 0.01`} accent />
        <Metric label="Accounts with Chest" value={String(accounts.filter(a => a.chestAmount > 0).length)} />
        <Metric label="Avg Chest" value={`$${accounts.filter(a=>a.chestAmount>0).length > 0 ? (summary.totalChestAmount / accounts.filter(a=>a.chestAmount>0).length).toFixed(2) : '0.00'}`} />
      </div>

      {/* Charts Toggle */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="bw-label text-sm">Analytics</span>
          <div className="flex-1 bw-divider min-w-[40px]" />
        </div>
        <button onClick={() => setShowCharts(!showCharts)}
          className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-sm mono text-xs tracking-widest uppercase transition-all",
            showCharts ? "bg-white text-black" : "text-[#aaa] border border-[#1e1e1e] hover:border-[#333]")}>
          <BarChart3 className="h-3.5 w-3.5" /> {showCharts ? "Hide" : "Show"}
        </button>
      </div>

      {showCharts && accounts.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Success Donut */}
          <div className="bw-card rounded-sm p-5">
            <div className="flex items-center gap-2 mb-4">
              <PieChartIcon className="h-3.5 w-3.5 text-[#666]" />
              <span className="bw-label">Result Distribution</span>
            </div>
            <div className="h-[200px] flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={donutData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={80}
                    paddingAngle={2}
                    dataKey="value"
                    stroke="none"
                  >
                    {donutData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Pie data={[{ value: 1 }]} cx="50%" cy="50%" innerRadius={0} outerRadius={0} dataKey="value">
                    <Cell fill="transparent" />
                    <DonutLabel viewBox={{ cx: "50%", cy: "50%" }} value={`${successRate}%`} label="SUCCESS" />
                  </Pie>
                  <Tooltip content={<ChartTooltipContent />} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex items-center justify-center gap-4 mt-2">
              {donutData.map((d, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: d.fill }} />
                  <span className="mono text-xs text-[#999]">{d.name} ({d.value})</span>
                </div>
              ))}
            </div>
          </div>

          {/* Profit Per Account */}
          <div className="bw-card rounded-sm p-5">
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp className="h-3.5 w-3.5 text-[#666]" />
              <span className="bw-label">Profit per Account (top 30)</span>
            </div>
            <div className="h-[240px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={profitChartData} layout="vertical" margin={{ left: 10, right: 10, top: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" horizontal={false} />
                  <XAxis type="number" tick={{ fill: '#888', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} axisLine={{ stroke: '#1e1e1e' }} tickLine={false} tickFormatter={(v) => `$${v}`} />
                  <YAxis type="category" dataKey="name" tick={{ fill: '#888', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} axisLine={false} tickLine={false} width={42} />
                  <Tooltip content={<ChartTooltipContent />} />
                  <Bar dataKey="profit" name="Profit" radius={[0, 2, 2, 0]} maxBarSize={14}>
                    {profitChartData.map((entry, i) => (
                      <Cell key={i} fill={entry.isPositive ? (isColor ? "#22c55e" : "rgba(255,255,255,0.7)") : (isColor ? "#ef4444" : "rgba(255,255,255,0.15)")} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Balance Comparison */}
          <div className="bw-card rounded-sm p-5">
            <div className="flex items-center gap-2 mb-4">
              <ArrowUpDown className="h-3.5 w-3.5 text-[#666]" />
              <span className="bw-label">Balance: Start vs End (top 25)</span>
            </div>
            <div className="h-[240px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={balanceData} margin={{ left: 10, right: 10, top: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: '#888', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} axisLine={{ stroke: '#1e1e1e' }} tickLine={false} angle={-45} textAnchor="end" height={40} />
                  <YAxis tick={{ fill: '#888', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v}`} />
                  <Tooltip content={<ChartTooltipContent />} />
                  <Bar dataKey="start" name="Start" fill={isColor ? "rgba(75,124,255,0.2)" : "rgba(255,255,255,0.12)"} radius={[2, 2, 0, 0]} maxBarSize={12} />
                  <Bar dataKey="end" name="End" fill={isColor ? "rgba(75,124,255,0.7)" : "rgba(255,255,255,0.5)"} radius={[2, 2, 0, 0]} maxBarSize={12} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="flex items-center justify-center gap-4 mt-2">
              <div className="flex items-center gap-1.5"><span className="h-2 w-6 rounded-sm bg-white/10" /><span className="mono text-xs text-[#999]">Start</span></div>
              <div className="flex items-center gap-1.5"><span className="h-2 w-6 rounded-sm bg-white/50" /><span className="mono text-xs text-[#999]">End</span></div>
            </div>
          </div>

          {/* SOL Profit Area */}
          {solAreaData.length > 0 && (
            <div className="bw-card rounded-sm p-5">
              <div className="flex items-center gap-2 mb-4">
                <TrendingUp className="h-3.5 w-3.5 text-[#666]" />
                <span className="bw-label">SOL Profit Distribution</span>
              </div>
              <div className="h-[240px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={solAreaData} margin={{ left: 10, right: 10, top: 10, bottom: 0 }}>
                    <defs>
                      <linearGradient id="solGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={isColor ? "rgba(59,214,198,0.4)" : "rgba(255,255,255,0.3)"} stopOpacity={0.8} />
                        <stop offset="95%" stopColor={isColor ? "rgba(59,214,198,0)" : "rgba(255,255,255,0)"} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" vertical={false} />
                    <XAxis dataKey="name" tick={{ fill: '#888', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} axisLine={{ stroke: '#1e1e1e' }} tickLine={false} />
                    <YAxis tick={{ fill: '#888', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} axisLine={false} tickLine={false} />
                    <Tooltip content={<ChartTooltipContent />} />
                    <Area type="monotone" dataKey="sol" name="SOL" stroke={isColor ? "#3bd6c6" : "rgba(255,255,255,0.5)"} strokeWidth={1.5} fill="url(#solGrad)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Chest Amount Chart */}
          {chestChartData.length > 0 && (
            <div className="bw-card rounded-sm p-5 lg:col-span-2">
              <div className="flex items-center gap-2 mb-4">
                <Box className="h-3.5 w-3.5 text-[#666]" />
                <span className="bw-label">Chest Amount by Account (desc)</span>
              </div>
              <div className="h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chestChartData} layout="vertical" margin={{ left: 10, right: 10, top: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" horizontal={false} />
                    <XAxis type="number" tick={{ fill: '#888', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} axisLine={{ stroke: '#1e1e1e' }} tickLine={false} tickFormatter={(v) => `$${v}`} />
                    <YAxis type="category" dataKey="name" tick={{ fill: '#888', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} axisLine={false} tickLine={false} width={42} />
                    <Tooltip content={<ChartTooltipContent />} />
                    <Bar dataKey="chest" name="Chest $" radius={[0, 2, 2, 0]} maxBarSize={14}
                      fill={isColor ? "rgba(251,191,36,0.75)" : "rgba(255,255,255,0.6)"} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Account Table */}
      <div className="bw-card rounded-sm p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-5">
          <span className="bw-label text-sm">Accounts · {filtered.length}</span>
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="flex gap-1.5">{(["ALL", "SUCCESS", "ERROR"] as const).map(f => <FilterBtn key={f} active={filter === f} onClick={() => setFilter(f)}>{f === "ALL" ? "All" : f === "SUCCESS" ? "OK" : "Err"}</FilterBtn>)}</div>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#999]" />
              <Input placeholder="Search..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-8 bg-[#0d0d0d] border-[#1e1e1e] text-white placeholder:text-[#777] text-sm h-8 w-40 rounded-sm mono" />
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <Table>
            <TableHeader><TableRow className="border-[#1a1a1a] hover:bg-transparent">
              {
                [
                  { label: "ID", field: "udDir" },
                  { label: "W", field: "workerId" },
                  { label: "Status", field: "result" },
                  { label: "Start", field: "startBalance" },
                  { label: "End", field: "endBalance" },
                  { label: "Profit", field: "balanceDifference" },
                  { label: "SOL", field: "solBalanceDifference" },
                  { label: "Chest $", field: "chestAmount" },
                  { label: "", field: null }
                ].map(h => (
                <TableHead key={h.label} className="bw-label text-[#aaa] text-xs py-3">
                  {h.field ? (
                    <button onClick={() => {
                      let direction: 'asc' | 'desc' = 'asc';
                      if (sortConfig && sortConfig.key === h.field && sortConfig.direction === 'asc') {
                        direction = 'desc';
                      }
                      setSortConfig({ key: h.field, direction });
                    }} className="flex items-center gap-1 hover:text-white transition-colors">
                      {h.label}
                      <ArrowUpDown className={cn("h-3 w-3 transition-opacity", sortConfig?.key === h.field ? "opacity-100" : "opacity-30")} />
                    </button>
                  ) : h.label}
                </TableHead>
              ))}
            </TableRow></TableHeader>
            <TableBody>
              {filtered.length === 0 ? <TableRow><TableCell colSpan={9} className="text-center text-[#888] py-12 bw-label text-sm">No data</TableCell></TableRow>
              : filtered.map((a) => {
                const maxProfit = Math.max(...accounts.map(x => Math.abs(x.balanceDifference)), 0.01);
                const barWidth = Math.min(Math.abs(a.balanceDifference) / maxProfit * 100, 100);
                return (
                <TableRow key={a.udDir} className="border-[#141414] hover:bg-white/[0.02] transition-colors group">
                  <TableCell className="mono font-semibold text-white text-base py-3.5">#{a.udDir}</TableCell>
                  <TableCell><span className="mono text-xs px-2 py-1 rounded-sm bg-[#161616] text-[#bbb] border border-[#1e1e1e]">{a.workerId}</span></TableCell>
                  <TableCell><StatusBadge status={a.result.includes("SUCCESS") ? "SUCCESS" : a.result.includes("CHEST") ? "PENDING" : "ERROR"} /></TableCell>
                  <TableCell className="text-right mono text-sm text-[#ccc]">${a.startBalance.toFixed(2)}</TableCell>
                  <TableCell className="text-right mono text-sm font-medium text-white">${a.endBalance.toFixed(2)}</TableCell>
                  <TableCell className="text-right min-w-[140px]">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-20 h-2 bg-[#1a1a1a] rounded-full overflow-hidden hidden sm:block">
                        <div className={cn("h-full rounded-full transition-all", a.balanceDifference > 0 ? "bg-white/50" : a.balanceDifference < 0 ? "bg-white/15" : "")}
                          style={{ width: `${barWidth}%` }} />
                      </div>
                      <span className={cn("mono text-sm font-semibold", a.balanceDifference > 0 ? "text-white/80" : a.balanceDifference < 0 ? "text-[#888]" : "text-[#888]")}>
                        {a.balanceDifference > 0 ? "+" : ""}{a.balanceDifference !== 0 ? `$${Math.abs(a.balanceDifference).toFixed(2)}` : "$0.00"}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    {a.solBalanceDifference !== 0 ? (
                      <span className={cn("mono text-xs font-semibold px-2 py-1 rounded-sm border", a.solBalanceDifference > 0 ? "bg-white/[0.04] text-white/70 border-white/8" : "bg-white/[0.02] text-[#ccc] border-white/5")}>
                        {a.solBalanceDifference > 0 ? "+" : ""}{a.solBalanceDifference.toFixed(4)}
                      </span>
                    ) : <span className="text-[#888] mono text-sm">0.0000</span>}
                  </TableCell>
                  <TableCell className="text-right">
                    {a.chestAmount > 0 ? (
                      <span className={cn("mono text-xs font-semibold px-2 py-1 rounded-sm border", isColor ? "bg-yellow-500/10 text-yellow-300/90 border-yellow-500/20" : "bg-white/[0.04] text-white/70 border-white/8")}>
                        ${a.chestAmount.toFixed(2)}
                      </span>
                    ) : <span className="text-[#666] mono text-xs">—</span>}
                  </TableCell>
                  <TableCell>
                    <a href={a.link} target="_blank" rel="noopener noreferrer">
                      <button className="p-1.5 rounded-sm text-[#999] hover:text-white transition-colors"><ExternalLink className="h-4 w-4" /></button>
                    </a>
                  </TableCell>
                </TableRow>
              )})}
            </TableBody>
          </Table>
        </div>
      </div>
      </>}
    </div>
  );
};
