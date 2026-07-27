import { useEffect, useState } from 'react';
import axios from 'axios';

interface ParseJob {
  job_id: string;
  filename: string;
  status: string;
  result?: {
    questions_parsed: number;
    answers_matched: number;
    questions_imported: number;
    questions_skipped: number;
  };
  error?: string;
}

export default function ParseJobs() {
  const [jobs, setJobs] = useState<ParseJob[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = async () => {
    const token = localStorage.getItem('access_token');
    try {
      const { data } = await axios.get('/api/v1/uploads/parse', {
        headers: { Authorization: `Bearer ${token}` },
      });
      setJobs((data.jobs || []).map((j: any) => ({
        job_id: j.job_id, filename: j.filename, status: j.status,
        result: j.result, error: j.error,
      })));
    } catch {}
  };

  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, []);

  const colors: Record<string, string> = {
    uploading: 'text-blue-600', saving: 'text-blue-600', parsing: 'text-orange-500',
    importing: 'text-orange-500', done: 'text-green-600', error: 'text-red-600',
  };
  const icons: Record<string, string> = {
    uploading: '⬆', saving: '📄', parsing: '🔍', importing: '💾',
    done: '✓', error: '✗',
  };

  const totalImported = jobs.reduce((s, j) => s + (j.result?.questions_imported || 0), 0);
  const totalParsed = jobs.reduce((s, j) => s + (j.result?.questions_parsed || 0), 0);
  const active = jobs.filter(j => !['done', 'error'].includes(j.status)).length;

  return (
    <div className="max-w-3xl mx-auto">
      <h2 className="text-xl font-bold mb-4">Parse Job History</h2>

      {/* Summary */}
      {jobs.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm p-4 mb-6 grid grid-cols-3 gap-4 text-center">
          <div><div className="text-xl font-bold text-blue-600">{jobs.length}</div><div className="text-xs text-gray-500">Total Jobs</div></div>
          <div><div className="text-xl font-bold text-green-600">{totalImported}</div><div className="text-xs text-gray-500">Questions Imported</div></div>
          <div><div className={`text-xl font-bold ${active > 0 ? 'text-orange-500' : 'text-gray-400'}`}>{active || '—'}</div><div className="text-xs text-gray-500">Active</div></div>
        </div>
      )}

      {/* Job table */}
      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left p-3">File</th>
              <th className="text-center p-3">Status</th>
              <th className="text-right p-3">Parsed</th>
              <th className="text-right p-3">Imported</th>
              <th className="text-right p-3">Skipped</th>
            </tr>
          </thead>
          <tbody>
            {jobs.length === 0 && (
              <tr><td colSpan={5} className="p-8 text-center text-gray-400">No parse jobs yet. Upload a PDF from the Upload page.</td></tr>
            )}
            {jobs.map(j => (
              <tr key={j.job_id} className={`border-t hover:bg-gray-50 ${j.status === 'error' ? 'bg-red-50' : ''}`}>
                <td className="p-3">
                  <button onClick={() => setExpanded(expanded === j.job_id ? null : j.job_id)} className="text-blue-600 hover:underline text-left text-xs">
                    {j.filename}
                  </button>
                  {expanded === j.job_id && j.error && (
                    <div className="mt-1 text-xs text-red-500 bg-red-50 p-2 rounded">{j.error}</div>
                  )}
                </td>
                <td className={`p-3 text-center text-xs font-medium ${colors[j.status] || ''}`}>
                  {icons[j.status] || ''} {j.status === 'done' ? 'Done' : j.status === 'error' ? 'Error' : `${j.status}...`}
                </td>
                <td className="p-3 text-right">{j.result?.questions_parsed ?? '—'}</td>
                <td className="p-3 text-right font-medium text-green-700">{j.result?.questions_imported ?? '—'}</td>
                <td className="p-3 text-right text-gray-400">{j.result?.questions_skipped ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
