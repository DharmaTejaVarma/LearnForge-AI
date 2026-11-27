import React from 'react';
import { Course } from '../../services/courseService';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import {
  BookOpen,
  Clock,
  CheckCircle2,
  PlayCircle,
  Target,
  Layers,
  ChevronRight,
  GraduationCap,
  Award,
} from 'lucide-react';

interface CourseOverviewViewProps {
  course: Course;
  onStartOrResume: (lessonId: number) => void;
  onOpenModuleAssessment?: (chapterId: number) => void;
  onOpenFinalAssessment?: () => void;
}

export const CourseOverviewView: React.FC<CourseOverviewViewProps> = ({
  course,
  onStartOrResume,
  onOpenModuleAssessment,
  onOpenFinalAssessment,
}) => {
  let totalLessons = 0;
  let completedLessons = 0;
  let firstIncompleteLessonId: number | null = null;
  let firstLessonId: number | null = null;

  course.chapters?.forEach((chap) => {
    chap.topics.forEach((topic) => {
      if (topic.lesson) {
        totalLessons += 1;
        if (!firstLessonId) {
          firstLessonId = topic.lesson.id;
        }
        if (topic.lesson.is_completed) {
          completedLessons += 1;
        } else if (!firstIncompleteLessonId) {
          firstIncompleteLessonId = topic.lesson.id;
        }
      }
    });
  });

  const targetLessonId = firstIncompleteLessonId || firstLessonId;
  const progressPercent = totalLessons > 0 ? Math.round((completedLessons / totalLessons) * 100) : 0;
  const isStarted = completedLessons > 0;
  const isFinished = totalLessons > 0 && completedLessons === totalLessons;

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Hero Course Banner (Dark Gradient) */}
      <div className="relative overflow-hidden rounded-[12px] lf-gradient-dark border border-indigo-400/20 p-6 md:p-10 shadow-card text-white">
        <div className="relative z-10 max-w-3xl space-y-4">
          <div className="flex flex-wrap items-center gap-2.5">
            {course.category && (
              <span className="px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider bg-white/15 text-violet-200 border border-white/20">
                {course.category}
              </span>
            )}
            <span className="px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider bg-indigo-500/30 text-indigo-100 border border-indigo-300/30">
              {course.difficulty_level || 'Modular Course'}
            </span>
            <span className="px-3 py-1 rounded-full text-xs font-medium bg-white/10 text-indigo-100 border border-white/15 flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-violet-300" />
              ~{course.estimated_duration_hours || 4} Hours Total
            </span>
            {isFinished && (
              <span className="px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/25 text-emerald-200 border border-emerald-400/30 flex items-center gap-1.5">
                <Award className="h-3.5 w-3.5" />
                Course Completed!
              </span>
            )}
          </div>

          <h1 className="text-[28px] md:text-[32px] font-bold text-white tracking-tight leading-[1.2]">
            {course.title}
          </h1>

          <p className="text-indigo-100/90 text-[15px] md:text-base leading-relaxed">
            {course.description}
          </p>

          <div className="pt-3 flex flex-wrap items-center gap-4">
            {targetLessonId ? (
              <Button
                variant="primary"
                size="lg"
                onClick={() => onStartOrResume(targetLessonId)}
                icon={<PlayCircle className="h-5 w-5" />}
              >
                {isStarted && !isFinished
                  ? 'Continue Learning'
                  : isFinished
                  ? 'Review Course from Start'
                  : 'Start Learning'}
              </Button>
            ) : null}

            <div className="text-xs text-indigo-200 font-medium">
              {completedLessons} of {totalLessons} lessons finished ({progressPercent}%)
            </div>
          </div>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="p-4 flex items-center gap-3.5">
          <div className="h-11 w-11 rounded-[10px] bg-brand-soft border border-brand-soft-border flex items-center justify-center text-brand shrink-0">
            <Layers className="h-5 w-5" />
          </div>
          <div>
            <p className="lf-label-sm">Modules</p>
            <p className="text-xl font-bold text-ink-primary mt-0.5">
              {course.chapters?.length || 0}
            </p>
          </div>
        </Card>

        <Card className="p-4 flex items-center gap-3.5">
          <div className="h-11 w-11 rounded-[10px] bg-accent-soft border border-accent-soft-border flex items-center justify-center text-accent shrink-0">
            <BookOpen className="h-5 w-5" />
          </div>
          <div>
            <p className="lf-label-sm">Lessons</p>
            <p className="text-xl font-bold text-ink-primary mt-0.5">{totalLessons}</p>
          </div>
        </Card>

        <Card className="p-4 flex items-center gap-3.5">
          <div className="h-11 w-11 rounded-[10px] bg-brand-soft border border-brand-soft-border flex items-center justify-center text-brand shrink-0">
            <Clock className="h-5 w-5" />
          </div>
          <div>
            <p className="lf-label-sm">Est. Duration</p>
            <p className="text-xl font-bold text-ink-primary mt-0.5">
              ~{course.estimated_duration_hours || 4}h
            </p>
          </div>
        </Card>

        <Card className="p-4 flex items-center gap-3.5">
          <div className="h-11 w-11 rounded-[10px] bg-status-success-bg border border-status-success-border flex items-center justify-center text-status-success-text shrink-0">
            <CheckCircle2 className="h-5 w-5" />
          </div>
          <div>
            <p className="lf-label-sm">Completion</p>
            <p className="text-xl font-bold text-ink-primary mt-0.5">{progressPercent}%</p>
          </div>
        </Card>
      </div>

      {/* Learning Objectives */}
      {course.learning_objectives && course.learning_objectives.length > 0 && (
        <Card className="p-6 md:p-8 space-y-4">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-[10px] bg-brand-soft border border-brand-soft-border flex items-center justify-center text-brand">
              <Target className="h-4 w-4" />
            </div>
            <div>
              <h2 className="lf-heading-card">Learning Objectives</h2>
              <p className="text-xs text-ink-secondary">Key competencies and knowledge outcomes of this course</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
            {course.learning_objectives.map((obj, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-[12px] bg-subtle border border-line flex items-start gap-3 hover:border-brand-soft-border transition-colors"
              >
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-soft border border-brand-soft-border text-[11px] font-bold text-brand">
                  {idx + 1}
                </span>
                <p className="text-xs md:text-sm text-ink-primary leading-relaxed">{obj}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Comprehensive Course Syllabus */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GraduationCap className="h-5 w-5 text-accent" />
            <h2 className="lf-heading-section">Detailed Syllabus</h2>
          </div>
          <span className="text-xs text-ink-secondary">
            {course.chapters?.length || 0} Modules • {totalLessons} Lessons
          </span>
        </div>

        <div className="space-y-4">
          {course.chapters?.map((chap, cIdx) => (
            <Card
              key={chap.id}
              className="p-5 md:p-6 hover:border-brand-soft-border transition-all space-y-4"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-line">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-brand bg-brand-soft px-2.5 py-0.5 rounded-full border border-brand-soft-border">
                      Module {cIdx + 1}
                    </span>
                    {chap.printed_page_start && (
                      <span className="text-[11px] text-ink-secondary font-mono">
                        Book p. {chap.printed_page_start}
                        {chap.printed_page_end && chap.printed_page_end !== chap.printed_page_start
                          ? `–${chap.printed_page_end}`
                          : ''}
                      </span>
                    )}
                  </div>
                  <h3 className="lf-heading-card mt-1.5">{chap.title}</h3>
                  {chap.description && (
                    <p className="text-xs text-ink-secondary mt-1">{chap.description}</p>
                  )}
                </div>
                <div className="flex items-center gap-2.5 self-start sm:self-center">
                  <span className="text-xs text-ink-secondary font-mono">
                    {chap.topics.length} lessons
                  </span>
                  {onOpenModuleAssessment && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onOpenModuleAssessment(chap.id)}
                    >
                      Module Quiz
                    </Button>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {chap.topics.map((topic, tIdx) => {
                  const lesson = topic.lesson;
                  const isDone = lesson?.is_completed;

                  return (
                    <div
                      key={topic.id}
                      onClick={() => lesson && onStartOrResume(lesson.id)}
                      className={`p-3 rounded-[10px] border transition-all flex items-center justify-between cursor-pointer ${
                        isDone
                          ? 'bg-status-success-bg border-status-success-border hover:opacity-90'
                          : 'bg-subtle border-line hover:bg-hoverbg hover:border-brand-soft-border'
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0 pr-2">
                        {isDone ? (
                          <CheckCircle2 className="h-4 w-4 text-status-success-text shrink-0" />
                        ) : (
                          <div className="h-4 w-4 rounded-full border border-line-strong flex items-center justify-center shrink-0">
                            <span className="text-[9px] text-ink-secondary font-mono">{tIdx + 1}</span>
                          </div>
                        )}
                        <span className="text-xs font-medium text-ink-primary truncate">
                          {lesson?.title || topic.title}
                        </span>
                      </div>

                      <ChevronRight className="h-4 w-4 text-ink-secondary shrink-0" />
                    </div>
                  );
                })}
              </div>
            </Card>
          ))}
        </div>

        {/* Final Mastery Exam Card */}
        {onOpenFinalAssessment && totalLessons > 0 && (
          <div className="rounded-[12px] lf-gradient-dark border border-indigo-400/20 p-6 shadow-card text-white flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-violet-300">
                <Award className="h-4 w-4" />
                <span>Comprehensive Capstone</span>
              </div>
              <h3 className="text-lg font-semibold text-white">Final Course Assessment</h3>
              <p className="text-xs text-indigo-100/90">
                Test mastery across all {course.chapters?.length || 0} modules and identify any weak concepts to revise.
              </p>
            </div>
            <Button variant="primary" onClick={onOpenFinalAssessment} icon={<Award className="h-4 w-4" />}>
              Take Final Exam
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};
