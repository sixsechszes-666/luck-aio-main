import { useState, useEffect, useMemo } from "react";
import { Search, Wallet, CheckCircle2, XCircle, DollarSign, ExternalLink, Loader2, ArrowUpDown } from "lucide-react";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/StatusBadge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type WithdrawAccount, type WithdrawSummary } from "@/data/mockData";
import { apiGetWithdraw } from "@/services/api";
import { cn } from "@/lib/utils";

const emptySummary: WithdrawSummary = { totalAccounts: 0, successCount: 0, errorCount: 0, totalWithdrawn: 0, totalSolWithdrawn: 0 };

const Metric = ({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: boolean }) => (
  <div className={cn("bw-card rounded-sm p-5", accent && "border-white/10")}>
    <p className="bw-label mb-2 text-xs">{label}</p>
    <p className={cn("text-2xl font-semibold bw-value", accent ? "text-white" : "text-[#ddd]")}>{value}</p>
    {sub && <p className="text-xs text-[#999] mt-1.5 mono">{sub}</p>}
  </div>
);

const FilterBtn = ({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) => (
  <button onClick={onClick} className={cn("px-3 py-1.5 rounded-sm mono text-xs tracking-widest uppercase transition-all", active ? "bg-white text-black" : "text-[#aaa] hover:text-white border border-[#1e1e1e] hover:border-[#333]")}>{children}</button>
);

export const WithdrawalsTab = () => {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"ALL" | "SUCCESS" | "ERROR">("ALL");
  const [accounts, setAccounts] = useState<WithdrawAccount[]>([]);
  const [summary, setSummary] = useState<WithdrawSummary>(emptySummary);
  const [loading, setLoading] = useState(true);
  const [sortConfig, setSortConfig] = useState<{key: string, direction: 'asc'|'desc'} | null>(null);

  useEffect(() => {
    setLoading(true);
    apiGetWithdraw().then((res) => {
      if (res.data && res.summary) {
        setAccounts(res.data.map((r: any) => ({ udDir: r.UD_DIR, workerId: r.WORKER_ID, walletAddress: r.WALLET_ADDRESS || "", result: r.RESULT, startBalance: r.START_BALANCE || 0, startSolBalance: r.START_SOL_BALANCE || 0, withdrawnAmount: r.WITHDRAWN_AMOUNT_USD || 0, keptAmount: r.KEPT_AMOUNT_USD || 0, link: r.LINK || "" })));
        setSummary({ totalAccounts: res.summary.total_accounts, successCount: res.summary.success_count, errorCount: res.summary.error_count, totalWithdrawn: res.summary.total_withdrawn, totalSolWithdrawn: res.summary.total_sol_withdrawn });
      }
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    let resultArr = accounts.filter((a) => {
      const m = a.udDir.toString().includes(search) || a.walletAddress.toLowerCase().includes(search.toLowerCase());
      if (filter === "ALL") return m; if (filter === "SUCCESS") return m && a.result === "SUCCESS"; return m && a.result !== "SUCCESS";
    });
    if (sortConfig !== null) {
      resultArr.sort((a, b) => {
        let aVal = (a as any)[sortConfig.key];
        let bVal = (b as any)[sortConfig.key];
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

  if (loading) return <div className="flex items-center justify-center py-20 text-[#999]"><Loader2 className="h-5 w-5 animate-spin mr-2" /><span className="bw-label text-sm">Loading...</span></div>;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Metric label="Total" value={String(summary.totalAccounts)} />
        <Metric label="Success" value={String(summary.successCount)} sub={`${summary.totalAccounts > 0 ? ((summary.successCount / summary.totalAccounts) * 100).toFixed(1) : 0}%`} accent />
        <Metric label="Withdrawn" value={`$${summary.totalWithdrawn.toFixed(2)}`} sub={`${summary.totalSolWithdrawn.toFixed(4)} SOL`} accent />
        <Metric label="Errors" value={String(summary.errorCount)} />
      </div>

      <div className="bw-card rounded-sm p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-5">
          <span className="bw-label text-sm">Withdrawals · {filtered.length}</span>
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
                { label: "Wallet", field: "walletAddress" },
                { label: "Status", field: "result" },
                { label: "Start $", field: "startBalance" },
                { label: "SOL", field: "startSolBalance" },
                { label: "Withdrawn $", field: "withdrawnAmount" },
                { label: "Kept $", field: "keptAmount" },
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
              : filtered.map((a) => (
                <TableRow key={a.udDir} className="border-[#141414] hover:bg-white/[0.02] transition-colors">
                  <TableCell className="mono font-semibold text-white text-base py-3.5">#{a.udDir}</TableCell>
                  <TableCell><span className="mono text-xs px-2 py-1 rounded-sm bg-[#161616] text-[#bbb] border border-[#1e1e1e]">{a.workerId}</span></TableCell>
                  <TableCell className="mono text-sm text-[#ccc] max-w-[160px] truncate">{a.walletAddress}</TableCell>
                  <TableCell><StatusBadge status={a.result === "SUCCESS" ? "SUCCESS" : "ERROR"} /></TableCell>
                  <TableCell className="mono text-base font-medium text-white">${a.startBalance.toFixed(2)}</TableCell>
                  <TableCell>
                    {a.startSolBalance > 0 ? <span className="mono text-xs font-semibold px-2 py-1 rounded-sm bg-white/[0.04] text-white/70 border border-white/8">{a.startSolBalance.toFixed(4)}</span>
                    : <span className="mono text-sm text-[#888]">0.0000</span>}
                  </TableCell>
                  <TableCell className="mono text-base font-medium text-green-400">${(a.withdrawnAmount || 0).toFixed(2)}</TableCell>
                  <TableCell className="mono text-base font-medium text-yellow-400">${(a.keptAmount || 0).toFixed(2)}</TableCell>
                  <TableCell>
                    <a href={a.link} target="_blank" rel="noopener noreferrer"><button className="p-1.5 rounded-sm text-[#999] hover:text-white transition-colors"><ExternalLink className="h-4 w-4" /></button></a>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  );
};
