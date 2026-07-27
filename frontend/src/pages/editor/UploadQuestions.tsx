import { useState, useCallback, useEffect, type DragEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '../../ToastContext';

interface UploadResult {
  job_id?: string;
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

export default function UploadQuestions() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState<UploadResult[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const notifiedJobs = useState<Set<string>>(new Set())[0];

  const pollJob = useCallback(async (jobId: string, idx: number) => {
    const token = localStorage.getItem('access_token');
    try {
      const { data } = await axios.get(`/api/v1/uploads/parse/${jobId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setResults(prev => {
        const next = [...prev];
        const oldStatus = next[idx]?.status;
        next[idx] = { job_id: jobId, filename: data.filename, status: data.status, result: data.result, error: data.error };
        // Fire toast when job transitions to done
        if (data.status === 'done' && oldStatus !== 'done' && data.result && !notifiedJobs.has(jobId)) {
          notifiedJobs.add(jobId);
          addToast(`✓ ${data.filename}: ${data.result.questions_imported} questions imported`, 'success');
        }
        if (data.status === 'error' && oldStatus !== 'error' && !notifiedJobs.has(jobId)) {
          notifiedJobs.add(jobId);
          addToast(`✗ ${data.filename}: ${data.error || 'Parse failed'}`, 'error');
        }
        return next;
      });
      if (data.status === 'done' || data.status === 'error') return;
      setTimeout(() => pollJob(jobId, idx), 2000);
    } catch {
      setResults(prev => {
        const next = [...prev];
        next[idx] = { ...next[idx], status: 'error', error: 'Poll failed' };
        return next;
      });
    }
  }, [addToast]);

  // Load existing jobs on mount
  const loadJobs = useCallback(async () => {
    const token = localStorage.getItem('access_token');
    try {
      const { data } = await axios.get('/api/v1/uploads/parse', {
        headers: { Authorization: `Bearer ${token}` },
      });
      const jobs: UploadResult[] = (data.jobs || []).map((j: any) => ({
        job_id: j.job_id,
        filename: j.filename || 'Unknown',
        status: j.status,
        result: j.result,
        error: j.error,
      }));
      setResults(jobs);
      jobs.forEach((j, i) => {
        if (!['done', 'error'].includes(j.status) && j.job_id) {
          pollJob(j.job_id, i);
        }
      });
    } catch {}
  }, [pollJob]);

  useEffect(() => { loadJobs(); }, [loadJobs]);

  const processFile = async (file: File, idx: number) => {
    const form = new FormData();
    form.append('file', file);
    const token = localStorage.getItem('access_token');
    try {
      const { data } = await axios.post('/api/v1/uploads/parse', form, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' },
      });
      setResults(prev => {
        const next = [...prev];
        next[idx] = { job_id: data.job_id, filename: file.name, status: data.status };
        return next;
      });
      pollJob(data.job_id, idx);
    } catch (err: any) {
      setResults(prev => {
        const next = [...prev];
        next[idx] = { filename: file.name, status: 'error', error: err?.response?.data?.detail?.message || err?.message || 'Upload failed' };
        return next;
      });
    }
  };

  const handleFiles = useCallback(async (files: FileList | File[]) => {
    setUploading(true);
    setResults([]);
    const fileArray = Array.from(files).filter(f => f.name.toLowerCase().endsWith('.pdf'));
    const initial: UploadResult[] = fileArray.map(f => ({ filename: f.name, status: 'uploading' }));
    setResults(initial);
    fileArray.forEach((file, i) => processFile(file, i));
    setUploading(false);
  }, [pollJob]);

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length) handleFiles(e.dataTransfer.files);
  };

  const allDone = results.length > 0 && results.every(r => r.status === 'done' || r.status === 'error');
  const totalParsed = results.reduce((s, r) => s + (r.result?.questions_parsed || 0), 0);
  const totalImported = results.reduce((s, r) => s + (r.result?.questions_imported || 0), 0);
  const totalSkipped = results.reduce((s, r) => s + (r.result?.questions_skipped || 0), 0);
  const inProgress = results.filter(r => !['done', 'error'].includes(r.status)).length;

  return (
    <div className="max-w-2xl mx-auto">
      <h2 className="text-xl font-bold mb-4">Upload Questions from PDF</h2>

      <div
        onDrop={onDrop}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        className={`border-2 border-dashed rounded-xl p-12 text-center transition-colors mb-6 ${
          dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50'
        }`}
      >
        <p className="text-gray-500 mb-2">Drop PDF files here</p>
        <p className="text-xs text-gray-400 mb-4">or</p>
        <label className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 cursor-pointer font-medium text-sm">
          Browse Files
          <input type="file" multiple accept=".pdf"
            onChange={e => { if (e.target.files?.length) handleFiles(e.target.files); }}
            className="hidden" />
        </label>
        <p className="text-xs text-gray-400 mt-3">Supports multiple files. Each PDF is OCR'd and imported as drafts.</p>
      </div>

      {/* ── Summary card ── */}
      {results.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm p-4 mb-4 grid grid-cols-4 gap-4 text-center">
          <div>
            <div className="text-2xl font-bold text-blue-600">{results.length}</div>
            <div className="text-xs text-gray-500">Files</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-green-600">{totalParsed}</div>
            <div className="text-xs text-gray-500">Questions Parsed</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-green-700">{totalImported}</div>
            <div className="text-xs text-gray-500">Imported</div>
          </div>
          <div>
            <div className={`text-2xl font-bold ${inProgress > 0 ? 'text-orange-500 animate-pulse' : 'text-gray-400'}`}>
              {inProgress || totalSkipped || '—'}
            </div>
            <div className="text-xs text-gray-500">{inProgress > 0 ? 'In Progress' : 'Skipped'}</div>
          </div>
        </div>
      )}

      {/* ── Job table ── */}
      {results.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left p-3">File</th>
                <th className="text-left p-3" colSpan={3}>Status / Progress</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => {
                const colors: Record<string, string> = {
                  uploading: 'bg-blue-500', saving: 'bg-blue-500',
                  parsing: 'bg-orange-500', importing: 'bg-orange-400',
                  done: 'bg-green-500', error: 'bg-red-500',
                };
                const working = !['done', 'error'].includes(r.status);
                return (
                  <tr key={i} className={`border-t ${r.status === 'error' ? 'bg-red-50' : ''}`}>
                    <td className="p-3">{r.filename}</td>
                    <td className="p-3" colSpan={3}>
                      {working && (
                        <div className="w-full bg-gray-200 rounded-full h-3 mb-1 overflow-hidden">
                          <div className={`h-3 rounded-full ${colors[r.status] || 'bg-gray-400'} transition-all duration-1000 animate-pulse`}
                            style={{ width: r.status === 'importing' ? '90%' : r.status === 'parsing' ? '60%' : r.status === 'saving' ? '20%' : r.status === 'uploading' ? '10%' : '100%' }} />
                        </div>
                      )}
                      <div className={`text-xs font-medium flex items-center gap-2 ${r.status === 'done' ? 'text-green-600' : r.status === 'error' ? 'text-red-600' : colors[r.status] ? colors[r.status].replace('bg-', 'text-') : 'text-gray-500'}`}>
                        {r.status === 'done' ? '✓ Done' : r.status === 'error' ? '✗ Error' : r.status === 'parsing' ? '🔍 OCR parsing...' : r.status === 'importing' ? '💾 Importing...' : r.status === 'saving' ? '📄 Saving...' : r.status === 'uploading' ? '⬆ Uploading...' : r.status}
                        {r.result && r.status === 'done' && (
                          <span className="font-normal text-gray-500 ml-2">({r.result.questions_parsed} parsed, {r.result.questions_imported} imported)</span>
                        )}
                      </div>
                      {r.error && <span className="block text-xs text-red-500 mt-0.5">{r.error}</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {allDone && (
        <div className="flex justify-end mt-4">
          <button onClick={() => navigate('/editor/questions')} className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 font-medium">
            Go to Questions
          </button>
        </div>
      )}
    </div>
  );
}
