import React, { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Spinner } from '../../components/common/Spinner';
import { authService } from '../../services/authService';
import { 
  BookOpen, 
  FileText, 
  Bot, 
  Layers, 
  HelpCircle, 
  CheckCircle2, 
  HardDrive, 
  Database,
  ArrowRight
} from 'lucide-react';
import { Link } from 'react-router-dom';

export const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const [systemHealth, setSystemHealth] = useState<any>(null);
  const [isLoadingHealth, setIsLoadingHealth] = useState<boolean>(true);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const data = await authService.getHealth();
        setSystemHealth(data);
      } catch (err) {
        setSystemHealth({ status: 'offline', database: { status: 'disconnected' } });
      } finally {
        setIsLoadingHealth(false);
      }
    };
    fetchHealth();
  }, []);

  return (
    <div className="space-y-8">
      {/* Welcome Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-indigo-900/60 via-purple-900/40 to-slate-900 border border-indigo-500/20 p-6 md:p-8">
        <div className="relative z-10 max-w-2xl space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 text-xs font-medium">
            <span>✨ Autonomous Agentic Learning</span>
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">
            Welcome back, {user?.full_name || user?.email.split('@')[0]}!
          </h1>
          <p className="text-slate-300 text-sm md:text-base leading-relaxed">
            Upload textbooks, research notes, or slide decks to automatically synthesize modular courses, spaced-repetition flashcards, and an active Socratic AI tutor.
          </p>
          <div className="pt-2 flex flex-wrap gap-3">
            <Link to="/documents">
              <Button variant="primary" icon={<FileText className="h-4 w-4" />}>
                Upload Documents
              </Button>
            </Link>
            <Link to="/tutor">
              <Button variant="secondary" icon={<Bot className="h-4 w-4" />}>
                Ask AI Tutor
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4 bg-slate-900/80 border-slate-800">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
              <FileText className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-slate-400 font-medium">Uploaded Documents</p>
              <p className="text-xl font-bold text-white mt-0.5">0</p>
            </div>
          </div>
        </Card>

        <Card className="p-4 bg-slate-900/80 border-slate-800">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <BookOpen className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-slate-400 font-medium">Active Courses</p>
              <p className="text-xl font-bold text-white mt-0.5">0</p>
            </div>
          </div>
        </Card>

        <Card className="p-4 bg-slate-900/80 border-slate-800">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
              <Layers className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-slate-400 font-medium">Flashcards Reviewed</p>
              <p className="text-xl font-bold text-white mt-0.5">0</p>
            </div>
          </div>
        </Card>

        <Card className="p-4 bg-slate-900/80 border-slate-800">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <HelpCircle className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-slate-400 font-medium">Quizzes Completed</p>
              <p className="text-xl font-bold text-white mt-0.5">0</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Main Content Grid: System Health & Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Activity / Empty State */}
        <div className="lg:col-span-2 space-y-4">
          <Card
            title="Recent Learning Activity"
            subtitle="Your latest courses, generated lessons, and quizzes"
            className="bg-slate-900/80 border-slate-800"
          >
            <div className="py-12 text-center space-y-3">
              <div className="h-14 w-14 rounded-full bg-slate-800 border border-slate-700/80 flex items-center justify-center mx-auto text-slate-400">
                <BookOpen className="h-6 w-6" />
              </div>
              <h4 className="text-base font-semibold text-slate-200">No courses generated yet</h4>
              <p className="text-xs text-slate-400 max-w-sm mx-auto">
                Upload your first PDF or DOCX file to let our multi-agent RAG engine build your personalized learning track.
              </p>
              <div className="pt-2">
                <Link to="/documents">
                  <Button variant="outline" size="sm" icon={<ArrowRight className="h-4 w-4" />}>
                    Get Started with Documents
                  </Button>
                </Link>
              </div>
            </div>
          </Card>
        </div>

        {/* System & Architecture Status Panel */}
        <div className="space-y-4">
          <Card
            title="Local System Status"
            subtitle="Real-time architecture telemetry"
            className="bg-slate-900/80 border-slate-800"
          >
            {isLoadingHealth ? (
              <Spinner size="md" />
            ) : (
              <div className="space-y-4 text-xs">
                <div className="p-3 rounded-lg bg-slate-800/60 border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between font-medium">
                    <span className="flex items-center gap-1.5 text-slate-300">
                      <Database className="h-4 w-4 text-indigo-400" />
                      SQLite Database
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[11px] ${
                      systemHealth?.database?.status === 'connected' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400'
                    }`}>
                      {systemHealth?.database?.status?.toUpperCase()}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 space-y-0.5">
                    <p>• Journal Mode: <span className="text-slate-200">{systemHealth?.database?.journal_mode || 'WAL'}</span></p>
                    <p>• Foreign Keys: <span className="text-slate-200">{systemHealth?.database?.foreign_keys_enabled ? 'Enforced' : 'Disabled'}</span></p>
                    <p>• Engine: <span className="text-slate-200">{systemHealth?.database?.database}</span></p>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-slate-800/60 border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between font-medium">
                    <span className="flex items-center gap-1.5 text-slate-300">
                      <HardDrive className="h-4 w-4 text-purple-400" />
                      Local Storage
                    </span>
                    <span className="px-2 py-0.5 rounded text-[11px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      PERSISTENT
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 space-y-0.5">
                    <p>• Uploads Dir: <span className="text-slate-200">backend/uploads/</span></p>
                    <p>• Chroma Vector DB: <span className="text-slate-200">backend/chroma_data/</span></p>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-slate-800/60 border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between font-medium">
                    <span className="flex items-center gap-1.5 text-slate-300">
                      <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                      Hybrid AI Engine
                    </span>
                    <span className="px-2 py-0.5 rounded text-[11px] bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                      READY
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 space-y-0.5">
                    <p>• Local Model: <span className="text-slate-200">{systemHealth?.ai_providers?.local_model || 'qwen2.5:7b'}</span></p>
                    <p>• Embeddings: <span className="text-slate-200">all-MiniLM-L6-v2</span></p>
                  </div>
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
};
