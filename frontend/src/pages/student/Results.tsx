import { useEffect, useState } from 'react';
import { resultApi } from '../../api';
import type { AnalysisResult } from '../../types';

export default function StudentResults() {
  const [trends, setTrends] = useState<AnalysisResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    resultApi.getTrends().then(({ data }) => {
      setTrends(data || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-4 text-gray-500">Loading...</div>;

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Your Results</h2>
      {trends.length === 0 ? (
        <div className="bg-white rounded-lg p-8 text-center text-gray-500">
          <p className="text-lg mb-2">No exam results yet</p>
          <p>Take an exam to see your scores here.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {trends.map((r: any, i: number) => (
            <div key={i} className="bg-white rounded-lg p-4 shadow-sm">
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold">Attempt #{i + 1}</span>
                <span className="text-sm text-gray-500">{r.submitted_at ? new Date(r.submitted_at).toLocaleDateString() : ''}</span>
              </div>
              <div className="flex gap-6 text-sm">
                <div><span className="text-gray-500">Total: </span><span className="font-bold text-lg">{r.scaled_total}</span></div>
                <div><span className="text-gray-500">R&W: </span>{r.scaled_rw}</div>
                <div><span className="text-gray-500">Math: </span>{r.scaled_math}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
