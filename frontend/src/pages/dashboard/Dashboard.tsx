import React, { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { learningService, ProgressStats } from '../../services/learningService';
import { courseService, Course } from '../../services/courseService';
import {
  BookOpen,
  FileText,
  Bot,
  Layers,
  HelpCircle,
  ArrowRight,
  ChevronRight,
  AlertTriangle,
  Sparkles,
} from 'lucide-react';
import { Link } from 'react-router-dom';

export const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState<ProgressStats | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);

  useEffect(() => {
    const fetchDashboard = async () => {
      const [progressRes, coursesRes] = await Promise.allSettled([
        learningService.getProgress(),
        courseService.list(),
      ]);

      if (progressRes.status === 'fulfilled') {
        setStats(progressRes.value);
      }
      if (coursesRes.status === 'fulfilled') {
        setCourses(coursesRes.value);
      }
    };
    fetchDashboard();
  }, []);

  const weekly = stats?.weekly_activity || [];
  const maxWeeklyActions = Math.max(1, ...weekly.map((w) => w.actions));
  const masteryPct = stats?.overall_mastery_percentage ?? 0;

  return (
    <div className="space-y-8">
      {/* Featured Welcome Banner (Dark Gradient used sparingly for hero highlight) */}
      <div className="relative overflow-hidden rounded-[12px] lf-gradient-dark border border-indigo-400/20 p-6 md:p-8 shadow-card text-white">
        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="max-w-2xl space-y-3">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 border border-white/15 text-indigo-100 text-xs font-medium">
              <Sparkles className="h-3.5 w-3.5 text-violet-300" />
              <span>LangGraph Multi-Agent Learning</span>
            </div>
            <h1 className="text-[26px] md:text-[32px] font-bold leading-[1.2] tracking-tight text-white">
              Welcome back, {user?.full_name || user?.email.split('@')[0]}!
            </h1>
            <p className="text-indigo-100/90 text-[15px] md:text-base leading-relaxed">
              Upload textbooks, research notes, or slide decks to synthesize modular courses, SM-2 flashcards, adaptive quizzes, and 1-on-1 Socratic tutoring.
            </p>
            <div className="pt-2 flex flex-wrap gap-3">
              <Link to="/documents">
                <Button variant="primary" icon={<FileText className="h-4 w-4" />}>
                  Upload Documents
                </Button>
              </Link>
              <Link to="/tutor">
                <Button
                  variant="ghost"
                  className="bg-white/10 hover:bg-white/20 text-white border border-white/20"
                  icon={<Bot className="h-4 w-4" />}
                >
                  Ask AI Tutor
                </Button>
              </Link>
            </div>
          </div>

          <div className="bg-white/10 border border-white/15 backdrop-blur-sm rounded-[12px] p-5 min-w-[210px] shrink-0 space-y-2.5">
            <div className="flex items-center justify-between">
              <p className="text-xs uppercase tracking-wider text-indigo-200 font-medium">Overall Mastery</p>
              <span className="text-xs font-semibold text-violet-200">{masteryPct}%</span>
            </div>
            <p className="text-3xl font-bold text-white leading-none">{masteryPct}%</p>
            <div className="h-2 w-full rounded-full bg-white/15 overflow-hidden">
              <div
                className="h-full lf-gradient-highlight rounded-full transition-all duration-300"
                style={{ width: `${masteryPct}%` }}
              />
            </div>
            <p className="text-xs text-indigo-200/90">
              {stats?.completed_lessons ?? 0}/{stats?.total_lessons ?? 0} lessons completed
            </p>
          </div>
        </div>
      </div>

      {/* KPI Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Link to="/documents" className="block">
          <Card interactive className="p-5 h-full">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="lf-label-sm">Uploaded Documents</p>
                <p className="text-2xl font-bold text-ink-primary mt-1">{stats?.total_documents ?? 0}</p>
              </div>
              <div className="h-11 w-11 rounded-[10px] bg-brand-soft border border-brand-soft-border flex items-center justify-center text-brand shrink-0">
                <FileText className="h-5 w-5" />
              </div>
            </div>
          </Card>
        </Link>

        <Link to="/courses" className="block">
          <Card interactive className="p-5 h-full">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="lf-label-sm">Active Courses</p>
                <p className="text-2xl font-bold text-ink-primary mt-1">{stats?.total_courses ?? courses.length}</p>
              </div>
              <div className="h-11 w-11 rounded-[10px] bg-brand-soft border border-brand-soft-border flex items-center justify-center text-brand shrink-0">
                <BookOpen className="h-5 w-5" />
              </div>
            </div>
          </Card>
        </Link>

        <Link to="/flashcards" className="block">
          <Card interactive className="p-5 h-full">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="lf-label-sm">Flashcards Mastered</p>
                <p className="text-2xl font-bold text-ink-primary mt-1">
                  {stats ? `${stats.flashcards_mastered}/${stats.total_flashcards}` : '0/0'}
                </p>
              </div>
              <div className="h-11 w-11 rounded-[10px] bg-accent-soft border border-accent-soft-border flex items-center justify-center text-accent shrink-0">
                <Layers className="h-5 w-5" />
              </div>
            </div>
          </Card>
        </Link>

        <Link to="/quizzes" className="block">
          <Card interactive className="p-5 h-full">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="lf-label-sm">Quizzes ({stats?.average_quiz_score ?? 0}% avg)</p>
                <p className="text-2xl font-bold text-ink-primary mt-1">{stats?.quizzes_taken ?? 0}</p>
              </div>
              <div className="h-11 w-11 rounded-[10px] bg-accent-soft border border-accent-soft-border flex items-center justify-center text-accent shrink-0">
                <HelpCircle className="h-5 w-5" />
              </div>
            </div>
          </Card>
        </Link>
      </div>

      {/* Main Content: Activity & Courses */}
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card
              title="Weekly Study Activity"
              subtitle="Recorded events over the last 7 days"
            >
              {weekly.length > 0 ? (
                <div className="flex items-end justify-between gap-2 h-32 pt-4">
                  {weekly.map((day) => {
                    const heightPct = day.actions > 0 ? Math.max(14, Math.round((day.actions / maxWeeklyActions) * 100)) : 6;
                    return (
                      <div key={day.date} className="flex-1 flex flex-col items-center gap-1.5 h-full justify-end">
                        <span className="text-[11px] font-mono text-ink-secondary">{day.actions}</span>
                        <div className="w-full max-w-[26px] bg-subtle rounded-t-md flex items-end h-20 overflow-hidden">
                          <div
                            className={`w-full rounded-t-md transition-all ${day.actions > 0 ? 'lf-gradient-primary' : 'bg-line'}`}
                            style={{ height: `${heightPct}%` }}
                            title={`${day.date}: ${day.actions} learning actions`}
                          />
                        </div>
                        <span className="text-[11px] text-ink-secondary font-medium">{day.label}</span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-xs text-ink-secondary py-8 text-center">
                  Complete lessons, quizzes, or tutor sessions to track weekly activity.
                </p>
              )}
            </Card>

            <Card
              title="Recommended Next"
              subtitle="Personalized priorities from Analytics Agent"
            >
              <div className="space-y-2.5 text-xs">
                {stats?.recommended_next_lessons && stats.recommended_next_lessons.length > 0 ? (
                  stats.recommended_next_lessons.slice(0, 3).map((item) => (
                    <Link
                      key={item.lesson_id}
                      to={`/courses/${item.course_id}`}
                      className="flex items-center justify-between p-2.5 rounded-[10px] bg-subtle hover:bg-hoverbg border border-line transition-colors"
                    >
                      <div className="min-w-0 pr-2">
                        <p className="font-medium text-ink-primary truncate">{item.lesson_title}</p>
                        <p className="text-[11px] text-ink-secondary truncate">{item.course_title}</p>
                      </div>
                      <ChevronRight className="h-4 w-4 text-accent shrink-0" />
                    </Link>
                  ))
                ) : (
                  <p className="text-ink-secondary py-4 text-center">
                    All available lessons completed or awaiting course synthesis.
                  </p>
                )}

                {stats?.weak_topics && stats.weak_topics.length > 0 && (
                  <div className="pt-2.5 border-t border-line flex items-start gap-2 text-status-warning-text">
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                    <span className="line-clamp-2">Focus area: {stats.weak_topics[0]}</span>
                  </div>
                )}
              </div>
            </Card>
          </div>

          <Card
            title="Recent Courses"
            subtitle="Progress across your generated learning tracks"
            action={
              courses.length > 0 ? (
                <Link to="/courses" className="text-xs font-medium text-accent hover:text-accent-hover">
                  View all →
                </Link>
              ) : undefined
            }
          >
            {courses.length > 0 ? (
              <div className="divide-y divide-line">
                {courses.slice(0, 5).map((course) => {
                  const cp = stats?.course_progress?.find((c) => c.course_id === course.id);
                  return (
                    <Link
                      key={course.id}
                      to={`/courses/${course.id}`}
                      className="py-3.5 flex items-center justify-between gap-4 hover:bg-hoverbg px-3 -mx-1 rounded-[10px] transition-colors group"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm font-semibold text-ink-primary group-hover:text-brand truncate">
                            {course.title}
                          </p>
                          {cp && (
                            <span className="text-xs font-mono text-accent font-medium shrink-0">
                              {cp.completed_lessons}/{cp.total_lessons} ({cp.completion_percentage}%)
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-ink-secondary truncate mt-0.5">
                          {course.difficulty_level} • {course.description}
                        </p>
                        {cp && (
                          <div className="mt-2 h-1.5 bg-subtle rounded-full overflow-hidden">
                            <div
                              className="h-full bg-accent rounded-full transition-all"
                              style={{ width: `${cp.completion_percentage}%` }}
                            />
                          </div>
                        )}
                      </div>
                      <ChevronRight className="h-4 w-4 text-ink-secondary group-hover:text-accent shrink-0" />
                    </Link>
                  );
                })}
              </div>
            ) : (
              <div className="py-10 text-center space-y-3">
                <div className="h-14 w-14 rounded-full bg-brand-soft border border-brand-soft-border flex items-center justify-center mx-auto text-brand">
                  <BookOpen className="h-6 w-6" />
                </div>
                <h4 className="text-base font-semibold text-ink-primary">No courses generated yet</h4>
                <p className="text-xs text-ink-secondary max-w-sm mx-auto">
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
    </div>
  );
};
