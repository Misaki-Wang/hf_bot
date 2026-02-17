'use client';

import { useEffect, useState } from 'react';

type ThemeMode = 'auto' | 'light' | 'dark';

const STORAGE_KEY = 'hf-theme-mode';

function applyTheme(mode: ThemeMode) {
  const root = document.documentElement;
  if (mode === 'auto') {
    root.removeAttribute('data-theme');
    return;
  }
  root.setAttribute('data-theme', mode);
}

export default function ThemeToggle() {
  const [mode, setMode] = useState<ThemeMode>('auto');

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    const nextMode: ThemeMode = saved === 'light' || saved === 'dark' ? saved : 'auto';
    setMode(nextMode);
    applyTheme(nextMode);
  }, []);

  function onChange(nextMode: ThemeMode) {
    setMode(nextMode);
    if (nextMode === 'auto') {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY, nextMode);
    }
    applyTheme(nextMode);
  }

  return (
    <div className="theme-toggle" role="group" aria-label="Theme mode">
      <button
        type="button"
        className={`button ${mode === 'auto' ? 'active' : ''}`}
        onClick={() => onChange('auto')}
      >
        Auto
      </button>
      <button
        type="button"
        className={`button ${mode === 'light' ? 'active' : ''}`}
        onClick={() => onChange('light')}
      >
        Light
      </button>
      <button
        type="button"
        className={`button ${mode === 'dark' ? 'active' : ''}`}
        onClick={() => onChange('dark')}
      >
        Dark
      </button>
    </div>
  );
}
