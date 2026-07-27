import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';

const navItems: Record<string, { label: string; path: string }[]> = {
  admin: [
    { label: 'Dashboard', path: '/admin' },
    { label: 'Users', path: '/admin/users' },
    { label: 'Upload', path: '/editor/upload' },
    { label: 'Questions', path: '/editor/questions' },
    { label: 'Exams', path: '/editor/exams' },
  ],
  editor: [
    { label: 'Dashboard', path: '/editor' },
    { label: 'Upload', path: '/editor/upload' },
    { label: 'Questions', path: '/editor/questions' },
    { label: 'Exams', path: '/editor/exams' },
  ],
  student: [
    { label: 'Dashboard', path: '/student' },
    { label: 'Exams', path: '/student/exams' },
    { label: 'Results', path: '/student/results' },
    { label: 'Practice', path: '/student/practice' },
  ],
};

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const items = user ? (navItems[user.role] || []) : [];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="flex h-screen bg-gray-100">
      <aside className="w-56 bg-gray-900 text-white flex flex-col">
        <div className="p-4 border-b border-gray-700">
          <h1 className="text-lg font-bold">SAT Exam</h1>
          <p className="text-xs text-gray-400 mt-1">{user?.email}</p>
          <p className="text-xs text-gray-500 capitalize">{user?.role}</p>
        </div>
        <nav className="flex-1 p-2 space-y-1">
          {items.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `block px-3 py-2 rounded text-sm ${isActive ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-gray-800'}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-gray-700">
          <button onClick={handleLogout} className="text-sm text-gray-400 hover:text-white transition-colors">
            Sign Out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
