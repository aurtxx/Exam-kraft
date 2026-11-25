import React, { useRef, useEffect } from 'react';
import { Delete, RotateCcw } from 'lucide-react';

interface VirtualNumpadProps {
  value: string;
  onChange: (val: string) => void;
  disabled?: boolean;
  singleDigit?: boolean;
}

export const VirtualNumpad: React.FC<VirtualNumpadProps> = ({
  value,
  onChange,
  disabled = false,
  singleDigit = false,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!disabled) {
      inputRef.current?.focus({ preventScroll: true });
    }
  }, [disabled, singleDigit]);

  const handleDigit = (digit: string) => {
    if (disabled) return;
    if (singleDigit) {
      if (!/^[0-9]$/.test(digit) || value.length >= 1) return;
      onChange(digit);
      inputRef.current?.focus();
      return;
    }
    // Disallow multiple decimal points
    if (digit === '.' && value.includes('.')) return;
    // Handle minus sign: only at start
    if (digit === '-') {
      if (value.startsWith('-')) {
        onChange(value.slice(1));
      } else if (value.length < 100) {
        onChange('-' + value);
      }
      inputRef.current?.focus();
      return;
    }
    if (value.length >= 100) return;
    onChange(value + digit);
    inputRef.current?.focus();
  };

  const handleBackspace = () => {
    if (disabled || !value) return;
    onChange(value.slice(0, -1));
    inputRef.current?.focus();
  };

  const handleClear = () => {
    if (disabled) return;
    onChange('');
    inputRef.current?.focus();
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (disabled) return;
    const raw = e.target.value.trim();
    if (singleDigit) {
      if (/^[0-9]?$/.test(raw)) {
        onChange(raw);
      }
      return;
    }
    if (/^-?\d*\.?\d*$/.test(raw) && raw.length <= 100) {
      onChange(raw);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    const allowedNavKeys = [
      'Backspace',
      'Delete',
      'Tab',
      'ArrowLeft',
      'ArrowRight',
      'Home',
      'End',
      'Enter',
      'Escape',
    ];
    if (allowedNavKeys.includes(e.key) || e.ctrlKey || e.metaKey || e.altKey) {
      return;
    }
    if (e.key.length === 1) {
      if (singleDigit && !/^[0-9]$/.test(e.key)) {
        e.preventDefault();
      } else if (!singleDigit && !/^[0-9.-]$/.test(e.key)) {
        e.preventDefault();
      }
    }
  };

  const keys = [
    ['1', '2', '3'],
    ['4', '5', '6'],
    ['7', '8', '9'],
    ['.', '0', '-'],
  ];

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 w-full max-w-sm shadow-sm select-none">
      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 flex items-center justify-between gap-2">
        <span>Virtual Keypad</span>
        <span className="text-[11px] text-slate-400 font-normal">NTA Numerical Input · or type directly</span>
      </div>

      {/* Controlled numerical input supporting direct keyboard entry */}
      <input
        ref={inputRef}
        type="text"
        role="textbox"
        aria-label="Numerical answer input"
        inputMode={singleDigit ? 'numeric' : 'decimal'}
        autoComplete="off"
        disabled={disabled}
        maxLength={singleDigit ? 1 : 100}
        value={value}
        onChange={handleInputChange}
        onKeyDown={handleKeyDown}
        placeholder={singleDigit ? 'Type 0–9...' : 'Enter value...'}
        className="w-full min-h-[48px] bg-white border-2 border-primary-500 rounded-lg px-3 py-2 mb-3 text-right text-xl font-mono font-bold text-slate-800 tracking-wider shadow-inner focus:outline-none focus:ring-2 focus:ring-primary-500/30 select-text placeholder:text-slate-300 placeholder:font-normal placeholder:text-sm disabled:bg-slate-100 disabled:cursor-not-allowed"
      />

      {/* 3x4 Keys Grid */}
      <div className="grid grid-cols-3 gap-2 mb-2">
        {keys.map((row, rIdx) =>
          row.map((k) => {
            const isKeyDisabled = disabled || (singleDigit && (k === '.' || k === '-'));
            return (
              <button
                key={`${rIdx}-${k}`}
                type="button"
                disabled={isKeyDisabled}
                onClick={() => handleDigit(k)}
                className="h-11 rounded-lg bg-white border border-slate-300 hover:bg-primary-50 hover:border-primary-400 active:bg-primary-100 font-semibold text-slate-700 text-lg transition-colors flex items-center justify-center shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {k}
              </button>
            );
          })
        )}
      </div>

      {/* Action buttons: Backspace and Clear */}
      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          disabled={disabled || !value}
          onClick={handleBackspace}
          className="h-10 rounded-lg bg-amber-50 border border-amber-200 hover:bg-amber-100 text-amber-700 font-medium text-xs flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title="Backspace"
        >
          <Delete className="w-4 h-4" />
          <span>Backspace</span>
        </button>
        <button
          type="button"
          disabled={disabled || !value}
          onClick={handleClear}
          className="h-10 rounded-lg bg-rose-50 border border-rose-200 hover:bg-rose-100 text-rose-700 font-medium text-xs flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title="Clear All"
        >
          <RotateCcw className="w-4 h-4" />
          <span>Clear</span>
        </button>
      </div>
    </div>
  );
};

export default VirtualNumpad;
