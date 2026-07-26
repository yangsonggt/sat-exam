// LaTeX formula modal with live KaTeX preview
import { useState, useEffect, useRef } from 'react';

interface Props {
  open: boolean;
  onClose: () => void;
  onInsert: (formula: string, displayMode: boolean) => void;
}

export default function FormulaEditor({ open, onClose, onInsert }: Props) {
  const [formula, setFormula] = useState('');
  const [displayMode, setDisplayMode] = useState(false);
  const [preview, setPreview] = useState('');
  const previewRef = useRef<HTMLDivElement>(null);
  const [katex, setKatex] = useState<any>(null);

  useEffect(() => {
    if (open) {
      import('katex').then((k) => {
        import('katex/dist/katex.min.css');
        setKatex(k);
      });
    }
  }, [open]);

  useEffect(() => {
    if (!katex || !formula) { setPreview(''); return; }
    try {
      setPreview(katex.default.renderToString(formula, { throwOnError: false, displayMode }));
    } catch {
      setPreview(formula);
    }
  }, [formula, displayMode, katex]);

  const handleInsert = () => {
    if (!formula.trim()) return;
    onInsert(formula, displayMode);
    setFormula('');
    onClose();
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-lg w-full max-w-lg p-6 m-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold">Formula Editor</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
        </div>

        <div className="flex gap-2 mb-3">
          <button onClick={() => setDisplayMode(false)} className={`px-3 py-1 rounded text-xs font-medium ${!displayMode ? 'bg-purple-600 text-white' : 'bg-gray-100'}`}>
            Inline \\(x\\)
          </button>
          <button onClick={() => setDisplayMode(true)} className={`px-3 py-1 rounded text-xs font-medium ${displayMode ? 'bg-purple-600 text-white' : 'bg-gray-100'}`}>
            Block \\[x\\]
          </button>
        </div>

        <textarea
          value={formula}
          onChange={e => setFormula(e.target.value)}
          placeholder={"e.g. \\frac{1}{2} + \\sqrt{x}"}
          className="w-full border rounded-lg px-3 py-2 font-mono text-sm h-24 mb-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
          autoFocus
        />

        {preview && (
          <div className="bg-purple-50 rounded-lg p-3 mb-3 min-h-12">
            <div className="text-xs text-purple-500 mb-1 font-medium">Preview:</div>
            <div
              ref={previewRef}
              className="overflow-x-auto"
              dangerouslySetInnerHTML={{ __html: preview }}
            />
          </div>
        )}

        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="px-4 py-2 rounded text-sm bg-gray-200 hover:bg-gray-300">Cancel</button>
          <button onClick={handleInsert} disabled={!formula.trim()} className="px-4 py-2 rounded text-sm bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50 font-medium">
            Insert Formula
          </button>
        </div>
      </div>
    </div>
  );
}
