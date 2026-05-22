'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';
import Sidebar from '@/components/Sidebar';
import { usersAPI, rolesAPI, auditAPI } from '@/lib/api';

export default function Dashboard() {
  const router = useRouter();
  const { isAuthenticated, checkAuth } = useAuthStore();
  const [stats, setStats] = useState({ users: 0, roles: 0, audits: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuth().then(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.push('/login');
    }
  }, [loading, isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) {
      Promise.all([
        usersAPI.list(0, 1).catch(() => ({ data: { total: 0 } })),
        rolesAPI.list().catch(() => ({ data: [] })),
        auditAPI.list({ limit: 1 }).catch(() => ({ data: { total: 0 } })),
      ]).then(([users, roles, audits]) => {
        setStats({
          users: (users.data as any)?.total || 0,
          roles: (roles.data as any)?.length || 0,
          audits: (audits.data as any)?.total || 0,
        });
      });
    }
  }, [isAuthenticated]);

  if (loading || !isAuthenticated) return null;

  return (
    <div className="flex">
      <Sidebar />
      <main className="flex-1 p-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Dashboard</h1>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Total Users</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">{stats.users}</p>
              </div>
              <div className="w-12 h-12 bg-blue-50 rounded-lg flex items-center justify-center text-2xl">👥</div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Roles</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">{stats.roles}</p>
              </div>
              <div className="w-12 h-12 bg-green-50 rounded-lg flex items-center justify-center text-2xl">🔑</div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Audit Events</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">{stats.audits}</p>
              </div>
              <div className="w-12 h-12 bg-purple-50 rounded-lg flex items-center justify-center text-2xl">📋</div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">System Overview</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 bg-gray-50 rounded-lg">
              <h3 className="font-medium text-gray-700">Microservices</h3>
              <ul className="mt-2 space-y-1 text-sm text-gray-600">
                <li>✓ Auth Service (Port 8001)</li>
                <li>✓ User Service (Port 8002)</li>
                <li>✓ Role Service (Port 8003)</li>
                <li>✓ Audit Service (Port 8004)</li>
                <li>✓ AI Agent Service (Port 8005)</li>
              </ul>
            </div>
            <div className="p-4 bg-gray-50 rounded-lg">
              <h3 className="font-medium text-gray-700">Infrastructure</h3>
              <ul className="mt-2 space-y-1 text-sm text-gray-600">
                <li>✓ PostgreSQL (Transactional Data)</li>
                <li>✓ MongoDB (Audit Logs)</li>
                <li>✓ Redis (Caching)</li>
                <li>✓ RabbitMQ (Async Events)</li>
                <li>✓ Qdrant (Vector DB)</li>
              </ul>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}