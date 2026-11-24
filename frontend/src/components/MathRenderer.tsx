import React from 'react';

interface MathRendererProps {
  content: string;
  className?: string;
}

export const MathRenderer: React.FC<MathRendererProps> = ({ content, className = '' }) => {
  if (!content) return null;

  // Formatter for LaTeX expressions e.g. $\det(2A)$, $x^2$, \frac{a}{b}
  const renderFormattedMath = (text: string) => {
    // Split by $...$ or $$...$$
    const parts = text.split(/(\$\$[\s\S]*?\$\$|\$[^$]*?\$)/g);

    return parts.map((part, index) => {
      if (part.startsWith('$$') && part.endsWith('$$')) {
        const mathExpr = part.slice(2, -2).trim();
        return (
          <span
            key={index}
            className="block my-2 text-center font-mono text-base font-semibold text-slate-800 bg-slate-50 border border-slate-200 py-1.5 px-3 rounded-lg"
          >
            {formatMathString(mathExpr)}
          </span>
        );
      } else if (part.startsWith('$') && part.endsWith('$')) {
        const mathExpr = part.slice(1, -1).trim();
        return (
          <span
            key={index}
            className="inline-block font-mono text-sm font-semibold text-slate-800 px-1 bg-slate-100 rounded"
          >
            {formatMathString(mathExpr)}
          </span>
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  const formatMathString = (raw: string): string => {
    return raw
      .replace(/\\det/g, 'det')
      .replace(/\\times/g, '×')
      .replace(/\\div/g, '÷')
      .replace(/\\pm/g, '±')
      .replace(/\\alpha/g, 'α')
      .replace(/\\beta/g, 'β')
      .replace(/\\theta/g, 'θ')
      .replace(/\\pi/g, 'π')
      .replace(/\\leq/g, '≤')
      .replace(/\\geq/g, '≥')
      .replace(/\\neq/g, '≠')
      .replace(/\\infty/g, '∞')
      .replace(/\\sqrt\{([^}]+)\}/g, '√($1)')
      .replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, '($1 / $2)');
  };

  return <div className={`text-slate-800 leading-relaxed ${className}`}>{renderFormattedMath(content)}</div>;
};

export default MathRenderer;
