import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import ImageExtension from '@tiptap/extension-image';
import Underline from '@tiptap/extension-underline';
import Placeholder from '@tiptap/extension-placeholder';
import { questionApi } from '../../api';
import axios from 'axios';
import FormulaEditor from '../../components/FormulaEditor';
import KatexRenderer from '../../components/KatexRenderer';

function EditorToolbar({ editor, onImage, onFormula }: { editor: any; onImage: () => void; onFormula: () => void }) {
  if (!editor) return null;
  const btn = (action: () => void, active: boolean, label: string, className = '') => (
    <button onClick={action} className={`px-2 py-1 text-xs rounded ${active ? 'bg-blue-200 font-bold' : 'bg-gray-100 hover:bg-gray-200'} ${className}`}>{label}</button>
  );
  return (
    <div className="flex gap-1 flex-wrap border-b pb-1 mb-1">
      {btn(() => editor.chain().focus().toggleBold().run(), editor.isActive('bold'), 'B')}
      {btn(() => editor.chain().focus().toggleItalic().run(), editor.isActive('italic'), 'I')}
      {btn(() => editor.chain().focus().toggleUnderline().run(), editor.isActive('underline'), 'U')}
      <span className="w-px bg-gray-300 mx-1" />
      {btn(() => editor.chain().focus().toggleHeading({ level: 2 }).run(), editor.isActive('heading', { level: 2 }), 'H2')}
      {btn(() => editor.chain().focus().toggleHeading({ level: 3 }).run(), editor.isActive('heading', { level: 3 }), 'H3')}
      <span className="w-px bg-gray-300 mx-1" />
      <button onClick={onFormula} className="px-2 py-1 text-xs rounded bg-purple-100 hover:bg-purple-200 font-mono font-bold">fx</button>
      <span className="w-px bg-gray-300 mx-1" />
      <button onClick={onImage} className="px-2 py-1 text-xs rounded bg-green-100 hover:bg-green-200">🖼</button>
      <span className="w-px bg-gray-300 mx-1" />
      {btn(() => editor.chain().focus().toggleBulletList().run(), editor.isActive('bulletList'), '•')}
      {btn(() => editor.chain().focus().toggleOrderedList().run(), editor.isActive('orderedList'), '1.')}
      {btn(() => editor.chain().focus().toggleBlockquote().run(), editor.isActive('blockquote'), '"')}
      {btn(() => editor.chain().focus().toggleCodeBlock().run(), editor.isActive('codeBlock'), '</>')}
    </div>
  );
}

function RichEditor({ content, onChange, placeholder, height = 'h-48' }: { content: string; onChange: (h: string) => void; placeholder: string; height?: string }) {
  const [formulaOpen, setFormulaOpen] = useState(false);
  const editor = useEditor({
    extensions: [
      StarterKit,
      ImageExtension,
      Underline,
      Placeholder.configure({ placeholder }),
    ],
    content,
    onUpdate: ({ editor }) => onChange(editor.getHTML()),
  });

  useEffect(() => {
    if (!editor) return;
    const currentHTML = editor.getHTML();
    if (content && content !== currentHTML) {
      editor.commands.setContent(content);
    }
  }, [editor, content]);

  const handleImage = useCallback(async () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file || !editor) return;
      const form = new FormData();
      form.append('file', file);
      const token = localStorage.getItem('access_token');
      try {
        const { data } = await axios.post('/api/v1/uploads/images', form, {
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' },
        });
        editor.chain().focus().setImage({ src: data.url }).run();
      } catch {}
    };
    input.click();
  }, [editor]);

  const handleFormulaInsert = (formula: string, displayMode: boolean) => {
    if (!editor) return;
    if (displayMode) {
      editor.chain().focus().insertContent(`\n\n\\[ ${formula} \\]\n\n`).run();
    } else {
      editor.chain().focus().insertContent(` \\( ${formula} \\) `).run();
    }
  };

  return (
    <>
      <div className="border rounded-lg overflow-hidden bg-white">
        <div className="px-2 pt-1"><EditorToolbar editor={editor} onImage={handleImage} onFormula={() => setFormulaOpen(true)} /></div>
        <EditorContent editor={editor} className={`prose prose-sm max-w-none p-3 ${height} overflow-auto focus:outline-none`} />
      </div>
      <FormulaEditor open={formulaOpen} onClose={() => setFormulaOpen(false)} onInsert={handleFormulaInsert} />
    </>
  );
}

