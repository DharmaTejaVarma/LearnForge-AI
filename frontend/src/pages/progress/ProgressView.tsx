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
  if (!stats) return <div className="text-center text-ink-secondary">Failed to load statistics.</div>;

  const weekly = stats.weekly_activity || [];
  const maxActions = Math.max(1, ...weekly.map((w) => w.actions));

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      <div>
        <h1 className="lf-heading-main">Learning Analytics &amp; Knowledge Retention</h1>
        <p className="text-sm text-ink-secondary mt-1">
          Real-time Analytics Agent telemetry across courses, lesson completion, SM-2 flashcards, and quiz performance
        </p>
      </div>

      {/* Main Mastery Hero Card (Dark Gradient) */}
      <div className="rounded-[12px] lf-gradient-dark border border-indigo-400/20 p-6 md:p-8 shadow-card text-white">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="space-y-2 text-center sm:text-left">
            <span className="text-xs font-semibold uppercase tracking-wider text-violet-300">
              Retention Score
            </span>
            <h2 className="text-3xl md:text-4xl font-bold text-white">
              {stats.overall_mastery_percentage}% Overall Mastery
            </h2>
            <p className="text-xs md:text-sm text-indigo-100/90 max-w-md">
              Synthesized from {stats.completed_lessons} completed lessons, {stats.flashcards_reviewed ?? 0} flashcard reviews, and {stats.quizzes_taken} quiz attempts.
            </p>
          </div>

          <div className="h-28 w-28 rounded-full border-4 border-violet-400/50 flex items-center justify-center p-3 text-center bg-white/10 backdrop-blur-sm shrink-0">
            <div>
              <p className="text-2xl font-bold text-white">{Math.round(stats.overall_mastery_percentage)}%</p>
              <p className="text-[10px] text-indigo-200 uppercase font-semibold">Mastery</p>
            </div>
          </div>
        </div>
      </div>

      {/* Metric Tiles */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-[10px] bg-brand-soft border border-brand-soft-border flex items-center justify-center text-brand shrink-0">
              <BookOpen className="h-5 w-5" />
            </div>
            <div>
              <p className="lf-label-sm">Lessons Finished</p>
              <p className="text-xl font-bold text-ink-primary mt-0.5">
                {stats.completed_lessons} / {stats.total_lessons}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-[10px] bg-accent-soft border border-accent-soft-border flex items-center justify-center text-accent shrink-0">
              <Layers className="h-5 w-5" />
            </div>
            <div>
              <p className="lf-label-sm">Flashcards Mastered</p>
              <p className="text-xl font-bold text-ink-primary mt-0.5">
                {stats.flashcards_mastered} / {stats.total_flashcards}
              </p>
              <p className="text-[11px] text-accent font-medium mt-0.5">{stats.flashcards_due ?? 0} due for SM-2 review</p>
            </div>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-[10px] bg-brand-soft border border-brand-soft-border flex items-center justify-center text-brand shrink-0">
              <HelpCircle className="h-5 w-5" />
            </div>
            <div>
              <p className="lf-label-sm">Quizzes Completed</p>
              <p className="text-xl font-bold text-ink-primary mt-0.5">{stats.quizzes_taken}</p>
            </div>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-[10px] bg-accent-soft border border-accent-soft-border flex items-center justify-center text-accent shrink-0">
              <Award className="h-5 w-5" />
            </div>
            <div>
              <p className="lf-label-sm">Avg Quiz Accuracy</p>
              <p className="text-xl font-bold text-ink-primary mt-0.5">{stats.average_quiz_score}%</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Charts Row: Weekly Activity + Course Completion */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card
          title="Weekly Study Consistency"
          subtitle="Daily completed lessons, flashcard reviews, quiz attempts & tutor turns"
        >
          <div className="flex items-end justify-between gap-3 h-40 pt-6">
            {weekly.map((day) => {
              const heightPct = day.actions > 0 ? Math.max(14, Math.round((day.actions / maxActions) * 100)) : 6;
              return (
                <div key={day.date} className="flex-1 flex flex-col items-center gap-2 h-full justify-end">
                  <span className="text-xs font-mono text-accent font-medium">{day.actions}</span>
                  <div className="w-full max-w-[34px] bg-subtle rounded-t-lg flex items-end h-24 overflow-hidden">
                    <div
                      className={`w-full rounded-t-lg transition-all ${day.actions > 0 ? 'lf-gradient-primary' : 'bg-line'}`}
                      style={{ height: `${heightPct}%` }}
                    />
                  </div>
                  <span className="text-[11px] text-ink-secondary font-medium">{day.label}</span>
                </div>
              );
            })}
          </div>
        </Card>

        <Card
          title="Course Completion Breakdown"
          subtitle="Curriculum progress across active courses"
        >
          {stats.course_progress && stats.course_progress.length > 0 ? (
            <div className="space-y-4 pt-2">
              {stats.course_progress.map((cp) => (
                <Link key={cp.course_id} to={`/courses/${cp.course_id}`} className="block group">
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <span className="font-semibold text-ink-primary group-hover:text-brand truncate pr-3 transition-colors">
                      {cp.title}
                    </span>
                    <span className="text-ink-secondary font-mono shrink-0">
                      {cp.completed_lessons}/{cp.total_lessons} ({cp.completion_percentage}%)
                    </span>
                  </div>
                  <div className="h-2 bg-subtle rounded-full overflow-hidden">
                    <div
                      className="h-full bg-accent rounded-full transition-all"
                      style={{ width: `${cp.completion_percentage}%` }}
                    />
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="py-10 text-center text-xs text-ink-secondary">
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
        >
          {stats.recommendations && stats.recommendations.length > 0 ? (
            <div className="space-y-2.5 pt-2">
              {stats.recommendations.map((rec, idx) => (
                <div key={idx} className="p-3 rounded-[10px] bg-subtle border border-line flex items-start gap-2.5 text-xs text-ink-primary">
                  <Sparkles className="h-4 w-4 text-accent shrink-0 mt-0.5" />
                  <span>{rec}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-8 text-center text-xs text-ink-secondary flex flex-col items-center gap-2">
              <TrendingUp className="h-7 w-7 text-accent" />
              <span>Keep studying to unlock personalized recommendations.</span>
            </div>
          )}
        </Card>

        <Card
          title="Identified Weak Concepts"
          subtitle="Captured from missed quiz questions and unmastered flashcards"
        >
          {stats.weak_topics && stats.weak_topics.length > 0 ? (
            <div className="space-y-3 pt-2">
              {stats.weak_topics.map((topic, idx) => (
                <div
                  key={idx}
                  className="p-3.5 rounded-[10px] bg-subtle border border-line flex items-center justify-between text-xs gap-3"
                >
                  <div className="flex items-center gap-2.5 text-ink-primary min-w-0">
                    <AlertTriangle className="h-4 w-4 text-status-warning-text shrink-0" />
                    <span className="truncate">{topic}</span>
                  </div>
                  <Link
                    to="/tutor"
                    className="text-[11px] font-medium text-brand bg-brand-soft hover:bg-hoverbg-strong border border-brand-soft-border px-2.5 py-1 rounded-[10px] shrink-0 transition-colors"
                  >
                    Ask Tutor
                  </Link>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-8 text-center text-xs text-ink-secondary">
              <CheckCircle2 className="h-8 w-8 text-status-success-text mx-auto mb-2" />
              No weak concepts recorded yet! Complete a quiz to identify targeted review topics.
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};
