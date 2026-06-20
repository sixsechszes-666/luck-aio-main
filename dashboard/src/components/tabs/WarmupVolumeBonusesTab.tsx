import { useState, useEffect, useMemo } from "react";
import { Search, ExternalLink, Loader2, BarChart3, PieChart as PieChartIcon, TrendingUp, ArrowUpDown, Clock, Calendar } from "lucide-react";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/StatusBadge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type DailyAccount, type DailySummary } from "@/data/mockData";
import { apiGetWarmupVolumeBonuses } from "@/services/api";
import { cn } from "@/lib/utils";
import { useTheme } from "@/contexts/ThemeContext";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie,
  AreaChart, Area,
  CartesianGrid,
} from "recharts";

const emptySummary: DailySummary = { totalAccounts: 0, successCount: 0, errorCount: 0, chestUnavailable: 0, avgDrop: 0, totalProfit: 0, totalSolProfit: 0, solRate: 0, totalBalanceUsd: 0, totalBalanceSol: 0 };

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

export const WarmupVolumeBonusesTab = () => {
  const { isColor } = useTheme();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"ALL" | "SUCCESS" | "ERROR">("ALL");
  const [accounts, setAccounts] = useState<DailyAccount[]>([]);
  const [summary, setSummary] = useState<DailySummary>(emptySummary);
  const [loading, setLoading] = useState(true);
  const [showCharts, setShowCharts] = useState(true);
  const [subTab, setSubTab] = useState<"results" | "timeline">("results");
  const [sortConfig, setSortConfig] = useState<{key: string, direction: 'asc'|'desc'} | null>(null);

  useEffect(() => {
    setLoading(true);
    apiGetWarmupVolumeBonuses().then((res) => {
      if (res.data && res.summary) {
        setAccounts(res.data.map((r: any) => ({ udDir: r.UD_DIR, workerId: r.WORKER_ID, result: r.RESULT, startBalance: r.START_BALANCE || 0, endBalance: r.END_BALANCE || 0, balanceDifference: r.BALANCE_DIFFERENCE || 0, solBalanceDifference: r.SOL_BALANCE_DIFFERENCE || 0, link: r.LINK || "" })));
        setSummary({ totalAccounts: res.summary.total_accounts, successCount: res.summary.success_count, errorCount: res.summary.error_count, chestUnavailable: res.summary.chest_unavailable, avgDrop: res.summary.avg_drop, totalProfit: res.summary.total_profit, totalSolProfit: res.summary.total_sol_profit, solRate: res.summary.sol_rate, totalBalanceUsd: res.summary.total_balance_usd, totalBalanceSol: res.summary.total_balance_sol });
      }
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

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
      </div>

      {subTab === "timeline" && (
        <div className="bw-card rounded-sm p-8 flex flex-col items-center justify-center min-h-[400px] text-center">
          <div className="w-16 h-16 rounded-full border border-[#222] flex items-center justify-center mb-5">
            <Clock className="h-7 w-7 text-[#444]" />
          </div>
          <h3 className="text-lg font-semibold text-[#ccc] mb-2 tech-font">Warmup Timeline</h3>
          <p className="text-[#777] text-sm max-w-md mb-6 mono">
            Visual timeline of warmup runs, task durations, and historical performance trends. Coming in a future update.
          </p>
          <div className="flex items-center gap-4 text-[0.6rem] text-[#555] mono tracking-widest uppercase">
            <span>Run History</span>
            <span className="text-[#333]">|</span>
            <span>Duration Charts</span>
            <span className="text-[#333]">|</span>
            <span>Trend Analysis</span>
          </div>
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
              {[
                { label: "ID", field: "udDir" },
                { label: "W", field: "workerId" },
                { label: "Status", field: "result" },
                { label: "Start", field: "startBalance" },
                { label: "End", field: "endBalance" },
                { label: "Profit", field: "balanceDifference" },
                { label: "SOL", field: "solBalanceDifference" },
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
              {filtered.length === 0 ? <TableRow><TableCell colSpan={8} className="text-center text-[#888] py-12 bw-label text-sm">No data</TableCell></TableRow>
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
