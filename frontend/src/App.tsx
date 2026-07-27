import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext';
import { ToastProvider } from './ToastContext';
import Layout from './pages/Layout';
import LoginPage from './pages/LoginPage';
import AdminDashboard from './pages/admin/Dashboard';
import AdminUsers from './pages/admin/Users';
import EditorDashboard from './pages/editor/Dashboard';
import EditorQuestions from './pages/editor/Questions';
import EditorExams from './pages/editor/Exams';
import EditorQuestionNew from './pages/editor/QuestionEditor';
import EditorQuestionEdit from './pages/editor/QuestionEditor';
import EditorUpload from './pages/editor/UploadQuestions';
import StudentDashboard from './pages/student/Dashboard';
import StudentExams from './pages/student/Exams';
import StudentExamTake from './pages/student/ExamTake';
import StudentResults from './pages/student/Results';
import StudentPractice from './pages/student/Practice';

function ProtectedRoute({ children, roles }: { children: React.ReactNode; roles?: string[] }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-8 text-center">Loading...</div>;
  if (!user) return <Navigate to="/login" />;
  if (roles && !roles.includes(user.role)) return <Navigate to={`/${user.role}`} />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route path="/admin" element={<ProtectedRoute roles={['admin']}><AdminDashboard /></ProtectedRoute>} />
            <Route path="/admin/users" element={<ProtectedRoute roles={['admin']}><AdminUsers /></ProtectedRoute>} />
            <Route path="/editor" element={<ProtectedRoute roles={['admin', 'editor']}><EditorDashboard /></ProtectedRoute>} />
            <Route path="/editor/questions" element={<ProtectedRoute roles={['admin', 'editor']}><EditorQuestions /></ProtectedRoute>} />
            <Route path="/editor/questions/new" element={<ProtectedRoute roles={['admin', 'editor']}><EditorQuestionNew /></ProtectedRoute>} />
            <Route path="/editor/questions/:id" element={<ProtectedRoute roles={['admin', 'editor']}><EditorQuestionEdit /></ProtectedRoute>} />
            <Route path="/editor/upload" element={<ProtectedRoute roles={['admin', 'editor']}><EditorUpload /></ProtectedRoute>} />
            <Route path="/editor/exams" element={<ProtectedRoute roles={['admin', 'editor']}><EditorExams /></ProtectedRoute>} />
            <Route path="/student" element={<ProtectedRoute roles={['student']}><StudentDashboard /></ProtectedRoute>} />
            <Route path="/student/exams" element={<ProtectedRoute roles={['student']}><StudentExams /></ProtectedRoute>} />
            <Route path="/student/exams/:examId/take" element={<ProtectedRoute roles={['student']}><StudentExamTake /></ProtectedRoute>} />
            <Route path="/student/results" element={<ProtectedRoute roles={['student']}><StudentResults /></ProtectedRoute>} />
            <Route path="/student/practice" element={<ProtectedRoute roles={['student']}><StudentPractice /></ProtectedRoute>} />
          </Route>
          <Route path="*" element={<Navigate to="/login" />} />
        </Routes>
      </AuthProvider>
      </ToastProvider>
      </BrowserRouter>
  );
}
