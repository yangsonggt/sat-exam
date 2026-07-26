// Renders HTML content with KaTeX math rendering for \(inline\) and \[block\] formulas
import { useEffect, useRef } from 'react';

interface Props {
  html: string | null | undefined;
  className?: string;
}

export default function KatexRenderer({ html, className }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !html) return;
    // Import KaTeX dynamically
    import('katex').then((katex) => {
      import('katex/dist/katex.min.css');
      const el = ref.current!;
      // Render all inline formulas: \(...\)
      el.innerHTML = el.innerHTML.replace(/\\\((.*?)\\\)/g, (_: string, formula: string) => {
        try {
          return katex.default.renderToString(formula, { throwOnError: false, displayMode: false });
        } catch {
          return formula;
        }
      });
      // Render all block formulas: \[...\]
      el.innerHTML = el.innerHTML.replace(/\\\[(.*?)\\\]/gs, (_: string, formula: string) => {
        try {
          return katex.default.renderToString(formula, { throwOnError: false, displayMode: true });
        } catch {
          return formula;
        }
      });
    });
  }, [html]);

  return (
    <div
      ref={ref}
      className={className}
      dangerouslySetInnerHTML={{ __html: html || '' }}
    />
  );
}
