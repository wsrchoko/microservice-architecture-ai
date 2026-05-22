'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';
import Sidebar from '@/components/Sidebar';
import { rolesAPI } from '@/lib/api';

export default function RolesPage() {
  const router = useRouter();
  const { isAuthenticated, checkAuth } = useAuthStore();
  const [roles, setRoles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { checkAuth().then(() => setLoading(false)); }, []);
  useEffect(() => { if (!loading && !isAuthenticated) router.push('/login'); }, [loading, isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) {
      rolesAPI.list().then(res => setRoles(Array.isArray(res.data) ? res.data : [])).catch(() => setRoles([]));
    }
  }, [isAuthenticated]);

  if (loading || !isAuthenticated) return null;

  return (
    <div className="flex">
      <Sidebar />
      <main className="flex-1 p-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Roles & Permissions</h1>
        <div className="grid gap-6">
          {roles.map((role: any) => (
            <div key={role.id} className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">{role.name}</h2>
                  <p className="text-sm text-gray-500">{role.description || 'No description'}</p>
                </div>
                <span className={`px-3 py-1 text-xs rounded-full ${role.is_system ? 'bg-purple-50 text-purple-600' : 'bg-gray-50 text-gray-600'}`}>
                  {role.is_system ? 'System' : 'Custom'}
                </span>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">Permissions ({role.permissions?.length || 0})</p>
                <div className="flex flex-wrap gap-2">
                  {(role.permissions || []).map((p: string) => (
                    <span key={p} className="px-2.5 py-1 bg-primary-50 text-primary-700 rounded-md text-xs font-medium">{p}</span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}