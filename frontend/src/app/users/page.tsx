'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';
import Sidebar from '@/components/Sidebar';
import { usersAPI } from '@/lib/api';

export default function UsersPage() {
  const router = useRouter();
  const { isAuthenticated, checkAuth } = useAuthStore();
  const [users, setUsers] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [selectedUser, setSelectedUser] = useState<any>(null);

  useEffect(() => { checkAuth().then(() => setLoading(false)); }, []);
  useEffect(() => { if (!loading && !isAuthenticated) router.push('/login'); }, [loading, isAuthenticated]);

  const loadUsers = async () => {
    try {
      const res = search ? await usersAPI.search(search) : await usersAPI.list();
      setUsers(res.data.items || res.data || []);
    } catch { setUsers([]); }
  };

  useEffect(() => { if (isAuthenticated) loadUsers(); }, [isAuthenticated, search]);

  if (loading || !isAuthenticated) return null;

  return (
    <div className="flex">
      <Sidebar />
      <main className="flex-1 p-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Users</h1>
          <div className="flex gap-3">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search users..."
              className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 outline-none"
            />
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 border-b">
                <th className="text-left px-6 py-3 text-sm font-medium text-gray-500">ID</th>
                <th className="text-left px-6 py-3 text-sm font-medium text-gray-500">Name</th>
                <th className="text-left px-6 py-3 text-sm font-medium text-gray-500">Department</th>
                <th className="text-left px-6 py-3 text-sm font-medium text-gray-500">Position</th>
                <th className="text-left px-6 py-3 text-sm font-medium text-gray-500">Status</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 ? (
                <tr><td colSpan={5} className="px-6 py-8 text-center text-gray-500">No users found</td></tr>
              ) : (
                users.map((u: any) => (
                  <tr key={u.id || u.user_id} className="border-b hover:bg-gray-50 cursor-pointer"
                      onClick={() => setSelectedUser(selectedUser?.id === u.id ? null : u)}>
                    <td className="px-6 py-4 text-sm text-gray-500 font-mono">{(u.id || u.user_id)?.slice(0, 8)}...</td>
                    <td className="px-6 py-4 text-sm font-medium text-gray-900">{u.first_name} {u.last_name}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">{u.department || '-'}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">{u.position || '-'}</td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 text-xs rounded-full ${u.is_deleted ? 'bg-red-50 text-red-600' : 'bg-green-50 text-green-600'}`}>
                        {u.is_deleted ? 'Inactive' : 'Active'}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}