export default function QuestionEditor() {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  const isNew = !id || id === 'new';

  const [section, setSection] = useState('reading_writing');
  const [type, setType] = useState('multiple_choice');
  const [stem, setStem] = useState('');
  const [passage, setPassage] = useState('');
  const [explanation, setExplanation] = useState('');
  const [options, setOptions] = useState([
    { label: 'A', text: '' }, { label: 'B', text: '' }, { label: 'C', text: '' }, { label: 'D', text: '' },
  ]);
  const [answer, setAnswer] = useState('');
  const [skill, setSkill] = useState('');
  const [difficulty, setDifficulty] = useState('medium');
  const [saving, setSaving] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [previewCollapsed, setPreviewCollapsed] = useState(false);
  const [status, setStatusState] = useState('draft');

  useEffect(() => {
    if (isNew) return;
    questionApi.get(id!).then(({ data }) => {
      const v = data.current_version || {};
      setSection(data.section || 'reading_writing');
      setType(data.type || 'multiple_choice');
      setStem(v.stem || '');
      setPassage(v.passage || '');
      setExplanation(v.explanation || '');
      setAnswer(v.correct_answer || '');
      setSkill(data.skill || '');
      setDifficulty(data.difficulty || 'medium');
      setStatusState(data.status || 'draft');
      if (v.options && Array.isArray(v.options)) setOptions(v.options);
    }).catch((err) => {
      console.error('Failed to load question:', err);
      alert('Failed to load question: ' + (err?.response?.data?.detail?.message || err.message));
    });
  }, [id, isNew]);

  const handleSave = async () => {
    if (!stem.trim()) return;
    setSaving(true);
    const payload = {
      section, type, stem,
      passage: passage || null,
      explanation: explanation || null,
      options: type === 'multiple_choice' ? options : null,
      correct_answer: answer,
      skill: skill || null,
      difficulty,
    };
    try {
      if (isNew) await questionApi.create(payload);
      else await questionApi.update(id!, payload);
      navigate('/editor/questions');
    } catch {
      setSaving(false);
    }
  };

  const handleSetStatus = async (newStatus: string) => {
    if (isNew) return;
    try {
      await questionApi.setStatus(id!, newStatus);
      setStatusState(newStatus);
    } catch (err: any) {
      alert('Failed to change status: ' + (err?.response?.data?.detail?.message || 'Unknown error'));
    }
  };

  const statusColors: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-700',
    saved: 'bg-blue-100 text-blue-700',
    reviewed: 'bg-yellow-100 text-yellow-700',
    published: 'bg-green-100 text-green-800',
    archived: 'bg-red-100 text-red-600',
  };

  const previewWidth = previewCollapsed ? 'w-0' : 'w-96';

  return (
    <div className="flex h-[calc(100vh-8rem)]">
      {/* Editor column */}
      <div className={`flex-1 overflow-auto ${showPreview ? 'pr-4' : ''}`}>
        <div className="max-w-4xl space-y-4">
          {/* Top bar */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold">{isNew ? 'Create Question' : 'Edit Question'}</h2>
              {!isNew && (
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColors[status] || statusColors.draft}`}>
                  {status}
                </span>
              )}
            </div>
            <div className="flex gap-2">
              <button onClick={() => setShowPreview(!showPreview)}
                className={`px-3 py-1 rounded text-xs font-medium ${showPreview ? 'bg-purple-600 text-white' : 'bg-gray-200 hover:bg-gray-300'}`}>
                {showPreview ? 'Hide Preview' : 'Preview'}
              </button>
              {showPreview && (
                <button onClick={() => setPreviewCollapsed(!previewCollapsed)}
                  className="px-2 py-1 rounded text-xs bg-gray-200 hover:bg-gray-300">
                  {previewCollapsed ? '▸' : '▸|'}
                </button>
              )}
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6 space-y-4">
            {/* Metadata row */}
            <div className="flex gap-4 flex-wrap">
              <div className="flex-1 min-w-32">
                <label className="text-xs font-medium text-gray-500">Section</label>
                <select value={section} onChange={e => setSection(e.target.value)} className="w-full border rounded px-3 py-2 mt-1">
                  <option value="reading_writing">Reading & Writing</option>
                  <option value="math">Math</option>
                </select>
              </div>
              <div className="flex-1 min-w-32">
                <label className="text-xs font-medium text-gray-500">Type</label>
                <select value={type} onChange={e => setType(e.target.value)} className="w-full border rounded px-3 py-2 mt-1">
                  <option value="multiple_choice">Multiple Choice</option>
                  <option value="grid_in">Grid-in</option>
                </select>
              </div>
              <div className="flex-1 min-w-32">
                <label className="text-xs font-medium text-gray-500">Difficulty</label>
                <select value={difficulty} onChange={e => setDifficulty(e.target.value)} className="w-full border rounded px-3 py-2 mt-1">
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </div>
              <div className="flex-1 min-w-32">
                <label className="text-xs font-medium text-gray-500">Skill</label>
                <input value={skill} onChange={e => setSkill(e.target.value)} placeholder="e.g. math.algebra" className="w-full border rounded px-3 py-2 mt-1 text-sm" />
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-gray-500">Passage (optional)</label>
              <RichEditor content={passage} onChange={setPassage} placeholder="Enter passage text..." height="h-32" />
            </div>

            <div>
              <label className="text-xs font-medium text-gray-500">Question Stem</label>
              <RichEditor content={stem} onChange={setStem} placeholder="Enter the question stem..." height="h-40" />
            </div>

            {type === 'multiple_choice' && (
              <div>
                <label className="text-xs font-medium text-gray-500">Options</label>
                <div className="space-y-2 mt-1">
                  {options.map((opt, i) => (
                    <div key={opt.label} className="flex items-start gap-2">
                      <span className="font-bold w-6 mt-2">{opt.label}.</span>
                      <input
                        value={opt.text}
                        onChange={e => { const next = [...options]; next[i] = { ...next[i], text: e.target.value }; setOptions(next); }}
                        placeholder={`Option ${opt.label}`}
                        className="flex-1 border rounded px-3 py-2 text-sm"
                      />
                      <button onClick={() => setAnswer(opt.label)}
                        className={`px-3 py-2 rounded text-xs font-medium mt-0.5 ${answer === opt.label ? 'bg-green-600 text-white' : 'bg-gray-100 hover:bg-gray-200'}`}>
                        {answer === opt.label ? '✓ Answer' : 'Answer'}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {type === 'grid_in' && (
              <div>
                <label className="text-xs font-medium text-gray-500">Correct Answer</label>
                <input value={answer} onChange={e => setAnswer(e.target.value)} placeholder="e.g. 3.14" className="w-full border rounded px-3 py-2 mt-1" />
              </div>
            )}

            <div>
              <label className="text-xs font-medium text-gray-500">Explanation (optional)</label>
              <RichEditor content={explanation} onChange={setExplanation} placeholder="Enter explanation..." height="h-28" />
            </div>

            <div className="flex justify-end gap-2 pt-4 border-t">
              <button onClick={() => navigate('/editor/questions')} className="px-4 py-2 rounded text-sm bg-gray-200 hover:bg-gray-300">Cancel</button>
              {!isNew && (
                <div className="flex gap-1 mr-auto">
                  {['draft', 'saved', 'reviewed', 'published'].filter(s => s !== status).map(s => (
                    <button key={s} onClick={() => handleSetStatus(s)}
                      className={`px-2 py-1 rounded text-xs font-medium ${statusColors[s]} hover:opacity-80`}>
                      → {s}
                    </button>
                  ))}
                </div>
              )}
              <button onClick={handleSave} disabled={saving || !stem.trim()} className="px-6 py-2 rounded text-sm bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 font-medium">
                {saving ? 'Saving...' : 'Save Question'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Preview panel */}
      {showPreview && (
        <div className={`${previewWidth} transition-all duration-200 bg-white border-l overflow-auto`}>
          {previewCollapsed ? null : (
            <div className="p-4">
              <h3 className="font-bold text-sm text-gray-500 mb-3 uppercase tracking-wide">Preview</h3>

              {passage && (
                <div className="mb-4 bg-gray-50 p-3 rounded text-sm italic">
                  <KatexRenderer html={passage} />
                </div>
              )}

              <div className="mb-4 text-base leading-relaxed">
                <KatexRenderer html={stem} />
              </div>

              {type === 'multiple_choice' && (
                <div className="space-y-2 mb-4">
                  {options.filter(o => o.text).map(opt => (
                    <div key={opt.label} className={`flex items-start gap-2 p-2 rounded text-sm ${opt.label === answer ? 'bg-green-50 border border-green-200' : 'bg-gray-50'}`}>
                      <span className="font-bold">{opt.label}.</span>
                      <span className="flex-1"><KatexRenderer html={opt.text} /></span>
                      {opt.label === answer && <span className="text-green-600 text-xs font-medium">✓</span>}
                    </div>
                  ))}
                </div>
              )}

              {type === 'grid_in' && answer && (
                <div className="text-sm mb-4">
                  <span className="font-medium">Answer: </span>
                  <span className="text-green-700 font-mono">{answer}</span>
                </div>
              )}

              {explanation && (
                <div className="bg-blue-50 p-3 rounded text-sm mt-4">
                  <span className="font-medium block mb-1">Explanation:</span>
                  <KatexRenderer html={explanation} />
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
