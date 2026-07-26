import { useState } from 'react';
import { adminApi } from '../../api';
import type { User } from '../../types';

export default function AdminUsers() {
  const [users, setUsers] = useState<User[]>([]);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('student');

  const loadUsers = async () => {
    const { data } = await adminApi.listUsers();
    setUsers(data);
  };

  const createUser = async () => {
    await adminApi.createUser({ email, password, role });
    setEmail(''); setPassword(''); setRole('student');
    loadUsers();
  };

  useState(() => { loadUsers(); });

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">User Management</h2>
      <div className="bg-white rounded-lg p-4 mb-6 shadow-sm">
        <h3 className="font-semibold mb-2">Create User</h3>
        <div className="flex gap-2">
          <input value={email} onChange={e => setEmail(e.target.value)} placeholder="Email" className="border rounded px-3 py-1 flex-1" />
          <input value={password} onChange={e => setPassword(e.target.value)} placeholder="Password" type="password" className="border rounded px-3 py-1" />
          <select value={role} onChange={e => setRole(e.target.value)} className="border rounded px-3 py-1">
            <option value="student">Student</option>
            <option value="editor">Editor</option>
            <option value="admin">Admin</option>
          </select>
          <button onClick={createUser} className="bg-blue-600 text-white px-4 py-1 rounded hover:bg-blue-700">Create</button>
        </div>
      </div>
      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50"><tr><th className="text-left p-3">Email</th><th className="text-left p-3">Role</th><th className="text-left p-3">Status</th></tr></thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} className="border-t"><td className="p-3">{u.email}</td><td className="p-3 capitalize">{u.role}</td><td className="p-3">{u.is_active ? 'Active' : 'Inactive'}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
