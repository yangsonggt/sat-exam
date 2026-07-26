import { useEffect, useState } from 'react';
import { questionApi } from '../../api';
import type { Question } from '../../types';

export default function EditorQuestions() {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState('');
  const [skill, setSkill] = useState('');

  const load = async () => {
    const params: Record<string, string | number> = { limit: 50 };
    if (status) params.status = status;
    if (skill) params.skill = skill;
    const { data } = await questionApi.list(params);
    setQuestions(data.items || []);
    setTotal(data.total || 0);
  };

  useEffect(() => { load(); }, [status, skill]);

  const handlePublish = async (id: string) => {
    await questionApi.publish(id);
    load();
  };

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Question Bank ({total})</h2>
      <div className="flex gap-2 mb-4">
        <select value={status} onChange={e => setStatus(e.target.value)} className="border rounded px-3 py-1">
          <option value="">All Status</option>
          <option value="draft">Draft</option>
          <option value="published">Published</option>
        </select>
        <input value={skill} onChange={e => setSkill(e.target.value)} placeholder="Filter by skill..." className="border rounded px-3 py-1" />
        <button onClick={load} className="bg-gray-200 px-4 py-1 rounded">Refresh</button>
      </div>
      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left p-2">#</th>
              <th className="text-left p-2">Section</th>
              <th className="text-left p-2">Type</th>
              <th className="text-left p-2">Skill</th>
              <th className="text-left p-2">Difficulty</th>
              <th className="text-left p-2">Status</th>
              <th className="text-left p-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {questions.map((q, i) => (
              <tr key={q.id} className="border-t hover:bg-gray-50">
                <td className="p-2 text-gray-400">{i + 1}</td>
                <td className="p-2">{q.section === 'reading_writing' ? 'R&W' : 'Math'}</td>
                <td className="p-2">{q.type === 'multiple_choice' ? 'MCQ' : 'Grid-in'}</td>
                <td className="p-2 text-xs">{q.skill || '—'}</td>
                <td className="p-2">{q.difficulty || '—'}</td>
                <td className="p-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    q.status === 'published' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
                  }`}>{q.status}</span>
                </td>
                <td className="p-2">
                  {q.status === 'draft' && (
                    <button onClick={() => handlePublish(q.id)} className="text-blue-600 hover:underline text-xs">Publish</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
