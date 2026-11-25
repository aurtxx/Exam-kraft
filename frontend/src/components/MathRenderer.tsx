import { createElement, ReactNode } from 'react';

interface MathRendererProps {
  content: string;
  className?: string;
}

const symbols: Record<string, string> = {
  det: 'det', times: '×', div: '÷', pm: '±', alpha: 'α', beta: 'β', theta: 'θ',
  pi: 'π', leq: '≤', geq: '≥', neq: '≠', infty: '∞',
};

function renderMath(source: string, display: 'block' | 'inline') {
  const tokens = source.match(/\\[a-zA-Z]+|\\.|[0-9]+(?:\.[0-9]+)?|[^\s]/gu) ?? [];
  let index = 0;

  function readAtom(): ReactNode {
    const token = tokens[index++];
    if (token === '{') {
      const group = readExpression();
      if (tokens[index++] !== '}') throw new Error('Missing closing brace');
      return group;
    }
    if (!token || token === '}') throw new Error('Missing operand');
    if (token === '\\frac') return createElement('mfrac', null, readAtom(), readAtom());
    if (token === '\\sqrt') return createElement('msqrt', null, readAtom());
    if (token.startsWith('\\')) {
      return createElement('mo', null, symbols[token.slice(1)] ?? token);
    }
    const tag = /^[0-9]/.test(token) ? 'mn' : /^\p{L}$/u.test(token) ? 'mi' : 'mo';
    return createElement(tag, null, token);
  }

  function readExpression(): ReactNode {
    const children = [];
    while (index < tokens.length && tokens[index] !== '}') {
      const key = index;
      let base = readAtom();
      let subscript: ReactNode;
      let superscript: ReactNode;
      while (tokens[index] === '_' || tokens[index] === '^') {
        const operator = tokens[index++];
        if (operator === '_') subscript = readAtom();
        else superscript = readAtom();
      }
      if (subscript && superscript) base = createElement('msubsup', null, base, subscript, superscript);
      else if (subscript) base = createElement('msub', null, base, subscript);
      else if (superscript) base = createElement('msup', null, base, superscript);
      children.push(createElement('mrow', { key }, base));
    }
    return createElement('mrow', null, children);
  }

  try {
    const expression = readExpression();
    if (index !== tokens.length) return source;
    return createElement('math', { display, 'aria-label': source }, expression);
  } catch {
    return source;
  }
}

export function MathRenderer({ content, className = '' }: MathRendererProps) {
  if (!content) return null;

  return (
    <div className={`whitespace-pre-wrap text-slate-800 leading-relaxed ${className}`}>
      {content.split(/(\$\$[\s\S]*?\$\$|\$[^$]+?\$)/g).map((part, index) => {
        if (index % 2 === 0) return <span key={index}>{part}</span>;
        const display = part.startsWith('$$') ? 'block' : 'inline';
        const delimiterLength = display === 'block' ? 2 : 1;
        return <span key={index}>{renderMath(part.slice(delimiterLength, -delimiterLength), display)}</span>;
      })}
    </div>
  );
}

export default MathRenderer;
