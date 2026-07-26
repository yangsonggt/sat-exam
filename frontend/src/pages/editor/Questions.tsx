import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { questionApi } from '../../api';
import type { Question } from '../../types';
import KatexRenderer from '../../components/KatexRenderer';

export default function EditorQuestions() {
  const navigate = useNavigate();
  const [questions, setQuestions] = useState<Question[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [status, setStatus] = useState('');
  const [skill, setSkill] = useState('');
  const [search, setSearch] = useState('');
  const [vocabulary, setVocabulary] = useState<string[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [editData, setEditData] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const load = async () => {
    const params: Record<string, string | number> = { limit: 50, offset: page * 50 };
    if (status) params.status = status;
    if (skill) params.skill = skill;
    if (search) params.search = search;
    const { data } = await questionApi.list(params);
    setQuestions(data.items || []);
    setTotal(data.total || 0);
  };

  const loadVocab = async () => {
    try {
      const { data } = await questionApi.vocabulary();
      setVocabulary(data.map((v: any) => v.skill_key));
    } catch {}
  };

  useEffect(() => { load(); }, [status, skill, search, page]);
  useEffect(() => { loadVocab(); }, []);

  const handleEdit = (q: Question) => {
    setEditing(q.id);
    setEditData({ skill: q.skill || '', difficulty: q.difficulty || 'medium' });
  };

  const handleSave = async (id: string) => {
    await questionApi.update(id, editData);
    setEditing(null);
    load();
  };

  const handlePublish = async (id: string) => {
    await questionApi.publish(id);
    load();
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this question?')) return;
    await questionApi.delete(id);
    load();
  };

  const handleBulkPublish = async () => {
    for (const id of selected) await questionApi.publish(id);
    setSelected(new Set());
    load();
  };

  const handleBulkDelete = async () => {
    if (!confirm(`Delete ${selected.size} questions?`)) return;
    for (const id of selected) await questionApi.delete(id);
    setSelected(new Set());
    load();
  };

  const toggleSelect = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === questions.length) setSelected(new Set());
    else setSelected(new Set(questions.map(q => q.id)));
  };

  const expandedQ = questions.find(q => q.id === expanded);

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Question Bank ({total})</h2>

      {/* Filters */}
      <div className="flex gap-2 mb-4 flex-wrap">
        <select value={status} onChange={e => { setStatus(e.target.value); setPage(0); }} className="border rounded px-3 py-1">
          <option value="">All Status</option>
          <option value="draft">Draft</option>
          <option value="published">Published</option>
          <option value="archived">Archived</option>
        </select>
        <select value={skill} onChange={e => { setSkill(e.target.value); setPage(0); }} className="border rounded px-3 py-1 max-w-xs">
          <option value="">All Skills</option>
          {vocabulary.map(v => <option key={v} value={v}>{v.split('.').slice(-1)[0]?.replace(/_/g, ' ')}</option>)}
        </select>
        <input value={search} onChange={e => { setSearch(e.target.value); setPage(0); }} placeholder="Search stem..." className="border rounded px-3 py-1 w-48" />
        <button onClick={load} className="bg-gray-200 px-4 py-1 rounded text-sm">Refresh</button>
        <button onClick={() => navigate('/editor/questions/new')} className="bg-blue-600 text-white px-4 py-1 rounded text-sm">+ Create</button>
        {selected.size > 0 && (
          <>
            <button onClick={handleBulkPublish} className="bg-green-600 text-white px-3 py-1 rounded text-sm">Publish ({selected.size})</button>
            <button onClick={handleBulkDelete} className="bg-red-500 text-white px-3 py-1 rounded text-sm">Delete ({selected.size})</button>
          </>
        )}
      </div>

      {/* Question table */}
      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left p-2 w-8"><input type="checkbox" onChange={toggleAll} checked={selected.size === questions.length && questions.length > 0} /></th>
              <th className="text-left p-2">#</th>
              <th className="text-left p-2">Sec</th>
              <th className="text-left p-2">Type</th>
              <th className="text-left p-2">Skill</th>
              <th className="text-left p-2">Diff</th>
              <th className="text-left p-2">Stem Preview</th>
              <th className="text-left p-2">Status</th>
              <th className="text-left p-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {questions.map((q, i) => (
              <tr key={q.id} className="border-t hover:bg-gray-50">
                <td className="p-2"><input type="checkbox" checked={selected.has(q.id)} onChange={() => toggleSelect(q.id)} /></td>
                <td className="p-2 text-gray-400">{page * 50 + i + 1}</td>
                <td className="p-2 font-mono text-xs">{q.section === 'reading_writing' ? 'R&W' : 'M'}</td>
                <td className="p-2 text-xs">{q.type === 'multiple_choice' ? 'MCQ' : 'Grid'}</td>
                <td className="p-2">
                  {editing === q.id ? (
                    <select value={editData.skill || ''} onChange={e => setEditData({ ...editData, skill: e.target.value })} className="border rounded px-1 py-0.5 text-xs w-32">
                      <option value="">—</option>
                      {vocabulary.map(v => <option key={v} value={v}>{v}</option>)}
                    </select>
                  ) : (
                    <span className="text-xs truncate block max-w-32" title={q.skill || ''}>{q.skill ? q.skill.split('.').slice(-1)[0]?.replace(/_/g, ' ') : '—'}</span>
                  )}
                </td>
                <td className="p-2">
                  {editing === q.id ? (
                    <select value={editData.difficulty || ''} onChange={e => setEditData({ ...editData, difficulty: e.target.value })} className="border rounded px-1 py-0.5 text-xs">
                      <option value="easy">Easy</option>
                      <option value="medium">Medium</option>
                      <option value="hard">Hard</option>
                    </select>
                  ) : (
                    <span className={`text-xs font-medium ${q.difficulty === 'easy' ? 'text-green-600' : q.difficulty === 'hard' ? 'text-red-600' : 'text-orange-500'}`}>
                      {q.difficulty || '—'}
                    </span>
                  )}
                </td>
                <td className="p-2">
                  <button onClick={() => setExpanded(expanded === q.id ? null : q.id)} className="text-left text-xs text-gray-700 hover:text-blue-600 max-w-64 truncate block">
                    {q.current_version?.stem?.slice(0, 80) || '[no stem]'}
                  </button>
                </td>
                <td className="p-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    q.status === 'published' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
                  }`}>{q.status}</span>
                </td>
                <td className="p-2">
                  <div className="flex gap-1">
                    {editing === q.id ? (
                      <>
                        <button onClick={() => handleSave(q.id)} className="text-green-600 hover:underline text-xs">Save</button>
                        <button onClick={() => setEditing(null)} className="text-gray-400 hover:underline text-xs">Cancel</button>
                      </>
                    ) : (
                      <>
                        <button onClick={() => handleEdit(q)} className="text-blue-600 hover:underline text-xs">Edit</button>
                        {q.status !== 'published' && (
                          <button onClick={() => handlePublish(q.id)} className="text-green-600 hover:underline text-xs">Pub</button>
                        )}
                        <button onClick={() => handleDelete(q.id)} className="text-red-500 hover:underline text-xs">Del</button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between mt-4 text-sm text-gray-500">
        <span>Page {page + 1} of {Math.ceil(total / 50) || 1}</span>
        <div className="flex gap-2">
          <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} className="px-3 py-1 bg-gray-200 rounded disabled:opacity-30">Prev</button>
          <button onClick={() => setPage(p => p + 1)} disabled={(page + 1) * 50 >= total} className="px-3 py-1 bg-gray-200 rounded disabled:opacity-30">Next</button>
        </div>
      </div>

      {/* Expanded question detail */}
      {expandedQ && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setExpanded(null)}>
          <div className="bg-white rounded-xl shadow-lg max-w-2xl w-full max-h-[80vh] overflow-auto p-6 m-4" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold">Question Detail</h3>
              <button onClick={() => setExpanded(null)} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
            </div>
            <div className="space-y-4">
              <div className="flex gap-4 text-sm text-gray-500">
                <span>{expandedQ.section === 'reading_writing' ? 'Reading & Writing' : 'Math'}</span>
                <span>{expandedQ.type === 'multiple_choice' ? 'Multiple Choice' : 'Grid-in'}</span>
                <span>Skill: {expandedQ.skill || '—'}</span>
                <span>Difficulty: {expandedQ.difficulty || '—'}</span>
                <span>Status: {expandedQ.status}</span>
              </div>
              {expandedQ.current_version?.passage && (
                <div className="bg-gray-50 p-3 rounded text-sm whitespace-pre-wrap italic">
                  <KatexRenderer html={expandedQ.current_version.passage} />
                </div>
              )}
              <div className="text-base leading-relaxed">
                <KatexRenderer html={expandedQ.current_version?.stem} />
              </div>
              {expandedQ.current_version?.options && (
                <div className="space-y-1">
                  {expandedQ.current_version.options.map((opt: any) => (
                    <div key={opt.label} className={`p-2 rounded text-sm ${
                      opt.label === expandedQ.current_version?.correct_answer ? 'bg-green-50 border border-green-200' : 'bg-gray-50'
                    }`}>
                      <span className="font-bold mr-2">{opt.label}.</span>
                      <KatexRenderer html={opt.text} className="inline" />
                      {opt.label === expandedQ.current_version?.correct_answer && (
                        <span className="ml-2 text-green-600 text-xs font-medium">✓ Correct</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
              {!expandedQ.current_version?.options && (
                <div className="text-sm">
                  <span className="font-medium">Answer: </span>
                  <span className="text-green-700">{expandedQ.current_version?.correct_answer}</span>
                </div>
              )}
              {expandedQ.current_version?.explanation && (
                <div className="bg-blue-50 p-3 rounded text-sm">
                  <span className="font-medium block mb-1">Explanation:</span>
                  <KatexRenderer html={expandedQ.current_version.explanation} />
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
