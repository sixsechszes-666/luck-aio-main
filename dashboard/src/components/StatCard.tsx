import { cn } from "@/lib/utils";
import { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: string;
  trendUp?: boolean;
  accent?: boolean;
  className?: string;
}

export const StatCard = ({ title, value, icon: Icon, trend, trendUp, accent, className }: StatCardProps) => (
  <div className={cn("bw-card rounded-sm p-5 hover-lift", accent && "border-white/10", className)}>
    <div className="flex items-start justify-between gap-3">
      <div className="flex-1 min-w-0">
        <p className="bw-label mb-2">{title}</p>
        <p className={cn("text-xl font-semibold bw-value truncate", accent ? "text-white" : "text-[#ccc]")}>{value}</p>
        {trend && (
          <p className={cn("mt-1.5 text-[0.65rem] mono", trendUp ? "text-[#999]" : "text-[#666]")}>
            {trendUp ? "+" : "-"}{trend}
          </p>
        )}
      </div>
      <Icon className="h-4 w-4 text-[#555] flex-shrink-0 mt-0.5" />
    </div>
  </div>
);
