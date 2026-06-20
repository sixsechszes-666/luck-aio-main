import { createContext, useContext, useState, useEffect, type ReactNode } from "react";

type Theme = "bw" | "color";

interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
  isColor: boolean;
}

const ThemeContext = createContext<ThemeContextType>({
  theme: "bw",
  toggleTheme: () => {},
  isColor: false,
});

export const useTheme = () => useContext(ThemeContext);

export const ThemeProvider = ({ children }: { children: ReactNode }) => {
  const [theme, setTheme] = useState<Theme>(() => {
    return (localStorage.getItem("dashboard-theme") as Theme) || "bw";
  });

  useEffect(() => {
    localStorage.setItem("dashboard-theme", theme);
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "bw" ? "color" : "bw"));

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, isColor: theme === "color" }}>
      {children}
    </ThemeContext.Provider>
  );
};
