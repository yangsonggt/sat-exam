import { useEffect, useState } from 'react';
import { practiceApi } from '../../api';
import type { Plan } from '../../types';

export default function StudentPractice() {
  const [plans, setPlans] = useState<Plan[]>([]);

  useEffect(() => {
    practiceApi.listPlans().then(({ data }) => setPlans(data || []));
  }, []);

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Practice Plans</h2>
      {plans.length === 0 ? (
        <div className="bg-white rounded-lg p-8 text-center text-gray-500">
          <p className="text-lg mb-2">No practice plans yet</p>
          <p>Complete an exam to generate a personalized practice plan.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {plans.map((plan) => (
            <div key={plan.plan_id} className="bg-white rounded-lg p-4 shadow-sm">
              <h3 className="font-semibold mb-2">{plan.title}</h3>
              <div className="flex gap-3 text-sm text-gray-500">
                <span>{plan.tasks?.length || 0} tasks</span>
                <span>{plan.tasks?.filter((t: any) => t.status === 'completed').length || 0} completed</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
