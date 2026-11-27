import React, { useState, useEffect } from 'react';
import {
  CourseAssessment,
  AssessmentResult,
  courseService,
} from '../../services/courseService';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Spinner } from '../common/Spinner';
import {
  Award,
  CheckCircle2,
  XCircle,
  ArrowLeft,
  Send,
  BookOpen,
  RotateCcw,
} from 'lucide-react';

interface AssessmentPanelProps {
  courseId: number;
  chapterId: number | null;
  onBackToOverview: () => void;
  onJumpToLesson: (lessonId: number) => void;
}

export const AssessmentPanel: React.FC<AssessmentPanelProps> = ({
  courseId,
  chapterId,
  onBackToOverview,
  onJumpToLesson,
}) => {
  const [assessment, setAssessment] = useState<CourseAssessment | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<AssessmentResult | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setIsLoading(true);
      setError(null);
      setResult(null);
      setAnswers({});
      try {
        const data =
          chapterId !== null
            ? await courseService.getModuleAssessment(courseId, chapterId)
            : await courseService.getFinalAssessment(courseId);
        if (active) setAssessment(data);
      } catch (err: any) {
        if (active) setError(err?.response?.data?.error?.message || err.message || 'Failed to load assessment.');
      } finally {
        if (active) setIsLoading(false);
      }
    };
    load();
    return () => {
      active = false;
    };
  }, [courseId, chapterId]);

  const handleSubmit = async () => {
    if (!assessment) return;
    setIsSubmitting(true);
    try {
      const res = await courseService.submitAssessment(courseId, assessment.id, answers);
      setResult(res);
    } catch (err: any) {
      setError(err?.response?.data?.error?.message || err.message || 'Submission failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="py-20 flex flex-col items-center justify-center space-y-3">
        <Spinner size="lg" />
        <p className="text-xs text-ink-secondary">Preparing grounded assessment questions...</p>
      </div>
    );
  }

  if (error || !assessment) {
    return (
      <Card className="p-8 space-y-4">
        <p className="text-sm text-status-danger-text">{error || 'Assessment unavailable.'}</p>
        <Button size="sm" variant="secondary" onClick={onBackToOverview} icon={<ArrowLeft className="h-4 w-4" />}>
          Back to Overview
        </Button>
      </Card>
    );
  }

  const answeredCount = assessment.questions.filter((q) => answers[q.id]).length;

  return (
    <div className="space-y-6 max-w-5xl mx-auto animate-fadeIn">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={onBackToOverview}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-ink-secondary hover:text-ink-primary transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Course Overview
        </button>

        {assessment.best_score !== null && assessment.best_score !== undefined && (
          <span className="text-xs px-3 py-1 rounded-full bg-brand-soft border border-brand-soft-border text-brand font-semibold">
            Best Score: {assessment.best_score}%
          </span>
        )}
      </div>

      <Card className="p-6 md:p-8 space-y-6">
        <div className="border-b border-line pb-5 space-y-2">
          <div className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-accent">
            <Award className="h-4 w-4" />
            <span>{assessment.assessment_type === 'final' ? 'Final Mastery Exam' : 'Module Assessment'}</span>
          </div>
          <h1 className="lf-heading-main">{assessment.title}</h1>
          {assessment.description && (
            <p className="text-sm text-ink-secondary">{assessment.description}</p>
          )}
        </div>

        {/* Graded Result View */}
        {result && (
          <div
            className={`p-5 rounded-[12px] border space-y-4 ${
              result.passed
                ? 'bg-status-success-bg border-status-success-border'
                : 'bg-status-warning-bg border-status-warning-border'
            }`}
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase font-bold tracking-wider text-ink-secondary">
                  Assessment Result
                </p>
                <h2 className="text-2xl font-bold text-ink-primary mt-0.5">
                  {result.score}% ({result.correct_count}/{result.total_questions} Correct)
                </h2>
              </div>
              <span
                className={`px-3.5 py-1.5 rounded-full text-xs font-bold border self-start ${
                  result.passed
                    ? 'bg-surface text-status-success-text border-status-success-border'
                    : 'bg-surface text-status-warning-text border-status-warning-border'
                }`}
              >
                {result.passed ? 'Passed Mastery Threshold' : 'Review Recommended'}
              </span>
            </div>

            {result.topic_breakdown.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-line">
                <p className="text-xs font-semibold text-ink-primary">Topic Mastery Breakdown</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {result.topic_breakdown.map((tb, idx) => (
                    <div
                      key={idx}
                      className="p-3 rounded-[10px] bg-surface border border-line flex items-center justify-between gap-2 text-xs"
                    >
                      <div className="min-w-0">
                        <p className="text-ink-primary font-medium truncate">{tb.topic_title}</p>
                        <p className="text-ink-secondary">
                          {tb.correct}/{tb.total} ({tb.percentage}%)
                        </p>
                      </div>
                      {tb.percentage < 70 && tb.lesson_id && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => tb.lesson_id && onJumpToLesson(tb.lesson_id)}
                          icon={<BookOpen className="h-3.5 w-3.5" />}
                        >
                          Revise
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  setResult(null);
                  setAnswers({});
                }}
                icon={<RotateCcw className="h-3.5 w-3.5" />}
              >
                Retake Assessment
              </Button>
            </div>
          </div>
        )}

        {/* Questions List */}
        <div className="space-y-5">
          {assessment.questions.map((q, qIdx) => {
            const fb = result?.question_feedback.find((item) => item.id === q.id);
            return (
              <div
                key={q.id}
                className="p-5 rounded-[12px] border border-line bg-subtle space-y-3"
              >
                <div className="flex items-center justify-between gap-2 text-xs">
                  <span className="font-bold text-brand">Question {qIdx + 1}</span>
                  {q.topic_title && (
                    <span className="px-2.5 py-0.5 rounded-full bg-surface border border-line text-ink-secondary">
                      {q.topic_title}
                    </span>
                  )}
                </div>

                <p className="text-base font-medium text-ink-primary leading-relaxed">{q.prompt}</p>

                <div className="space-y-2.5">
                  {q.options.map((opt, optIdx) => {
                    const selected = answers[q.id] === opt;
                    return (
                      <button
                        key={optIdx}
                        type="button"
                        disabled={!!result}
                        onClick={() => setAnswers((p) => ({ ...p, [q.id]: opt }))}
                        className={`w-full text-left px-5 py-3.5 rounded-[10px] border text-sm md:text-[15px] transition-all flex items-start gap-3 ${
                          selected
                            ? 'bg-hoverbg border-brand text-ink-primary font-medium'
                            : 'bg-surface border-line text-ink-secondary hover:bg-hoverbg hover:text-ink-primary hover:border-brand-soft-border'
                        }`}
                      >
                        <span className="font-mono font-bold text-accent">
                          {String.fromCharCode(65 + optIdx)}.
                        </span>
                        <span>{opt}</span>
                      </button>
                    );
                  })}
                </div>

                {fb && (
                  <div
                    className={`p-3.5 rounded-[10px] text-xs border flex items-start gap-2 ${
                      fb.is_correct
                        ? 'bg-status-success-bg border-status-success-border text-status-success-text'
                        : 'bg-status-danger-bg border-status-danger-border text-status-danger-text'
                    }`}
                  >
                    {fb.is_correct ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
                    ) : (
                      <XCircle className="h-4 w-4 shrink-0 mt-0.5" />
                    )}
                    <div className="space-y-1">
                      {!fb.is_correct && (
                        <p>
                          <strong>Correct answer:</strong> {fb.correct_answer}
                        </p>
                      )}
                      {fb.explanation && <p className="text-ink-primary">{fb.explanation}</p>}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {!result && (
          <div className="flex items-center justify-between pt-4 border-t border-line">
            <span className="text-xs text-ink-secondary">
              Answered {answeredCount} of {assessment.questions.length}
            </span>
            <Button
              variant="primary"
              onClick={handleSubmit}
              isLoading={isSubmitting}
              disabled={answeredCount < assessment.questions.length}
              icon={<Send className="h-4 w-4" />}
            >
              Submit Assessment
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
};
