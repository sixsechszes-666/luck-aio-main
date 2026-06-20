export type TaskStatus = "idle" | "running" | "completed" | "error";
export type AccountStatus = "SUCCESS" | "ERROR" | "PENDING";

export interface LogEntry {
  timestamp: string;
  level: "INFO" | "WARN" | "ERROR" | "SUCCESS";
  message: string;
}

// ===== Control Tab =====
export interface TaskCard {
  type: string;
  icon: string;
  title: string;
  description: string;
}

export const taskCards: TaskCard[] = [
  { type: "daily", icon: "🎯", title: "Daily Tasks", description: "Mines/Dice, сундуки" },
  { type: "browser_setup", icon: "🔧", title: "Browser Setup", description: "Кошельки, капча" },
  { type: "registration", icon: "📝", title: "Registration", description: "Новые аккаунты" },
  { type: "warmup_registration", icon: "🔥", title: "Подготовка аккаунта", description: "Разминка кошельков" },
  { type: "warmup_volume_bonuses", icon: "📈", title: "Warmup Volume", description: "Разминка объема" },
  { type: "withdraw", icon: "💸", title: "Withdraw", description: "Вывод средств" },
  { type: "renew", icon: "🔄", title: "Renew Timer", description: "Обновление таймера" },
  { type: "manual_withdraw", icon: "🖐️", title: "Manual Withdraw", description: "Ручной вывод" },
  { type: "hardware", icon: "🔐", title: "Hardware Login", description: "Hardware авторизация" },
];

// ===== Daily Tasks Tab =====
export interface DailyAccount {
  udDir: number;
  workerId: number;
  result: string;
  startBalance: number;
  endBalance: number;
  balanceDifference: number;
  solBalanceDifference: number;
  chestAmount: number;
  link: string;
}

export interface DailySummary {
  totalAccounts: number;
  successCount: number;
  errorCount: number;
  chestUnavailable: number;
  avgDrop: number;
  totalProfit: number;
  totalSolProfit: number;
  solRate: number;
  totalBalanceUsd: number;
  totalBalanceSol: number;
  totalChestAmount: number;
  plannedTomorrow: number;
}

// ===== Withdrawals Tab =====
export interface WithdrawAccount {
  udDir: number;
  workerId: number;
  walletAddress: string;
  result: string;
  startBalance: number;
  startSolBalance: number;
  withdrawnAmount?: number;
  keptAmount?: number;
  link: string;
}

export interface WithdrawSummary {
  totalAccounts: number;
  successCount: number;
  errorCount: number;
  totalWithdrawn: number;
  totalSolWithdrawn: number;
}

// ===== Registrations Tab =====
export interface RegistrationAccount {
  udDir: number;
  workerId: number;
  result: string;
  forwardTransactionStatus: string;
  reverseTransactionStatus: string;
  solSent: number;
  tempWalletsUsed: number;
  link: string;
}

export interface RegistrationSummary {
  totalAccounts: number;
  successCount: number;
  forwardSuccess: number;
  reverseSuccess: number;
}

// ===== Renew Timers Tab =====
export interface RenewAccount {
  udDir: number;
  workerId: number;
  result: string;
  forwardTransactionStatus: string;
  reverseTransactionStatus: string;
  link: string;
}

export interface RenewSummary {
  totalAccounts: number;
  successCount: number;
  forwardSuccess: number;
  reverseSuccess: number;
}

// ===== Warmup Tab =====
export interface WarmupAccount {
  udDir: number;
  workerId: number;
  result: string;
  forwardTransactionStatus: string;
  reverseTransactionStatus: string;
  solSent: number;
  tempWalletsUsed: number;
  link: string;
}

export interface WarmupSummary {
  totalAccounts: number;
  successCount: number;
  forwardSuccess: number;
  reverseSuccess: number;
}

// ===== Settings Tab =====
export interface SettingItem {
  key: string;
  value: string | number | boolean;
  type: "text" | "number" | "float" | "checkbox";
}

export interface SettingsGroup {
  name: string;
  settings: SettingItem[];
}
