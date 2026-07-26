import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { attemptApi } from '../../api';
import type { AttemptState, ModuleSubmitResult } from '../../types';

export default function StudentExamTake() {
  const { examId } = useParams<{ examId: string }>();
  const navigate = useNavigate();
  const [state, setState] = useState<AttemptState | null>(null);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [finished, setFinished] = useState(false);

  const loadState = useCallback(async () => {
    if (!examId) return;
    try {
      const { data } = await attemptApi.start(examId);
      setState(data);
    } catch (e) {
      console.error(e);
    }
  }, [examId]);

  useEffect(() => { loadState(); }, [loadState]);

  if (!state) return <div className="p-8 text-center text-gray-500">Loading exam...</div>;

  const q = state.questions[currentIdx];
  if (!q) return null;

  const handleAnswer = async (answer: string) => {
    if (!state) return;
    await attemptApi.saveAnswer(state.id, q.aq_id, answer);
    setState((prev) => {
      if (!prev) return prev;
      const updated = prev.questions.map((qq) =>
        qq.aq_id === q.aq_id ? { ...qq, your_answer: answer } : qq,
      );
      return { ...prev, questions: updated };
    });
  };

  const handleSubmitModule = async () => {
    if (!state) return;
    setSubmitting(true);
    try {
      const { data } = await attemptApi.submitModule(state.id) as { data: ModuleSubmitResult };
      if (data.next_state === 'submitted') {
        setFinished(true);
      } else {
        // Reload state for next module
        const { data: newState } = await attemptApi.getState(state.id);
        setState(newState);
        setCurrentIdx(0);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSubmitting(false);
    }
  };

  if (finished) {
    return (
      <div className="text-center py-12">
        <h2 className="text-2xl font-bold text-green-600 mb-2">Exam Submitted!</h2>
        <p className="text-gray-500 mb-4">Your answers have been recorded.</p>
        <button onClick={() => navigate('/student/results')} className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700">
          View Results
        </button>
      </div>
    );
  }

  const totalQ = state.questions.length;
  const answered = state.questions.filter((q) => q.your_answer).length;
  const timerMin = Math.floor(state.remaining_ms / 60000);
  const timerSec = Math.floor((state.remaining_ms % 60000) / 1000);

  return (
    <div className="flex h-[calc(100vh-6rem)]">
      {/* Question area */}
      <div className="flex-1 bg-white rounded-lg shadow-sm p-6 overflow-auto">
        <div className="mb-4 flex items-center gap-4 text-sm text-gray-500">
          <span className="font-semibold text-gray-700">
            {state.section === 'rw' ? 'Reading & Writing' : 'Math'} — Module {state.module_no}
          </span>
          <span>Question {currentIdx + 1} of {totalQ}</span>
          <span className="ml-auto font-mono text-lg font-bold text-blue-600">
            {timerMin}:{String(timerSec).padStart(2, '0')}
          </span>
        </div>

        <div className="prose max-w-none mb-6 whitespace-pre-wrap">{q.stem}</div>

        <div className="space-y-2">
          {q.options?.map((opt) => (
            <button
              key={opt.label}
              onClick={() => handleAnswer(opt.label)}
              className={`w-full text-left p-3 rounded-lg border transition-colors ${
                q.your_answer === opt.label
                  ? 'bg-blue-50 border-blue-500 ring-1 ring-blue-500'
                  : 'bg-gray-50 border-gray-200 hover:bg-gray-100'
              }`}
            >
              <span className="font-bold mr-2">{opt.label}.</span>
              {opt.text}
            </button>
          ))}
          {!q.options && (
            <div>
              <input
                type="text"
                value={q.your_answer || ''}
                onChange={(e) => handleAnswer(e.target.value)}
                placeholder="Enter your answer"
                className="border rounded-lg px-4 py-2 w-48"
              />
            </div>
          )}
        </div>
      </div>

      {/* Question navigator */}
      <div className="w-48 ml-4 bg-white rounded-lg shadow-sm p-3 flex flex-col">
        <div className="text-xs text-gray-500 mb-2">{answered}/{totalQ} answered</div>
        <div className="grid grid-cols-5 gap-1 mb-4">
          {state.questions.map((qq, i) => (
            <button
              key={qq.aq_id}
              onClick={() => setCurrentIdx(i)}
              className={`w-8 h-8 text-xs rounded font-medium ${
                i === currentIdx ? 'ring-2 ring-blue-500' : ''
              } ${
                qq.your_answer ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
              }`}
            >
              {i + 1}
            </button>
          ))}
        </div>
        <div className="flex gap-1 mb-2">
          <button onClick={() => setCurrentIdx(Math.max(0, currentIdx - 1))} className="flex-1 bg-gray-200 py-1 rounded text-sm hover:bg-gray-300">Prev</button>
          <button onClick={() => setCurrentIdx(Math.min(totalQ - 1, currentIdx + 1))} className="flex-1 bg-gray-200 py-1 rounded text-sm hover:bg-gray-300">Next</button>
        </div>
        <button
          onClick={handleSubmitModule}
          disabled={submitting}
          className="mt-auto bg-green-600 text-white py-2 rounded-lg hover:bg-green-700 font-medium text-sm disabled:opacity-50"
        >
          {submitting ? 'Submitting...' : 'Submit Module'}
        </button>
      </div>
    </div>
  );
}
