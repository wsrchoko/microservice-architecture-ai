'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';
import Sidebar from '@/components/Sidebar';
import { aiAPI } from '@/lib/api';

export default function AIPage() {
  const router = useRouter();
  const { isAuthenticated, checkAuth } = useAuthStore();
  const [question, setQuestion] = useState('');
  const [response, setResponse] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [loadingAuth, setLoadingAuth] = useState(true);

  useEffect(() => { checkAuth().then(() => setLoadingAuth(false)); }, []);
  useEffect(() => { if (!loadingAuth && !isAuthenticated) router.push('/login'); }, [loadingAuth, isAuthenticated]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setResponse(null);
    try {
      const res = await aiAPI.query(question);
      setResponse(res.data);
    } catch (err: any) {
      setResponse({ answer: `Error: ${err.response?.data?.detail || err.message}`, sources: [], metadata: {} });
    } finally {
      setLoading(false);
    }
  };

  if (loadingAuth || !isAuthenticated) return null;

  return (
    <div className="flex">
      <Sidebar />
      <main className="flex-1 p-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">AI Assistant</h1>
        
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Ask a question about the system</label>
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 outline-none resize-none"
                rows={3}
                placeholder="e.g., How many users are in the system?"
              />
            </div>
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="px-6 py-2.5 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 disabled:opacity-50 transition-colors"
            >
              {loading ? 'Thinking...' : 'Ask AI'}
            </button>
          </form>
        </div>

        {response && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Response</h2>
            <div className="prose max-w-none mb-4">
              <p className="text-gray-700 whitespace-pre-wrap">{response.answer}</p>
            </div>
            
            {response.sources && response.sources.length > 0 && (
              <div className="mb-4">
                <h3 className="text-sm font-medium text-gray-700 mb-2">Sources ({response.sources.length})</h3>
                <div className="flex flex-wrap gap-2">
                  {response.sources.map((s: any, i: number) => (
                    <span key={i} className="px-2 py-1 bg-gray-50 text-gray-600 rounded text-xs">
                      Score: {(s.score * 100).toFixed(1)}%
                    </span>
                  ))}
                </div>
              </div>
            )}

            {response.metadata && (
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-sm font-medium text-gray-700 mb-2">Metrics</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div><span className="text-gray-500">Latency:</span> <span className="font-medium">{response.metadata.latency_ms}ms</span></div>
                  <div><span className="text-gray-500">Tokens:</span> <span className="font-medium">{response.metadata.total_tokens}</span></div>
                  <div><span className="text-gray-500">Cost:</span> <span className="font-medium">${response.metadata.cost_usd}</span></div>
                  <div><span className="text-gray-500">Model:</span> <span className="font-medium">{response.metadata.model}</span></div>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}