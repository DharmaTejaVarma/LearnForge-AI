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
  Award
} from 'lucide-react';

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

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight">
          Learning Analytics & Knowledge Retention
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Detailed metrics across courses, lesson completion, flashcard mastery, and quiz performance
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
              Synthesized from completed lesson checkpoints, active recall repetitions, and assessment accuracy.
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
              <p className="text-xl font-bold text-white mt-0.5">
                {stats.quizzes_taken}
              </p>
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
              <p className="text-xl font-bold text-white mt-0.5">
                {stats.average_quiz_score}%
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Weak Topics & Personalized Recommendations */}
      <Card
        title="Personalized Review Recommendations"
        subtitle="Identified from quiz results and unmastered flashcard decks"
        className="bg-slate-900 border-slate-800"
      >
        {stats.weak_topics && stats.weak_topics.length > 0 ? (
          <div className="space-y-3 pt-2">
            {stats.weak_topics.map((topic, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-xl bg-slate-800/40 border border-slate-800 flex items-center justify-between text-xs"
              >
                <div className="flex items-center gap-2.5 text-slate-300">
                  <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
                  <span>{topic}</span>
                </div>
                <span className="text-[11px] font-medium text-indigo-400 bg-indigo-500/10 px-2.5 py-0.5 rounded">
                  Recommended Action
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-8 text-center text-xs text-slate-400">
            <CheckCircle2 className="h-8 w-8 text-emerald-400 mx-auto mb-2" />
            No weak topics detected. Your learning retention is in excellent shape!
          </div>
        )}
      </Card>
    </div>
  );
};
