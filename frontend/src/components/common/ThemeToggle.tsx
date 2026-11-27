import React from 'react';
import { Moon, Sun } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';

interface ThemeToggleProps {
  className?: string;
  showLabel?: boolean;
}

/**
 * Segmented Light/Dark mode switch synchronized with ThemeContext.
 */
export const ThemeToggle: React.FC<ThemeToggleProps> = ({
  className = '',
  showLabel = false,
}) => {
  const { theme, setTheme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <div
      role="group"
      aria-label="Theme mode"
      className={`inline-flex items-center p-0.5 rounded-[10px] border border-line bg-subtle ${className}`}
    >
      <button
        type="button"
        onClick={() => setTheme('light')}
        aria-pressed={!isDark}
        title="Light theme"
        className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-[8px] text-xs font-medium transition-all ${
          !isDark
            ? 'bg-surface text-brand shadow-sm'
            : 'text-ink-secondary hover:text-ink-primary'
        }`}
      >
        <Sun className="h-3.5 w-3.5" />
        {showLabel && <span className="hidden sm:inline">Light</span>}
      </button>

      <button
        type="button"
        onClick={() => setTheme('dark')}
        aria-pressed={isDark}
        title="Dark theme"
        className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-[8px] text-xs font-medium transition-all ${
          isDark
            ? 'bg-brand text-white shadow-sm'
            : 'text-ink-secondary hover:text-ink-primary'
        }`}
      >
        <Moon className="h-3.5 w-3.5" />
        {showLabel && <span className="hidden sm:inline">Dark</span>}
      </button>
    </div>
  );
};
