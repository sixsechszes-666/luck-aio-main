import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  status: "SUCCESS" | "ERROR" | "PENDING" | "IDLE" | "RUNNING" | "WAITING";
  className?: string;
}

const config = {
  SUCCESS: { dot: "bg-white", text: "text-white/80", bg: "bg-white/[0.06] border-white/10", label: "OK", animate: "", themeClass: "status-success" },
  ERROR: { dot: "bg-[#666]", text: "text-[#888]", bg: "bg-white/[0.03] border-white/5", label: "ERR", animate: "", themeClass: "status-error" },
  PENDING: { dot: "bg-[#555]", text: "text-[#777]", bg: "bg-white/[0.03] border-white/5", label: "WAIT", animate: "", themeClass: "status-pending" },
  IDLE: { dot: "bg-[#333]", text: "text-[#555]", bg: "bg-white/[0.02] border-white/5", label: "IDLE", animate: "", themeClass: "status-idle" },
  RUNNING: { dot: "bg-white", text: "text-white/80", bg: "bg-white/[0.06] border-white/10", label: "RUN", animate: "animate-subtle-pulse", themeClass: "status-running" },
  WAITING: { dot: "bg-[#666]", text: "text-[#888]", bg: "bg-white/[0.04] border-white/8", label: "WAIT", animate: "animate-subtle-pulse", themeClass: "status-waiting" },
};

export const StatusBadge = ({ status, className }: StatusBadgeProps) => {
  const c = config[status];
  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 rounded-sm border px-2.5 py-1",
      "mono text-xs font-medium tracking-[0.15em] uppercase",
      c.bg, c.text, c.themeClass, className
    )}>
      <span className={cn("h-1.5 w-1.5 rounded-full flex-shrink-0 status-dot", c.dot, c.animate)} />
      {c.label}
    </span>
  );
};
