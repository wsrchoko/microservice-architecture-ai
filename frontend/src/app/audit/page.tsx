'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';
import Sidebar from '@/components/Sidebar';
import { auditAPI } from '@/lib/api';

export default function AuditPage() {
  const router = useRouter();
  const { isAuthenticated, checkAuth } = useAuthStore();
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { checkAuth().then(() => setLoading(false)); }, []);
  useEffect(() => { if (!loading && !isAuthenticated) router.push('/login'); }, [loading, isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) {
      auditAPI.list({ limit: 50 }).then(res => setLogs(res.data.items || [])).catch(() => setLogs([]));
    }
  }, [isAuthenticated]);

  if (loading || !isAuthenticated) return null;

  return (
    <div className="flex">
      <Sidebar />
      <main className="flex-1 p-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Audit Logs</h1>
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 border-b">
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Timestamp</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Event</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Source</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">User</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Action</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Status</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-500">No audit logs found</td></tr>
              ) : (
                logs.map((log: any) => (
                  <tr key={log.id} className="border-b hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-500">{new Date(log.timestamp).toLocaleString()}</td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">{log.event_type}</td>
                    <td className="px-4 py-3 text-sm text-gray-500">{log.source}</td>
                    <td className="px-4 py-3 text-sm text-gray-500">{log.email || log.user_id?.slice(0, 8) || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-500">{log.action}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 text-xs rounded-full ${log.success ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
                        {log.success ? 'Success' : 'Failed'}
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