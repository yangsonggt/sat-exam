import { useState, useCallback, DragEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

interface UploadResult {
  filename: string;
  questions_parsed: number;
  answers_matched: number;
  questions_imported: number;
  questions_skipped: number;
  error?: string;
}

export default function UploadQuestions() {
  const navigate = useNavigate();
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState<UploadResult[]>([]);
  const [dragOver, setDragOver] = useState(false);

  const processFile = async (file: File) => {
    const form = new FormData();
    form.append('file', file);
    const token = localStorage.getItem('access_token');
    const { data } = await axios.post('/api/v1/uploads/parse', form, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' },
      timeout: 600000, // 10 min for large PDFs
    });
    return { filename: file.name, ...data } as UploadResult;
  };

  const handleFiles = useCallback(async (files: FileList | File[]) => {
    setUploading(true);
    setResults([]);
    const fileArray = Array.from(files).filter(f => f.name.toLowerCase().endsWith('.pdf'));

    for (let i = 0; i < fileArray.length; i++) {
      setResults(prev => [...prev, { filename: fileArray[i].name, questions_parsed: 0, answers_matched: 0, questions_imported: 0, questions_skipped: 0, error: 'Processing...' }]);
    }

    const newResults: UploadResult[] = [];
    for (const file of fileArray) {
      try {
        const result = await processFile(file);
        newResults.push(result);
      } catch (err: any) {
        newResults.push({
          filename: file.name,
          questions_parsed: 0, answers_matched: 0, questions_imported: 0, questions_skipped: 0,
          error: err?.response?.data?.detail?.message || err?.message || 'Upload failed',
        });
      }
      setResults([...newResults]);
    }
    setUploading(false);
  }, []);

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length) handleFiles(e.dataTransfer.files);
  };

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
          <input
            type="file"
            multiple
            accept=".pdf"
            onChange={e => { if (e.target.files?.length) handleFiles(e.target.files); }}
            className="hidden"
          />
        </label>
        <p className="text-xs text-gray-400 mt-3">Supports multiple files. Each PDF is OCR'd and imported as drafts.</p>
      </div>

      {uploading && (
        <div className="text-center py-4">
          <div className="animate-spin inline-block w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full mr-2" />
          <span className="text-sm text-gray-500">Processing {results.length} file(s)...</span>
        </div>
      )}

      {results.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left p-3">File</th>
                <th className="text-right p-3">Parsed</th>
                <th className="text-right p-3">Matched</th>
                <th className="text-right p-3">Imported</th>
                <th className="text-right p-3">Skipped</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => (
                <tr key={i} className={`border-t ${r.error ? 'bg-red-50' : ''}`}>
                  <td className="p-3">
                    <span className={r.error ? 'text-red-600' : ''}>{r.filename}</span>
                    {r.error && !r.error.startsWith('Processing') && (
                      <span className="block text-xs text-red-500 mt-0.5">{r.error}</span>
                    )}
                  </td>
                  <td className="p-3 text-right">{r.questions_parsed}</td>
                  <td className="p-3 text-right">{r.answers_matched}</td>
                  <td className="p-3 text-right font-medium text-green-700">{r.questions_imported}</td>
                  <td className="p-3 text-right text-gray-400">{r.questions_skipped}</td>
                </tr>
              ))}
              {!uploading && (
                <tr className="border-t bg-gray-50 font-medium">
                  <td className="p-3">Total</td>
                  <td className="p-3 text-right">{results.reduce((s, r) => s + r.questions_parsed, 0)}</td>
                  <td className="p-3 text-right">{results.reduce((s, r) => s + r.answers_matched, 0)}</td>
                  <td className="p-3 text-right text-green-700">{results.reduce((s, r) => s + r.questions_imported, 0)}</td>
                  <td className="p-3 text-right">{results.reduce((s, r) => s + r.questions_skipped, 0)}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {!uploading && results.length > 0 && (
        <div className="flex justify-end mt-4">
          <button onClick={() => navigate('/editor/questions')} className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 font-medium">
            Go to Questions
          </button>
        </div>
      )}
    </div>
  );
}
