import { useEffect, useState } from 'react';
import { adminApi } from '../../api';
import type { User } from '../../types';

export default function AdminUsers() {
  const [users, setUsers] = useState<User[]>([]);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [role, setRole] = useState('student');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [editing, setEditing] = useState<string | null>(null);
  const [editRole, setEditRole] = useState('');

  useEffect(() => { loadUsers(); }, []);

  const loadUsers = async () => {
    try {
      const { data } = await adminApi.listUsers();
      setUsers(data);
    } catch { /* ignore */ }
  };

  const clearMessages = () => { setError(''); setSuccess(''); };

  const createUser = async () => {
    clearMessages();
    if (!email.trim()) { setError('Email is required'); return; }
    if (!password) { setError('Password is required'); return; }
    if (password.length < 6) { setError('Password must be at least 6 characters'); return; }
    if (password !== confirmPassword) { setError('Passwords do not match'); return; }
    try {
      await adminApi.createUser({ email: email.trim(), password, role });
      setEmail(''); setPassword(''); setConfirmPassword(''); setRole('student');
      setSuccess('User created successfully');
      loadUsers();
    } catch {
      setError('Failed to create user');
    }
  };

  const startEdit = (user: User) => {
    setEditing(user.id);
    setEditRole(user.role);
  };

  const saveEdit = async (userId: string) => {
    clearMessages();
    try {
      await adminApi.changeRole(userId, editRole);
      setEditing(null);
      loadUsers();
    } catch {
      setError('Failed to update user');
    }
  };

  const handleToggleActive = async (user: User) => {
    clearMessages();
    try {
      await adminApi.toggleActive(user.id);
      loadUsers();
    } catch {
      setError('Failed to toggle status');
    }
  };

  const handleDelete = async (user: User) => {
    if (!confirm(`Delete ${user.email}? This cannot be undone.`)) return;
    clearMessages();
    try {
      await adminApi.deleteUser(user.id);
      loadUsers();
    } catch {
      setError('Failed to delete user');
    }
  };

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">User Management</h2>

      <div className="bg-white rounded-lg p-4 mb-6 shadow-sm">
        <h3 className="font-semibold mb-3">Create User</h3>
        <div className="space-y-3">
          <div className="flex gap-2">
            <input
              value={email} onChange={e => setEmail(e.target.value)} placeholder="Email"
              className="border rounded px-3 py-2 flex-1"
            />
            <select value={role} onChange={e => setRole(e.target.value)} className="border rounded px-3 py-2 w-32">
              <option value="student">Student</option>
              <option value="editor">Editor</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div className="flex gap-2">
            <input
              value={password} onChange={e => setPassword(e.target.value)}
              placeholder="Password (min 6 chars)" type="password"
              className="border rounded px-3 py-2 flex-1"
            />
            <input
              value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)}
              placeholder="Confirm password" type="password"
              className="border rounded px-3 py-2 flex-1"
            />
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
          {success && <p className="text-green-600 text-sm">{success}</p>}
          <button onClick={createUser} className="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700 font-medium">
            Create
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left p-3">Email</th>
              <th className="text-left p-3">Role</th>
              <th className="text-left p-3">Status</th>
              <th className="text-left p-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} className="border-t">
                <td className="p-3">{u.email}</td>
                <td className="p-3">
                  {editing === u.id ? (
                    <select value={editRole} onChange={e => setEditRole(e.target.value)} className="border rounded px-2 py-1">
                      <option value="student">Student</option>
                      <option value="editor">Editor</option>
                      <option value="admin">Admin</option>
                    </select>
                  ) : (
                    <span className="capitalize">{u.role}</span>
                  )}
                </td>
                <td className="p-3">
                  <button
                    onClick={() => handleToggleActive(u)}
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      u.is_active ? 'bg-green-100 text-green-800 hover:bg-red-100 hover:text-red-800' : 'bg-gray-100 text-gray-600 hover:bg-green-100 hover:text-green-800'
                    }`}
                  >
                    {u.is_active ? 'Active' : 'Inactive'}
                  </button>
                </td>
                <td className="p-3">
                  {editing === u.id ? (
                    <div className="flex gap-1">
                      <button onClick={() => saveEdit(u.id)} className="text-green-600 hover:underline text-xs font-medium">Save</button>
                      <button onClick={() => setEditing(null)} className="text-gray-400 hover:underline text-xs">Cancel</button>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <button onClick={() => startEdit(u)} className="text-blue-600 hover:underline text-xs">Edit</button>
                      <button onClick={() => handleDelete(u)} className="text-red-500 hover:underline text-xs">Delete</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
