import axios from 'axios';

const api = axios.create({ baseURL: '/api/v1' });

// Request interceptor: attach token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Response interceptor: handle 401 → refresh
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    if (error.response?.status === 401 && !error.config._retry) {
      error.config._retry = true;
      try {
        const refresh = localStorage.getItem('refresh_token');
        if (!refresh) throw new Error('no refresh token');
        const { data } = await axios.post('/api/v1/auth/refresh', { refresh_token: refresh });
        localStorage.setItem('access_token', data.access_token);
        error.config.headers.Authorization = `Bearer ${data.access_token}`;
        return api(error.config);
      } catch {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

// Auth
export const authApi = {
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),
  me: () => api.get('/auth/me'),
};

// Admin
export const adminApi = {
  createUser: (data: { email: string; password: string; role: string; display_name?: string }) =>
    api.post('/admin/users', data),
  listUsers: () => api.get('/admin/users'),
  changeRole: (userId: string, role: string) =>
    api.patch(`/admin/users/${userId}/role?new_role=${role}`),
};

// Questions
export const questionApi = {
  list: (params?: Record<string, string | number>) => api.get('/questions', { params }),
  get: (id: string) => api.get(`/questions/${id}`),
  create: (data: Record<string, unknown>) => api.post('/questions', data),
  update: (id: string, data: Record<string, unknown>) => api.patch(`/questions/${id}`, data),
  publish: (id: string) => api.post(`/questions/${id}/publish`),
  vocabulary: () => api.get('/questions/vocabulary'),
  delete: (id: string) => api.delete(`/questions/${id}`),
};

// Exams
export const examApi = {
  list: () => api.get('/exams'),
  get: (id: string) => api.get(`/exams/${id}`),
  create: (data: Record<string, unknown>) => api.post('/exams', data),
  publish: (id: string) => api.post(`/exams/${id}/publish`),
  validate: (id: string) => api.get(`/exams/${id}/validate`),
};

// Attempts
export const attemptApi = {
  start: (examId: string) => api.post(`/exams/${examId}/attempts`),
  getState: (id: string) => api.get(`/attempts/${id}`),
  saveAnswer: (attemptId: string, aqId: string, answer: string) =>
    api.post(`/attempts/${attemptId}/answers`, { aq_id: aqId, answer }),
  submitModule: (attemptId: string) =>
    api.post(`/attempts/${attemptId}/modules/current/submit`),
  getAnalysis: (attemptId: string) => api.get(`/attempts/${attemptId}/analysis`),
};

// Results
export const resultApi = {
  getTrends: () => api.get('/results/me/trends'),
};

// Practice
export const practiceApi = {
  generatePlan: (attemptId: string) => api.post('/practice/plans', { attempt_id: attemptId }),
  listPlans: () => api.get('/practice/plans'),
  getPlan: (id: string) => api.get(`/practice/plans/${id}`),
  startTask: (taskId: string) => api.post(`/practice/tasks/${taskId}/start`),
  answerTask: (taskId: string, ptqId: string, answer: string) =>
    api.post(`/practice/tasks/${taskId}/answer`, { ptq_id: ptqId, answer }),
  completeTask: (taskId: string) => api.post(`/practice/tasks/${taskId}/complete`),
};

export default api;
