import katex from 'katex';
import 'katex/dist/katex.min.css';

interface MathRendererProps {
  content: string;
  className?: string;
  inline?: boolean;
}

export function MathRenderer({ content, className = '', inline = false }: MathRendererProps) {
  if (!content) return null;

  const parts = content.split(/(\$\$[\s\S]*?\$\$|\$(?:\\\$|[^$\n])+?\$)/g);
  const Wrapper = inline ? 'span' : 'div';

  return (
    <Wrapper className={`whitespace-pre-wrap text-slate-800 leading-relaxed ${className}`}>
      {parts.map((part, index) => {
        if (index % 2 === 0) return <span key={index}>{part}</span>;
        const isDisplay = part.startsWith('$$');
        const latex = isDisplay ? part.slice(2, -2) : part.slice(1, -1);
        try {
          const html = katex.renderToString(latex, {
            displayMode: isDisplay,
            throwOnError: false,
            trust: false,
          });
          return <span key={index} dangerouslySetInnerHTML={{ __html: html }} />;
        } catch {
          return <span key={index}>{part}</span>;
        }
      })}
    </Wrapper>
  );
}

export default MathRenderer;
