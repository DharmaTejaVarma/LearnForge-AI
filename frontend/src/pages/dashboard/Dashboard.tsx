import React, { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Spinner } from '../../components/common/Spinner';
import { authService } from '../../services/authService';
import { learningService, ProgressStats } from '../../services/learningService';
import { courseService, Course } from '../../services/courseService';
import {
  BookOpen,
  FileText,
  Bot,
  Layers,
  HelpCircle,
  CheckCircle2,
  HardDrive,
  Database,
  ArrowRight,
  ChevronRight,
  TrendingUp,
  AlertTriangle,
  Sparkles,
} from 'lucide-react';
import { Link } from 'react-router-dom';

export const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const [systemHealth, setSystemHealth] = useState<any>(null);
  const [stats, setStats] = useState<ProgressStats | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [isLoadingHealth, setIsLoadingHealth] = useState<boolean>(true);

  useEffect(() => {
    const fetchDashboard = async () => {
      const [healthRes, progressRes, coursesRes] = await Promise.allSettled([
        authService.getHealth(),
        learningService.getProgress(),
        courseService.list(),
      ]);

      if (healthRes.status === 'fulfilled') {
        setSystemHealth(healthRes.value);
      } else {
        setSystemHealth({ status: 'offline', database: { status: 'disconnected' } });
      }
      if (progressRes.status === 'fulfilled') {
        setStats(progressRes.value);
      }
      if (coursesRes.status === 'fulfilled') {
        setCourses(coursesRes.value);
      }
      setIsLoadingHealth(false);
    };
    fetchDashboard();
  }, []);

  const weekly = stats?.weekly_activity || [];
  const maxWeeklyActions = Math.max(1, ...weekly.map((w) => w.actions));

  return (
    <div className="space-y-8">
      {/* Welcome Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-indigo-900/60 via-purple-900/40 to-slate-900 border border-indigo-500/20 p-6 md:p-8">
        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="max-w-2xl space-y-3">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 text-xs font-medium">
              <Sparkles className="h-3.5 w-3.5" />
              <span>LangGraph Multi-Agent Learning</span>
            </div>
            <h1 className="text-3xl font-extrabold text-white tracking-tight">
              Welcome back, {user?.full_name || user?.email.split('@')[0]}!
            </h1>
            <p className="text-slate-300 text-sm md:text-base leading-relaxed">
              Upload textbooks, research notes, or slide decks to synthesize modular courses, SM-2 flashcards, adaptive quizzes, and 1-on-1 Socratic tutoring.
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

          <div className="flex items-center gap-4 bg-slate-950/60 border border-slate-800 rounded-2xl px-5 py-4 shrink-0">
            <div>
              <p className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Overall Mastery</p>
              <p className="text-3xl font-black text-indigo-400 mt-0.5">
                {stats ? `${stats.overall_mastery_percentage}%` : '0%'}
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">
                {stats?.completed_lessons ?? 0}/{stats?.total_lessons ?? 0} lessons completed
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* KPI Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4 bg-slate-900/80 border-slate-800">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
              <FileText className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-slate-400 font-medium">Uploaded Documents</p>
              <p className="text-xl font-bold text-white mt-0.5">{stats?.total_documents ?? 0}</p>
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
              <p className="text-xl font-bold text-white mt-0.5">{stats?.total_courses ?? courses.length}</p>
            </div>
          </div>
        </Card>

        <Card className="p-4 bg-slate-900/80 border-slate-800">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
              <Layers className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-slate-400 font-medium">Flashcards Mastered</p>
              <p className="text-xl font-bold text-white mt-0.5">
                {stats ? `${stats.flashcards_mastered}/${stats.total_flashcards}` : '0/0'}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-4 bg-slate-900/80 border-slate-800">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <HelpCircle className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-slate-400 font-medium">Quizzes ({stats?.average_quiz_score ?? 0}% avg)</p>
              <p className="text-xl font-bold text-white mt-0.5">{stats?.quizzes_taken ?? 0}</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Main Content Grid: Activity, Charts & Health */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Courses & Weekly Activity */}
        <div className="lg:col-span-2 space-y-6">
          {/* Weekly Study Activity + Recommended Next Lessons */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card
              title="Weekly Study Activity"
              subtitle="Recorded events over the last 7 days"
              className="bg-slate-900/80 border-slate-800"
            >
              {weekly.length > 0 ? (
                <div className="flex items-end justify-between gap-2 h-32 pt-4">
                  {weekly.map((day) => {
                    const heightPct = day.actions > 0 ? Math.max(14, Math.round((day.actions / maxWeeklyActions) * 100)) : 6;
                    return (
                      <div key={day.date} className="flex-1 flex flex-col items-center gap-1.5 h-full justify-end">
                        <span className="text-[10px] font-mono text-slate-400">{day.actions}</span>
                        <div className="w-full max-w-[26px] bg-slate-800 rounded-t-md flex items-end h-20 overflow-hidden">
                          <div
                            className={`w-full rounded-t-md transition-all ${day.actions > 0 ? 'bg-indigo-500' : 'bg-slate-700/50'}`}
                            style={{ height: `${heightPct}%` }}
                            title={`${day.date}: ${day.actions} learning actions`}
                          />
                        </div>
                        <span className="text-[10px] text-slate-500 font-medium">{day.label}</span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-xs text-slate-500 py-8 text-center">Complete lessons, quizzes, or tutor sessions to track weekly activity.</p>
              )}
            </Card>

            <Card
              title="Recommended Next"
              subtitle="Personalized priorities from Analytics Agent"
              className="bg-slate-900/80 border-slate-800"
            >
              <div className="space-y-2.5 text-xs">
                {stats?.recommended_next_lessons && stats.recommended_next_lessons.length > 0 ? (
                  stats.recommended_next_lessons.slice(0, 3).map((item) => (
                    <Link
                      key={item.lesson_id}
                      to={`/courses/${item.course_id}`}
                      className="flex items-center justify-between p-2.5 rounded-lg bg-slate-800/50 hover:bg-slate-800 border border-slate-800 transition-colors"
                    >
                      <div className="min-w-0 pr-2">
                        <p className="font-medium text-white truncate">{item.lesson_title}</p>
                        <p className="text-[11px] text-slate-400 truncate">{item.course_title}</p>
                      </div>
                      <ChevronRight className="h-4 w-4 text-indigo-400 shrink-0" />
                    </Link>
                  ))
                ) : (
                  <p className="text-slate-400 py-4 text-center">All available lessons completed or awaiting course synthesis.</p>
                )}

                {stats?.weak_topics && stats.weak_topics.length > 0 && (
                  <div className="pt-2 border-t border-slate-800 flex items-start gap-2 text-amber-300">
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                    <span className="line-clamp-2">Focus area: {stats.weak_topics[0]}</span>
                  </div>
                )}
              </div>
            </Card>
          </div>

          {/* Recent Courses */}
          <Card
            title="Recent Courses"
            subtitle="Progress across your generated learning tracks"
            className="bg-slate-900/80 border-slate-800"
          >
            {courses.length > 0 ? (
              <div className="divide-y divide-slate-800">
                {courses.slice(0, 5).map((course) => {
                  const cp = stats?.course_progress?.find((c) => c.course_id === course.id);
                  return (
                    <Link
                      key={course.id}
                      to={`/courses/${course.id}`}
                      className="py-3.5 flex items-center justify-between gap-4 hover:bg-slate-800/40 px-2 rounded-lg transition-colors group"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm font-semibold text-white group-hover:text-indigo-400 truncate">
                            {course.title}
                          </p>
                          {cp && (
                            <span className="text-[11px] font-mono text-indigo-300 shrink-0">
                              {cp.completed_lessons}/{cp.total_lessons} ({cp.completion_percentage}%)
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-400 truncate mt-0.5">
                          {course.difficulty_level} • {course.description}
                        </p>
                        {cp && (
                          <div className="mt-2 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-indigo-500 rounded-full"
                              style={{ width: `${cp.completion_percentage}%` }}
                            />
                          </div>
                        )}
                      </div>
                      <ChevronRight className="h-4 w-4 text-slate-500 group-hover:text-indigo-400 shrink-0" />
                    </Link>
                  );
                })}
              </div>
            ) : (
              <div className="py-10 text-center space-y-3">
                <div className="h-14 w-14 rounded-full bg-slate-800 border border-slate-700/80 flex items-center justify-center mx-auto text-slate-400">
                  <BookOpen className="h-6 w-6" />
                </div>
                <h4 className="text-base font-semibold text-slate-200">No courses generated yet</h4>
                <p className="text-xs text-slate-400 max-w-sm mx-auto">
                  Upload your first document to let our multi-agent RAG engine build your personalized learning track.
                </p>
                <div className="pt-2">
                  <Link to="/documents">
                    <Button variant="outline" size="sm" icon={<ArrowRight className="h-4 w-4" />}>
                      Get Started with Documents
                    </Button>
                  </Link>
                </div>
              </div>
            )}
          </Card>
        </div>

        {/* System & Architecture Status Panel */}
        <div className="space-y-4">
          <Card
            title="AI & System Telemetry"
            subtitle="Live backend and model router status"
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
                      {systemHealth?.database?.status?.toUpperCase() || 'UNKNOWN'}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 space-y-0.5">
                    <p>• Journal Mode: <span className="text-slate-200">{systemHealth?.database?.journal_mode || 'WAL'}</span></p>
                    <p>• Foreign Keys: <span className="text-slate-200">{systemHealth?.database?.foreign_keys_enabled ? 'Enforced' : 'Disabled'}</span></p>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-slate-800/60 border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between font-medium">
                    <span className="flex items-center gap-1.5 text-slate-300">
                      <HardDrive className="h-4 w-4 text-purple-400" />
                      Local Storage
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[11px] border ${
                      systemHealth?.storage?.uploads_writable && systemHealth?.storage?.chroma_writable
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                    }`}>
                      {systemHealth?.storage?.uploads_writable ? 'WRITABLE' : 'CHECK'}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 space-y-0.5">
                    <p>• Uploads: <span className="text-slate-200">{systemHealth?.storage?.uploads_writable ? 'Active' : 'Unavailable'}</span></p>
                    <p>• ChromaDB Vectors: <span className="text-slate-200">{systemHealth?.storage?.chroma_writable ? 'Active' : 'Unavailable'}</span></p>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-slate-800/60 border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between font-medium">
                    <span className="flex items-center gap-1.5 text-slate-300">
                      <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                      Hybrid AI Router
                    </span>
                    <span className="px-2 py-0.5 rounded text-[11px] bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                      {systemHealth?.ai_providers?.local_ollama?.online ? 'LOCAL READY' : 'CHECK OLLAMA'}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 space-y-0.5">
                    <p>• Active Local Model: <span className="text-slate-200">{systemHealth?.ai_providers?.local_ollama?.active_model || 'unavailable'}</span></p>
                    <p>• Cloud OpenAI: <span className="text-slate-200">{systemHealth?.ai_providers?.cloud_openai?.disabled_reason ? 'Fallback to Local' : systemHealth?.ai_providers?.cloud_openai?.configured ? 'Configured' : 'Not Configured'}</span></p>
                    <p>• Embeddings: <span className="text-slate-200 truncate block">{systemHealth?.ai_providers?.embedding_model}</span></p>
                    {systemHealth?.ai_metrics && (
                      <p className="flex items-center gap-1 pt-1 text-indigo-300">
                        <TrendingUp className="h-3 w-3" />
                        Avg Latency: {Math.round(systemHealth.ai_metrics.avg_latency_ms || 0)}ms ({systemHealth.ai_metrics.total_requests || 0} calls)
                      </p>
                    )}
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
