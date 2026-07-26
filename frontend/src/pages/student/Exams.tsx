import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { examApi } from '../../api';
import type { Exam } from '../../types';

export default function StudentExams() {
  const [exams, setExams] = useState<Exam[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    examApi.list().then(({ data }) => setExams(data.items || []));
  }, []);

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Available Exams</h2>
      {exams.length === 0 ? (
        <p className="text-gray-500">No exams available yet.</p>
      ) : (
        <div className="space-y-3">
          {exams.map((exam) => (
            <div key={exam.id} className="bg-white rounded-lg p-4 shadow-sm flex items-center justify-between">
              <div>
                <h3 className="font-semibold">{exam.title}</h3>
                <p className="text-sm text-gray-500">{exam.modules?.length || 4} modules • Digital SAT</p>
              </div>
              <button
                onClick={() => navigate(`/student/exams/${exam.id}/take`)}
                className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 font-medium"
              >
                Start Exam
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
