import React, { useState, useEffect } from 'react';
import { Card } from '../../components/common/Card';
import { Spinner } from '../../components/common/Spinner';
import { learningService, ProgressStats } from '../../services/learningService';
import {
  BookOpen,
  Layers,
  HelpCircle,
  CheckCircle2,
  AlertTriangle,
  Award,
  TrendingUp,
  Sparkles,
} from 'lucide-react';
import { Link } from 'react-router-dom';

export const ProgressView: React.FC = () => {
  const [stats, setStats] = useState<ProgressStats | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchProgress = async () => {
      try {
        const data = await learningService.getProgress();
        setStats(data);
      } catch (err) {
        console.error('Failed to load progress telemetry:', err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchProgress();
  }, []);

  if (isLoading) return <Spinner size="lg" />;
  if (!stats) return <div className="text-center text-slate-400">Failed to load statistics.</div>;

  const weekly = stats.weekly_activity || [];
  const maxActions = Math.max(1, ...weekly.map((w) => w.actions));

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight">
          Learning Analytics & Knowledge Retention
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Real-time Analytics Agent telemetry across courses, lesson completion, SM-2 flashcards, and quiz performance
        </p>
      </div>

      {/* Main Mastery Hero Card */}
      <Card className="bg-gradient-to-r from-indigo-950/80 via-purple-950/40 to-slate-900 border-indigo-500/20 p-8">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="space-y-2 text-center sm:text-left">
            <span className="text-xs font-semibold uppercase tracking-wider text-indigo-400">
              Retention Score
            </span>
            <h2 className="text-3xl md:text-4xl font-extrabold text-white">
              {stats.overall_mastery_percentage}% Overall Mastery
            </h2>
            <p className="text-xs md:text-sm text-slate-300 max-w-md">
              Synthesized from {stats.completed_lessons} completed lessons, {stats.flashcards_reviewed ?? 0} flashcard reviews, and {stats.quizzes_taken} quiz attempts.
            </p>
          </div>

          <div className="h-28 w-28 rounded-full border-4 border-indigo-500/30 flex items-center justify-center p-3 text-center bg-indigo-950/40">
            <div>
              <p className="text-2xl font-black text-indigo-400">{Math.round(stats.overall_mastery_percentage)}%</p>
              <p className="text-[10px] text-slate-400 uppercase font-semibold">Mastery</p>
            </div>
          </div>
        </div>
      </Card>

      {/* Metric Tiles */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-5 bg-slate-900 border-slate-800">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
              <BookOpen className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-slate-400 font-medium">Lessons Finished</p>
              <p className="text-xl font-bold text-white mt-0.5">
                {stats.completed_lessons} / {stats.total_lessons}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-5 bg-slate-900 border-slate-800">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
              <Layers className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-slate-400 font-medium">Flashcards Mastered</p>
              <p className="text-xl font-bold text-white mt-0.5">
                {stats.flashcards_mastered} / {stats.total_flashcards}
              </p>
              <p className="text-[10px] text-indigo-300 mt-0.5">{stats.flashcards_due ?? 0} due for SM-2 review</p>
            </div>
          </div>
        </Card>

        <Card className="p-5 bg-slate-900 border-slate-800">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <HelpCircle className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-slate-400 font-medium">Quizzes Completed</p>
              <p className="text-xl font-bold text-white mt-0.5">{stats.quizzes_taken}</p>
            </div>
          </div>
        </Card>

        <Card className="p-5 bg-slate-900 border-slate-800">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
              <Award className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-slate-400 font-medium">Avg Quiz Accuracy</p>
              <p className="text-xl font-bold text-white mt-0.5">{stats.average_quiz_score}%</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Charts Row: Weekly Activity + Course Completion */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card
          title="Weekly Study Consistency"
          subtitle="Daily completed lessons, flashcard reviews, quiz attempts & tutor turns"
          className="bg-slate-900 border-slate-800"
        >
          <div className="flex items-end justify-between gap-3 h-40 pt-6">
            {weekly.map((day) => {
              const heightPct = day.actions > 0 ? Math.max(14, Math.round((day.actions / maxActions) * 100)) : 6;
              return (
                <div key={day.date} className="flex-1 flex flex-col items-center gap-2 h-full justify-end">
                  <span className="text-xs font-mono text-indigo-300">{day.actions}</span>
                  <div className="w-full max-w-[34px] bg-slate-800 rounded-t-lg flex items-end h-24 overflow-hidden">
                    <div
                      className={`w-full rounded-t-lg transition-all ${day.actions > 0 ? 'bg-gradient-to-t from-indigo-600 to-purple-500' : 'bg-slate-700/40'}`}
                      style={{ height: `${heightPct}%` }}
                    />
                  </div>
                  <span className="text-[11px] text-slate-400 font-medium">{day.label}</span>
                </div>
              );
            })}
          </div>
        </Card>

        <Card
          title="Course Completion Breakdown"
          subtitle="Curriculum progress across active courses"
          className="bg-slate-900 border-slate-800"
        >
          {stats.course_progress && stats.course_progress.length > 0 ? (
            <div className="space-y-4 pt-2">
              {stats.course_progress.map((cp) => (
                <Link key={cp.course_id} to={`/courses/${cp.course_id}`} className="block group">
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <span className="font-semibold text-slate-200 group-hover:text-indigo-400 truncate pr-3">
                      {cp.title}
                    </span>
                    <span className="text-slate-400 font-mono shrink-0">
                      {cp.completed_lessons}/{cp.total_lessons} ({cp.completion_percentage}%)
                    </span>
                  </div>
                  <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-indigo-500 rounded-full transition-all"
                      style={{ width: `${cp.completion_percentage}%` }}
                    />
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="py-10 text-center text-xs text-slate-500">
              Generate a course from your study materials to track module progress.
            </div>
          )}
        </Card>
      </div>

      {/* Recommendations + Weak Topics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card
          title="Adaptive Study Recommendations"
          subtitle="Actionable next steps synthesized from your learning history"
          className="bg-slate-900 border-slate-800"
        >
          {stats.recommendations && stats.recommendations.length > 0 ? (
            <div className="space-y-2.5 pt-2">
              {stats.recommendations.map((rec, idx) => (
                <div key={idx} className="p-3 rounded-xl bg-slate-800/40 border border-slate-800 flex items-start gap-2.5 text-xs text-slate-200">
                  <Sparkles className="h-4 w-4 text-indigo-400 shrink-0 mt-0.5" />
                  <span>{rec}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-8 text-center text-xs text-slate-400 flex flex-col items-center gap-2">
              <TrendingUp className="h-7 w-7 text-indigo-400" />
              <span>Keep studying to unlock personalized recommendations.</span>
            </div>
          )}
        </Card>

        <Card
          title="Identified Weak Concepts"
          subtitle="Captured from missed quiz questions and unmastered flashcards"
          className="bg-slate-900 border-slate-800"
        >
          {stats.weak_topics && stats.weak_topics.length > 0 ? (
            <div className="space-y-3 pt-2">
              {stats.weak_topics.map((topic, idx) => (
                <div
                  key={idx}
                  className="p-3.5 rounded-xl bg-slate-800/40 border border-slate-800 flex items-center justify-between text-xs gap-3"
                >
                  <div className="flex items-center gap-2.5 text-slate-300 min-w-0">
                    <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
                    <span className="truncate">{topic}</span>
                  </div>
                  <Link
                    to="/tutor"
                    className="text-[11px] font-medium text-indigo-400 bg-indigo-500/10 hover:bg-indigo-500/20 px-2.5 py-1 rounded shrink-0"
                  >
                    Ask Tutor
                  </Link>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-8 text-center text-xs text-slate-400">
              <CheckCircle2 className="h-8 w-8 text-emerald-400 mx-auto mb-2" />
              No weak concepts recorded yet! Complete a quiz to identify targeted review topics.
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};
