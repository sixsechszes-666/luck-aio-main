import { useState, useEffect, useRef, useCallback } from "react";
import { Activity, Cpu, Play, Square, Users, XCircle, Maximize2, Minimize2, Clock, Timer, Zap } from "lucide-react";
import { Slider } from "@/components/ui/slider";
import { StatusBadge } from "@/components/StatusBadge";
import { taskCards } from "@/data/mockData";
import { apiTaskStart, apiTaskStop, apiTaskStatus, apiTaskWaitAndStart, type TaskStatus } from "@/services/api";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import { useTheme } from "@/contexts/ThemeContext";

export const ControlTab = () => {
  const { toast } = useToast();
  const { isColor } = useTheme();
  const [workers, setWorkers] = useState([1]);
  const [selectedTask, setSelectedTask] = useState("daily");
  const [status, setStatus] = useState<TaskStatus | null>(null);
  const [logLines, setLogLines] = useState<string[]>([]);
  const [errorLines, setErrorLines] = useState<string[]>([]);
  const [logExpanded, setLogExpanded] = useState(false);
  const [errorExpanded, setErrorExpanded] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const stopTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const errorContainerRef = useRef<HTMLDivElement>(null);

  const isRunning = status?.status === "running";
  const isWaiting = status?.status === "waiting";
  const isCompleted = status?.status === "completed";
  const isError = status?.status === "error";
  const isBusy = isRunning || isWaiting;
  const cooldownSeconds = status?.cooldown_remaining ?? 0;
  const hasCooldown = (isCompleted || isError) && cooldownSeconds > 0;
  const progressCurrent = status?.progress_current ?? 0;
  const progressTotal = status?.progress_total ?? 0;
  const hasProgress = progressTotal > 0;
  const progressPercent = hasProgress ? Math.round((progressCurrent / progressTotal) * 100) : 0;
  const waitRemaining = status?.wait_remaining ?? 0;

  const fetchStatus = useCallback(async () => {
    try {
      const data = await apiTaskStatus();
      setStatus(data);
      if (data.log) setLogLines(data.log);
      if (data.errors) setErrorLines(data.errors);
    } catch { }
  }, []);

  const startPolling = useCallback(() => {
    if (stopTimeoutRef.current) { clearTimeout(stopTimeoutRef.current); stopTimeoutRef.current = null; }
    if (pollRef.current) return;
    pollRef.current = setInterval(fetchStatus, 1000);
  }, [fetchStatus]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      stopTimeoutRef.current = setTimeout(() => { clearInterval(pollRef.current!); pollRef.current = null; stopTimeoutRef.current = null; }, 3000);
    }
  }, []);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);
  useEffect(() => { if (isBusy || hasCooldown) startPolling(); else if (status && !isBusy && !hasCooldown) stopPolling(); }, [isBusy, hasCooldown, status, startPolling, stopPolling]);
  useEffect(() => { const el = logContainerRef.current; if (el) { const b = el.scrollHeight - el.clientHeight <= el.scrollTop + 30; if (b) el.scrollTop = el.scrollHeight; } }, [logLines]);
  useEffect(() => { const el = errorContainerRef.current; if (el) { const b = el.scrollHeight - el.clientHeight <= el.scrollTop + 30; if (b) el.scrollTop = el.scrollHeight; } }, [errorLines]);
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); if (stopTimeoutRef.current) clearTimeout(stopTimeoutRef.current); }, []);

  const handleStart = async () => {
    try {
      const result = await apiTaskStart(selectedTask, workers[0]);
      if (result.ok) { startPolling(); toast({ title: "Started", description: result.message }); }
      else { toast({ title: "Error", description: result.message, variant: "destructive" }); fetchStatus(); }
    } catch { toast({ title: "Error", description: "Connection failed", variant: "destructive" }); }
  };

  const handleWaitAndStart = async () => {
    if (cooldownSeconds <= 0) return;
    try {
      const result = await apiTaskWaitAndStart(selectedTask, workers[0], cooldownSeconds);
      if (result.ok) { startPolling(); toast({ title: "Waiting", description: result.message }); }
      else toast({ title: "Error", description: result.message, variant: "destructive" });
    } catch { toast({ title: "Error", description: "Connection failed", variant: "destructive" }); }
  };

  const handleStop = async () => {
    try { const result = await apiTaskStop(); toast({ title: "Stopping", description: result.message }); }
    catch { toast({ title: "Error", description: "Connection failed", variant: "destructive" }); }
  };

  const fmtElapsed = (s: number | null) => { if (s === null) return ""; const m = Math.floor(s / 60); return `${m}m ${s % 60}s`; };
  const fmtWait = (s: number) => { const h = Math.floor(s / 3600); const m = Math.floor((s % 3600) / 60); if (h > 0) return `${h}h ${m}m`; if (m > 0) return `${m}m ${s % 60}s`; return `${s}s`; };

  const colorLogLine = (line: string) => {
    if (isColor) {
      if (line.includes("✅") || line.includes("SUCCESS")) return "text-emerald-400/80";
      if (line.includes("❌") || line.includes("ERROR") || line.includes("⚠️")) return "text-red-400/70";
      if (line.includes("🚀") || line.includes("📋") || line.includes("SEND")) return "text-blue-400/60";
      if (line.includes("•") || line.includes("►")) return "text-blue-300/40";
      return "text-blue-200/50";
    }
    if (line.includes("✅") || line.includes("SUCCESS")) return "text-white/70";
    if (line.includes("❌") || line.includes("ERROR") || line.includes("⚠️")) return "text-[#888]";
    if (line.includes("🚀") || line.includes("📋") || line.includes("SEND")) return "text-[#777]";
    if (line.includes("•") || line.includes("►")) return "text-[#666]";
    return "text-[#888]";
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Status */}
      <div className={cn("bw-card rounded-sm p-5", isRunning && (isColor ? "border-blue-500/20" : "border-white/10"))}>
        <div className="flex items-center justify-between mb-3">
          <span className="bw-label">Status</span>
          <StatusBadge status={isWaiting ? "WAITING" : isRunning ? "RUNNING" : isCompleted ? "SUCCESS" : isError ? "ERROR" : "IDLE"} />
        </div>

        {isWaiting && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs mono">
              <span className="text-amber-400/80">{status?.task_name} — waiting for cooldown</span>
              <span className="text-amber-400 font-bold text-sm animate-subtle-pulse">{fmtWait(waitRemaining)}</span>
            </div>
            <div className="h-1 bg-[#1e1e1e] rounded-full relative overflow-hidden">
              <div className="h-full bg-amber-400/60 rounded-full absolute left-0 top-0 transition-all duration-1000" style={{ width: `${waitRemaining > 0 && cooldownSeconds > 0 ? ((cooldownSeconds - waitRemaining) / cooldownSeconds) * 100 : 0}%` }} />
            </div>
          </div>
        )}

        {(isRunning || isCompleted || isError) && (
          <div className="space-y-2">
            <div className="flex justify-between text-xs mono text-[#999]">
              <span>{status?.task_name}</span>
              <span>{hasProgress && <span className="text-white/80 mr-2">{progressCurrent}/{progressTotal}</span>}{fmtElapsed(status?.elapsed ?? null)}</span>
            </div>
            <div className="h-px bg-[#1e1e1e] relative overflow-hidden">
              <div className={cn("h-full absolute left-0 top-0 transition-all duration-500", isError ? (isColor ? "bg-red-500/40" : "bg-[#555]") : (isColor ? "bg-blue-500/50" : "bg-white/40"), isRunning && !hasProgress && "animate-subtle-pulse")}
                style={{ width: `${hasProgress ? progressPercent : 100}%` }} />
            </div>
          </div>
        )}

        {!status && <p className="text-[#888] text-sm mono italic">Awaiting task launch...</p>}
      </div>

      {/* Controls Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Launch */}
        <div className="bw-card rounded-sm p-5 space-y-5">
          <span className="bw-label">Task Launch</span>

          <div className="space-y-1.5">
            <label className="mono text-xs text-[#999] uppercase tracking-widest">Type</label>
            <select value={selectedTask} onChange={(e) => setSelectedTask(e.target.value)}
              className="w-full rounded-sm border border-[#1e1e1e] bg-[#0d0d0d] px-3 py-2.5 text-sm text-white mono focus:outline-none focus:border-[#333] transition-colors pr-8">
              {taskCards.map((t) => <option key={t.type} value={t.type}>{t.icon} {t.title}</option>)}
            </select>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="mono text-xs text-[#999] uppercase tracking-widest flex items-center gap-1.5"><Users className="h-3.5 w-3.5" /> Workers</span>
              <span className="mono text-sm font-semibold text-white">{workers[0]}</span>
            </div>
            <Slider value={workers} onValueChange={setWorkers} min={1} max={10} step={1}
              className={cn(
                "[&_.relative]:bg-[#1e1e1e]",
                isColor
                  ? "[&>span[role=slider]]:bg-blue-500 [&>span[role=slider]]:border-blue-500 [&>span:first-child]:bg-blue-500/50"
                  : "[&>span[role=slider]]:bg-white [&>span[role=slider]]:border-white [&>span:first-child]:bg-white/50"
              )} />
          </div>

          <div className="flex gap-2">
            {!isBusy ? (
              <>
                <button onClick={handleStart}
                  className="flex-1 flex items-center justify-center gap-2 py-3 rounded-sm bg-white text-black text-xs font-semibold uppercase tracking-[0.15em] hover:bg-white/90 transition-colors">
                  <Play className="h-3.5 w-3.5 fill-current" /> Launch
                </button>
                {(isError || isCompleted) && cooldownSeconds > 0 && (
                  <button onClick={handleWaitAndStart}
                    className="flex-1 flex items-center justify-center gap-2 py-3 rounded-sm border border-amber-500/30 text-amber-400 text-xs font-semibold uppercase tracking-[0.15em] hover:border-amber-500/50 hover:bg-amber-500/5 transition-colors">
                    <Clock className="h-3.5 w-3.5" /> Wait {fmtWait(cooldownSeconds)}
                  </button>
                )}
              </>
            ) : (
              <button onClick={handleStop}
                className="flex-1 flex items-center justify-center gap-2 py-3 rounded-sm border border-[#333] text-[#bbb] text-xs font-semibold uppercase tracking-[0.15em] hover:text-white hover:border-[#555] transition-colors">
                <Square className="h-3.5 w-3.5 fill-current" /> Stop
              </button>
            )}
          </div>
        </div>

        {/* Log */}
        <div className={cn("bw-card rounded-sm p-5 space-y-3", logExpanded && "fixed inset-0 z-[100] rounded-none flex flex-col")}
          style={logExpanded ? { background: "#0a0a0a" } : undefined}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="bw-label">System Log</span>
              {isRunning && <span className="h-1 w-1 rounded-full bg-white animate-subtle-pulse" />}
            </div>
            <button onClick={() => setLogExpanded(!logExpanded)} className="text-[#666] hover:text-white transition-colors">
              {logExpanded ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
            </button>
          </div>
          <div ref={logContainerRef}
            className={cn("rounded-sm terminal-log overflow-y-auto whitespace-pre-wrap bg-[#0c0c0c] border border-[#161616] p-3", logExpanded ? "flex-1 min-h-0" : "h-[240px]")}>
            {logLines.length > 0 ? logLines.map((line, i) => (
              <div key={i} className={cn(colorLogLine(line), "hover:bg-white/[0.01] px-1 rounded-sm")}>{line}</div>
            )) : <span className="text-[#666] italic">Awaiting task launch...</span>}
          </div>
          {errorLines.length > 0 && !logExpanded && (
            <div className={cn("rounded-sm border border-[#222]", errorExpanded && "fixed inset-0 z-[100] rounded-none flex flex-col")}
              style={errorExpanded ? { background: "#0a0a0a" } : undefined}>
              <div className="flex items-center justify-between p-3 pb-2">
                <span className="bw-label text-[#666]">Errors ({errorLines.length})</span>
                <button onClick={() => setErrorExpanded(!errorExpanded)} className="text-[#666] hover:text-white transition-colors">
                  {errorExpanded ? <Minimize2 className="h-3 w-3" /> : <Maximize2 className="h-3 w-3" />}
                </button>
              </div>
              <div ref={errorContainerRef}
                className={cn("mono text-xs leading-relaxed whitespace-pre-wrap overflow-y-auto text-[#666] px-3 pb-3", errorExpanded ? "flex-1 min-h-0 p-4" : "max-h-[100px]")}>
                {errorLines.map((line, i) => <div key={i}>{line}</div>)}
              </div>
            </div>
          )}
          {errorLines.length > 0 && errorExpanded && !logExpanded && (
            <div className="fixed inset-0 z-[100] flex flex-col p-5" style={{ background: "#0a0a0a" }}>
              <div className="flex items-center justify-between mb-3">
                <span className="bw-label text-[#666]">Errors</span>
                <button onClick={() => setErrorExpanded(false)} className="text-[#666] hover:text-white"><Minimize2 className="h-4 w-4" /></button>
              </div>
              <div ref={errorContainerRef} className="flex-1 min-h-0 rounded-sm border border-[#1e1e1e] bg-[#0c0c0c] p-4 overflow-y-auto mono text-sm leading-loose whitespace-pre-wrap text-[#666]">
                {errorLines.map((line, i) => <div key={i}>{line}</div>)}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Task Grid */}
      <div>
        <div className="flex items-center gap-3 mb-4">
          <span className="bw-label">Available Tasks</span>
          <div className="flex-1 bw-divider" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {taskCards.map((card) => (
            <button key={card.type} onClick={() => setSelectedTask(card.type)}
              className={cn(
                "bw-card rounded-sm p-4 text-left hover-lift transition-all group",
                selectedTask === card.type ? (isColor ? "border-blue-500/25 bg-blue-500/[0.05]" : "border-white/20 bg-white/[0.03]") : ""
              )}>
              <div className="text-lg mb-2 opacity-60 group-hover:opacity-100 transition-opacity">{card.icon}</div>
              <h4 className={cn("text-sm font-medium transition-colors", selectedTask === card.type ? "text-white" : "text-[#aaa] group-hover:text-white")}>{card.title}</h4>
              <p className="text-xs text-[#999] mt-1 leading-snug mono">{card.description}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
