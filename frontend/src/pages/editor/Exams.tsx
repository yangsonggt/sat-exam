import { useEffect, useState } from 'react';
import { examApi } from '../../api';
import type { Exam } from '../../types';

export default function EditorExams() {
  const [exams, setExams] = useState<Exam[]>([]);

  useEffect(() => {
    examApi.list().then(({ data }) => setExams(data.items || []));
  }, []);

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Exams</h2>
      {exams.length === 0 ? (
        <p className="text-gray-500">No exams created yet. Run `scripts/create_exam.py` to create one.</p>
      ) : (
        <div className="space-y-3">
          {exams.map((exam) => (
            <div key={exam.id} className="bg-white rounded-lg p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-semibold">{exam.title}</h3>
                  <p className="text-sm text-gray-500">
                    {exam.modules?.length || 0} modules
                    {' · '}
                    <span className={`font-medium ${exam.status === 'published' ? 'text-green-600' : 'text-yellow-600'}`}>
                      {exam.status}
                    </span>
                  </p>
                </div>
                {exam.status === 'draft' && (
                  <button
                    onClick={async () => { await examApi.publish(exam.id); window.location.reload(); }}
                    className="bg-green-600 text-white px-4 py-1 rounded text-sm hover:bg-green-700"
                  >
                    Publish
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
