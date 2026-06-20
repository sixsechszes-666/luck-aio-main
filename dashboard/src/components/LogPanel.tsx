import { useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { LogEntry } from "@/data/mockData";

interface LogPanelProps {
  logs: LogEntry[];
  className?: string;
}

const levelColors: Record<string, string> = {
  INFO: "text-primary",
  WARN: "text-warning",
  ERROR: "text-destructive",
  SUCCESS: "text-success",
};

export const LogPanel = ({ logs, className }: LogPanelProps) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className={cn("glass-card rounded-lg overflow-hidden", className)}>
      <div className="flex items-center gap-2 border-b border-border/50 px-4 py-2.5">
        <div className="flex gap-1.5">
          <span className="h-3 w-3 rounded-full bg-destructive/70" />
          <span className="h-3 w-3 rounded-full bg-warning/70" />
          <span className="h-3 w-3 rounded-full bg-success/70" />
        </div>
        <span className="text-xs text-muted-foreground font-medium">Live Logs — TaskManager</span>
      </div>
      <div className="h-72 overflow-y-auto p-4 bg-background/40">
        {logs.map((log, i) => (
          <div key={i} className="terminal-log">
            <span className="text-muted-foreground">[{log.timestamp}]</span>{" "}
            <span className={cn("font-semibold", levelColors[log.level])}>[{log.level}]</span>{" "}
            <span className="text-foreground/80">{log.message}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};
