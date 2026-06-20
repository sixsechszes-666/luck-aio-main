import { useState, useEffect } from "react";
import { Save, Settings, Loader2, Globe } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { type SettingItem } from "@/data/mockData";
import { apiGetSettings, apiSaveSettings, getApiBaseUrl, setApiBaseUrl } from "@/services/api";
import { cn } from "@/lib/utils";

interface SettingsGroupData { name: string; settings: SettingItem[]; }

export const SettingsTab = () => {
  const { toast } = useToast();
  const [groups, setGroups] = useState<SettingsGroupData[]>([]);
  const [values, setValues] = useState<Record<string, string | number | boolean>>({});
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [apiUrl, setApiUrl] = useState(getApiBaseUrl());

  useEffect(() => {
    const fetch = async () => {
      setLoading(true);
      try {
        const g = await apiGetSettings();
        if (g && Array.isArray(g)) {
          const mapped: SettingsGroupData[] = g.map((x: any) => ({ name: x.name, settings: (x.settings_list || x.settings || []).map((s: any) => ({ key: s.key, value: s.value, type: s.type })) }));
          setGroups(mapped);
          const v: Record<string, any> = {};
          mapped.forEach(g => g.settings.forEach(s => v[s.key] = s.value));
          setValues(v);
        }
      } catch { } finally { setLoading(false); }
    };
    fetch();
  }, []);

  const updateValue = (key: string, v: string | number | boolean) => setValues(p => ({ ...p, [key]: v }));

  const handleSave = async () => {
    setSaving(true);
    try {
      const r = await apiSaveSettings(values);
      toast({ title: r.ok ? "Saved" : "Error", description: r.ok ? r.message + " (restart required)" : r.message, variant: r.ok ? "default" : "destructive" });
    } catch { toast({ title: "Error", description: "Connection failed", variant: "destructive" }); }
    finally { setSaving(false); }
  };

  const handleApiUrlSave = () => { setApiBaseUrl(apiUrl); toast({ title: "Updated", description: `URL: ${apiUrl || "(current)"}` }); window.location.reload(); };

  const renderInput = (item: SettingItem) => {
    const val = values[item.key];
    if (item.type === "checkbox") return (
      <div className="flex items-center gap-3">
        <Switch checked={val as boolean} onCheckedChange={(c) => updateValue(item.key, c)} className="data-[state=checked]:bg-white" />
        <span className={cn("mono text-sm", val ? "text-white" : "text-[#999]")}>{val ? "ON" : "OFF"}</span>
      </div>
    );
    return <Input type={item.type === "number" || item.type === "float" ? "number" : "text"} step={item.type === "float" ? "0.0001" : "1"} value={val as string | number}
      onChange={(e) => updateValue(item.key, item.type === "number" ? parseInt(e.target.value) || 0 : item.type === "float" ? parseFloat(e.target.value) || 0 : e.target.value)}
      className="bg-[#0d0d0d] border-[#1e1e1e] text-white mono text-sm h-10 rounded-sm focus:border-[#333]" />;
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="bw-card rounded-sm p-6">
        <span className="bw-label text-sm">Server Connection</span>
        <div className="flex gap-3 mt-3">
          <Input placeholder="http://localhost:5000" value={apiUrl} onChange={(e) => setApiUrl(e.target.value)}
            className="bg-[#0d0d0d] border-[#1e1e1e] text-white mono text-sm flex-1 rounded-sm focus:border-[#333] h-10" />
          <button onClick={handleApiUrlSave}
            className="px-5 py-2.5 rounded-sm border border-[#333] text-white/80 mono text-xs tracking-widest uppercase hover:bg-white/5 transition-colors flex items-center gap-2 whitespace-nowrap">
            <Globe className="h-3.5 w-3.5" /> Connect
          </button>
        </div>
        <p className="mono text-xs text-[#888] mt-2.5">Set Flask server address. Leave empty if same server.</p>
      </div>

      <div className="bw-card rounded-sm p-6 border-white/8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <span className="bw-label text-sm">Configuration</span>
            <p className="text-sm text-[#999] mt-1.5">Edit bot parameters (.env). Restart required after saving.</p>
          </div>
          <button onClick={handleSave} disabled={saving}
            className="flex items-center gap-2 px-6 py-3 rounded-sm bg-white text-black mono text-xs font-semibold tracking-widest uppercase hover:bg-white/90 disabled:opacity-40 transition-all whitespace-nowrap">
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-[#999]"><Loader2 className="h-5 w-5 animate-spin mr-2" /><span className="bw-label text-sm">Loading...</span></div>
      ) : groups.length === 0 ? (
        <div className="bw-card rounded-sm p-10 text-center"><p className="bw-label text-sm text-[#888]">Could not load settings. Check connection.</p></div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {groups.map((group) => (
            <div key={group.name} className="bw-card rounded-sm p-6">
              <div className="flex items-center gap-2.5 mb-5 pb-3 border-b border-[#1a1a1a]">
                <div className="w-1 h-4 bg-white/30 rounded-full" />
                <h3 className="text-base font-medium text-white tracking-wide">{group.name}</h3>
              </div>
              <div className="space-y-5">
                {group.settings.map((item) => (
                  <div key={item.key} className="space-y-2">
                    <Label className="bw-label text-xs">{item.key}</Label>
                    {renderInput(item)}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
