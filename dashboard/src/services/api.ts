/**
 * API service for communicating with the Flask backend.
 * 
 * Configure API_BASE_URL to point to your Flask server.
 * In development, you can set it via the UI or localStorage.
 */

// Base URL — reads from localStorage or defaults to current origin
export const getApiBaseUrl = (): string => {
  return localStorage.getItem("api_base_url") || "";
};

export const setApiBaseUrl = (url: string) => {
  localStorage.setItem("api_base_url", url);
};

const apiFetch = async (path: string, options?: RequestInit) => {
  const base = getApiBaseUrl();
  const url = `${base}${path}`;
  const res = await fetch(url, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) throw new Error(`API Error ${res.status}: ${res.statusText}`);
  return res.json();
};

// ===== Task Control =====
export interface TaskStatus {
  status: "idle" | "waiting" | "running" | "completed" | "error";
  task_type: string | null;
  task_name: string | null;
  workers: number;
  started_at: string | null;
  finished_at: string | null;
  elapsed: number | null;
  error: string | null;
  log: string[];
  errors: string[];
  progress_current: number;
  progress_total: number;
  wait_remaining: number;
  cooldown_remaining: number;
}

export const apiTaskStart = (type: string, workers: number) =>
  apiFetch("/api/task/start", {
    method: "POST",
    body: JSON.stringify({ type, workers }),
  });

export const apiTaskStop = () =>
  apiFetch("/api/task/stop", { method: "POST" });

export const apiTaskStatus = (): Promise<TaskStatus> =>
  apiFetch("/api/task/status");

export const apiTaskWaitAndStart = (type: string, workers: number, waitSeconds: number) =>
  apiFetch("/api/task/wait-and-start", {
    method: "POST",
    body: JSON.stringify({ type, workers, wait_seconds: waitSeconds }),
  });

// ===== Settings =====
export interface SettingsGroup {
  name: string;
  settings_list: Array<{
    key: string;
    value: string | number | boolean;
    type: "text" | "number" | "float" | "checkbox";
  }>;
}

export const apiGetSettings = (): Promise<SettingsGroup[]> =>
  apiFetch("/api/settings");

export const apiSaveSettings = (data: Record<string, string | number | boolean>) =>
  apiFetch("/api/settings/save", {
    method: "POST",
    body: JSON.stringify(data),
  });

// ===== Data endpoints =====
export interface DailyData {
  data: any[];
  summary: {
    total_accounts: number;
    success_count: number;
    error_count: number;
    chest_unavailable: number;
    total_profit: number;
    total_sol_profit: number;
    sol_rate: number;
    total_balance_usd: number;
    total_balance_sol: number;
    avg_drop: number;
    total_chest_amount: number;
    planned_tomorrow: number;
  };
}

export interface WithdrawData {
  data: any[];
  summary: {
    total_accounts: number;
    success_count: number;
    error_count: number;
    total_withdrawn: number;
    total_sol_withdrawn: number;
  };
}

export interface RegistrationData {
  data: any[];
  summary: {
    total_accounts: number;
    success_count: number;
    forward_success: number;
    reverse_success: number;
  };
}

export interface RenewData {
  data: any[];
  summary: {
    total_accounts: number;
    success_count: number;
    forward_success: number;
    reverse_success: number;
  };
}

export interface WarmupData {
  data: any[];
  summary: {
    total_accounts: number;
    success_count: number;
  };
}

export const apiGetDaily = (): Promise<DailyData> => apiFetch("/api/daily");
export const apiGetWithdraw = (): Promise<WithdrawData> => apiFetch("/api/withdraw");
export const apiGetRegistration = (): Promise<RegistrationData> => apiFetch("/api/registration");
export const apiGetRenew = (): Promise<RenewData> => apiFetch("/api/renew");
export const apiGetWarmup = (): Promise<WarmupData> => apiFetch("/api/warmup");
export const apiGetWarmupVolumeBonuses = (): Promise<DailyData> => apiFetch("/api/warmup_volume_bonuses");
export const apiGetDailyTimeline = (): Promise<TimelineEntry[]> => apiFetch("/api/daily/timeline");

export interface BonusTrackerEntry {
  ud_dir: string;
  weekly_claimed_at: string | null;
  monthly_claimed_at: string | null;
  weekly_countdown: string;
  monthly_countdown: string;
  next_weekly_at: string | null;
  next_monthly_at: string | null;
}

export interface BonusTrackerData {
  data: BonusTrackerEntry[];
  summary: {
    total_accounts: number;
    weekly_available: number;
    monthly_available: number;
    no_data: number;
  };
}

export const apiGetBonusTracker = (): Promise<BonusTrackerData> => apiFetch("/api/bonus_tracker");


export interface TimelineEntry {
  date: string;
  file: string;
  profit_usd: number;
  profit_sol: number;
  balance_usd: number;
  balance_sol: number;
  avg_drop: number;
  total_chest: number;
}

// ===== Restart =====
export const apiRestart = () =>
  apiFetch("/api/restart", { method: "POST" });
