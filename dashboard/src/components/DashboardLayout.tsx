import { useState } from "react";
import { RotateCcw, Menu, X, ArrowRight, Sun, Moon } from "lucide-react";
import { useTheme } from "@/contexts/ThemeContext";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ControlTab } from "@/components/tabs/ControlTab";
import { DailyTasksTab } from "@/components/tabs/DailyTasksTab";
import { WithdrawalsTab } from "@/components/tabs/WithdrawalsTab";
import { WarmupTab } from "@/components/tabs/WarmupTab";
import { RenewTimersTab } from "@/components/tabs/RenewTimersTab";
import { SettingsTab } from "@/components/tabs/SettingsTab";
import { WarmupVolumeBonusesTab } from "@/components/tabs/WarmupVolumeBonusesTab";
import { useToast } from "@/hooks/use-toast";
import { apiRestart } from "@/services/api";
import { cn } from "@/lib/utils";

const tabs = [
  { value: "control", label: "Control" },
  { value: "daily", label: "Daily" },
  { value: "withdrawals", label: "Withdraw" },
  { value: "warmup", label: "Warmup" },
  { value: "warmup_vol", label: "Warmup Vol." },
  { value: "renew", label: "Renew" },
  { value: "settings", label: "Settings" },
];

export const DashboardLayout = () => {
  const [activeTab, setActiveTab] = useState("control");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { toast } = useToast();
  const { theme, toggleTheme, isColor } = useTheme();

  const handleRestart = async () => {
    if (!confirm("Restart bot? All running tasks will be interrupted.")) return;
    try {
      const result = await apiRestart();
      toast({ title: "Restarting", description: result.message || "Bot is restarting..." });
      setTimeout(() => window.location.reload(), 3000);
    } catch {
      toast({ title: "Error", description: "Could not send restart command", variant: "destructive" });
    }
  };

  const handleTabChange = (val: string) => {
    setActiveTab(val);
    setMobileMenuOpen(false);
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 glass border-b border-[#1a1a1a]">
        <div className="mx-auto max-w-[1600px] px-5 sm:px-8 lg:px-12">
          <div className="flex h-14 items-center justify-between">
            <div className="flex items-center gap-6">
              <span className="tech-font text-xl text-white font-bold tracking-tight">Luck.io</span>

              <div className="hidden md:flex items-center gap-0.5">
                {tabs.map((tab) => (
                  <button
                    key={tab.value}
                    onClick={() => handleTabChange(tab.value)}
                    className={cn(
                      "px-3 py-1.5 text-sm tracking-wide transition-all duration-200 rounded-sm",
                      activeTab === tab.value
                        ? "text-white font-medium"
                        : "text-[#777] hover:text-[#bbb]"
                    )}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={handleRestart}
                className="hidden sm:flex items-center gap-1.5 text-xs tracking-wider uppercase text-[#999] hover:text-white transition-colors"
              >
                <RotateCcw className="h-3 w-3" /> Restart
              </button>

              <button
                onClick={toggleTheme}
                className={cn(
                  "hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs tracking-wider uppercase transition-all border",
                  isColor
                    ? "border-blue-500/30 text-blue-400 hover:bg-blue-500/10"
                    : "border-[#333] text-[#777] hover:text-white hover:border-[#555]"
                )}
              >
                {isColor ? <Sun className="h-3 w-3" /> : <Moon className="h-3 w-3" />}
                {isColor ? "Color" : "B&W"}
              </button>

              <div className="hidden sm:block h-5 w-px bg-[#222]" />

              <button
                className="md:hidden p-1 text-[#888] hover:text-white transition-colors"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              >
                {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              </button>
            </div>
          </div>
        </div>

        {mobileMenuOpen && (
          <div className="md:hidden border-t border-[#1a1a1a] bg-[#0a0a0a]/98 animate-fade-in">
            <div className="px-5 py-3 space-y-0.5">
              {tabs.map((tab) => (
                <button
                  key={tab.value}
                  onClick={() => handleTabChange(tab.value)}
                  className={cn(
                    "w-full flex items-center justify-between px-3 py-2.5 text-sm transition-all",
                    activeTab === tab.value ? "text-white" : "text-[#888]"
                  )}
                >
                  <span>{tab.label}</span>
                  {activeTab === tab.value && <ArrowRight className="h-3 w-3" />}
                </button>
              ))}
              <div className="pt-3 border-t border-[#1a1a1a] flex gap-2">
                <button
                  onClick={handleRestart}
                  className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 text-sm text-[#888] hover:text-white transition-colors"
                >
                  <RotateCcw className="h-3.5 w-3.5" /> Restart
                </button>
                <button
                  onClick={toggleTheme}
                  className={cn(
                    "flex-1 flex items-center justify-center gap-2 px-3 py-2.5 text-sm transition-colors",
                    isColor ? "text-blue-400" : "text-[#888] hover:text-white"
                  )}
                >
                  {isColor ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
                  {isColor ? "Color" : "B&W"}
                </button>
              </div>
            </div>
          </div>
        )}
      </nav>

      {/* Header */}
      <div className="mx-auto max-w-[1600px] w-full px-5 sm:px-8 lg:px-12 pt-8 pb-2">
        <h1 className="tech-font text-3xl sm:text-4xl text-white font-bold tracking-tight">
          {tabs.find(t => t.value === activeTab)?.label}
        </h1>
        <div className="bw-divider mt-4" />
      </div>

      {/* Content */}
      <main className="mx-auto max-w-[1600px] w-full px-5 sm:px-8 lg:px-12 py-6 flex-1">
        <Tabs value={activeTab} onValueChange={handleTabChange}>
          <div className="md:hidden mb-5 overflow-x-auto pb-1 no-scrollbar">
            <TabsList className="inline-flex bg-[#111] border border-[#1e1e1e] p-0.5 gap-0 rounded-sm min-w-max">
              {tabs.map((tab) => (
                <TabsTrigger
                  key={tab.value}
                  value={tab.value}
                  className={cn(
                    "px-3 py-1.5 text-xs tracking-widest uppercase rounded-sm transition-all mono",
                    "data-[state=active]:bg-white data-[state=active]:text-black",
                    "data-[state=inactive]:text-[#888]"
                  )}
                >
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>

          <div className="animate-fade-in">
            <TabsContent value="control" className="mt-0"><ControlTab /></TabsContent>
            <TabsContent value="daily" className="mt-0"><DailyTasksTab /></TabsContent>
            <TabsContent value="withdrawals" className="mt-0"><WithdrawalsTab /></TabsContent>
            <TabsContent value="warmup" className="mt-0"><WarmupTab /></TabsContent>
            <TabsContent value="warmup_vol" className="mt-0"><WarmupVolumeBonusesTab /></TabsContent>
            <TabsContent value="renew" className="mt-0"><RenewTimersTab /></TabsContent>
            <TabsContent value="settings" className="mt-0"><SettingsTab /></TabsContent>
          </div>
        </Tabs>
      </main>

      {/* Footer */}
      <footer className="border-t border-[#141414] py-6 px-5 sm:px-8 lg:px-12">
        <div className="mx-auto max-w-[1600px] flex items-center justify-between">
          <span className="mono text-[0.55rem] tracking-widest uppercase text-[#444]">Luck.io Automation</span>
          <span className="mono text-[0.55rem] tracking-widest uppercase text-[#444]">v2.0</span>
        </div>
      </footer>
    </div>
  );
};
