import React from 'react';
import { Delete, RotateCcw } from 'lucide-react';

interface VirtualNumpadProps {
  value: string;
  onChange: (val: string) => void;
  disabled?: boolean;
}

export const VirtualNumpad: React.FC<VirtualNumpadProps> = ({
  value,
  onChange,
  disabled = false,
}) => {
  const handleDigit = (digit: string) => {
    if (disabled) return;
    // Disallow multiple decimal points
    if (digit === '.' && value.includes('.')) return;
    // Handle minus sign: only at start
    if (digit === '-') {
      if (value.startsWith('-')) {
        onChange(value.slice(1));
      } else {
        onChange('-' + value);
      }
      return;
    }
    onChange(value + digit);
  };

  const handleBackspace = () => {
    if (disabled || !value) return;
    onChange(value.slice(0, -1));
  };

  const handleClear = () => {
    if (disabled) return;
    onChange('');
  };

  const keys = [
    ['1', '2', '3'],
    ['4', '5', '6'],
    ['7', '8', '9'],
    ['.', '0', '-'],
  ];

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 w-72 shadow-sm select-none">
      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 flex items-center justify-between">
        <span>Virtual Keypad</span>
        <span className="text-[11px] text-slate-400 font-normal">NTA Numerical Input</span>
      </div>

      {/* Numerical display box */}
      <div className="bg-white border-2 border-primary-500 rounded-lg px-3 py-2 mb-3 text-right text-xl font-mono font-bold text-slate-800 tracking-wider min-h-[46px] flex items-center justify-end overflow-x-auto shadow-inner">
        {value ? value : <span className="text-slate-300 font-normal text-sm">Enter value...</span>}
      </div>

      {/* 3x4 Keys Grid */}
      <div className="grid grid-cols-3 gap-2 mb-2">
        {keys.map((row, rIdx) =>
          row.map((k) => (
            <button
              key={`${rIdx}-${k}`}
              type="button"
              disabled={disabled}
              onClick={() => handleDigit(k)}
              className="h-11 rounded-lg bg-white border border-slate-300 hover:bg-primary-50 hover:border-primary-400 active:bg-primary-100 font-semibold text-slate-700 text-lg transition-colors flex items-center justify-center shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {k}
            </button>
          ))
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
