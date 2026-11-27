import React from 'react';
import { Lesson, LessonExercise, LessonJobStatus } from '../../services/courseService';
import { MarkdownRenderer } from './MarkdownRenderer';
import { InteractiveConceptDeck } from './InteractiveConceptDeck';
import { InteractiveMatchingCard } from './InteractiveMatchingCard';
import { InteractiveArchitectureDiagram } from './InteractiveArchitectureDiagram';
import { InteractiveSimulator } from './InteractiveSimulator';
import { ProjectMilestoneCard } from './ProjectMilestoneCard';
import { LessonExercisesPanel } from './LessonExercisesPanel';
import { Button } from '../common/Button';
import { Card } from '../common/Card';
import { Spinner } from '../common/Spinner';
import { formatSourcePages } from '../../utils/formatters';
import {
  CheckCircle2,
  Circle,
  FileText,
  ListChecks,
  ChevronLeft,
  ChevronRight,
  ArrowLeft,
  Award,
  BookmarkCheck,
  Sparkles,
  AlertCircle,
  RotateCw,
  Clock,
} from 'lucide-react';

interface LessonNavInfo {
  id: number;
  title: string;
}

interface LessonContentViewProps {
  lesson: Lesson;
  chapterTitle?: string;
  topicTitle?: string;
  difficultyLevel?: string;
  prevLesson: LessonNavInfo | null;
  nextLesson: LessonNavInfo | null;
  onToggleComplete: () => Promise<void>;
  isTogglingComplete: boolean;
  onSelectLesson: (id: number) => void;
  onSelectOverview: () => void;
  onRegenerate?: () => Promise<void>;
  isRegenerating?: boolean;
  jobStatus?: LessonJobStatus | null;
  onCancelGeneration?: () => Promise<void>;
  onAskTutorHint?: (exercise: LessonExercise) => void;
}

export const LessonContentView: React.FC<LessonContentViewProps> = ({
  lesson,
  chapterTitle,
  topicTitle,
  difficultyLevel,
  prevLesson,
  nextLesson,
  onToggleComplete,
  isTogglingComplete,
  onSelectLesson,
  onSelectOverview,
  onRegenerate,
  isRegenerating = false,
  jobStatus = null,
  onCancelGeneration,
  onAskTutorHint,
}) => {
  const [showGrounding, setShowGrounding] = React.useState(false);
  const formattedPages =
    lesson.page_start && lesson.page_end
      ? lesson.page_start === lesson.page_end
        ? `PDF Page ${lesson.page_start}`
        : `PDF Pages ${lesson.page_start}–${lesson.page_end}`
      : formatSourcePages(lesson.source_pages);

  const printedPageStr =
    lesson.printed_pages && lesson.printed_pages.length > 0
      ? lesson.printed_pages.length > 1
        ? `Book p. ${lesson.printed_pages[0]}–${lesson.printed_pages[lesson.printed_pages.length - 1]}`
        : `Book p. ${lesson.printed_pages[0]}`
      : null;

  return (
    <div className="space-y-6 max-w-5xl mx-auto animate-fadeIn">
      {/* Top Breadcrumb & Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-2">
        <button
          onClick={onSelectOverview}
          type="button"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-ink-secondary hover:text-ink-primary transition-colors group"
        >
          <ArrowLeft className="h-3.5 w-3.5 group-hover:-translate-x-0.5 transition-transform" />
          <span>Curriculum Overview</span>
        </button>

        {/* Quick Header Nav Buttons */}
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="ghost"
            disabled={!prevLesson}
            onClick={() => prevLesson && onSelectLesson(prevLesson.id)}
            icon={<ChevronLeft className="h-4 w-4" />}
            title={prevLesson ? `Previous: ${prevLesson.title}` : 'No previous lesson'}
          >
            <span className="hidden sm:inline">Previous</span>
          </Button>

          <Button
            size="sm"
            variant="ghost"
            disabled={!nextLesson}
            onClick={() => nextLesson && onSelectLesson(nextLesson.id)}
            icon={<ChevronRight className="h-4 w-4" />}
            title={nextLesson ? `Next: ${nextLesson.title}` : 'Last lesson'}
          >
            <span className="hidden sm:inline">Next</span>
          </Button>
        </div>
      </div>

      {/* Main Lesson Card */}
      <Card className="p-6 md:p-10 space-y-8">
        {/* Lesson Header */}
        <div className="space-y-4 pb-6 border-b border-line">
          <div className="flex flex-wrap items-center justify-between gap-3">
            {/* Module Breadcrumb Pill */}
            <div className="flex flex-wrap items-center gap-2 text-xs">
              {chapterTitle && (
                <span className="px-2.5 py-1 rounded-[10px] bg-brand-soft border border-brand-soft-border text-brand font-medium">
                  {chapterTitle}
                </span>
              )}
              {topicTitle && (
                <span className="text-ink-secondary">
                  / <span className="text-ink-primary font-medium">{topicTitle}</span>
                </span>
              )}
            </div>

            {/* Status & Mark Complete Button */}
            <div className="flex items-center gap-3">
              {lesson.is_completed ? (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-status-success-bg border border-status-success-border text-status-success-text">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Completed
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-subtle border border-line text-ink-secondary">
                  <Circle className="h-3 w-3" />
                  In Progress
                </span>
              )}

              <Button
                variant={lesson.is_completed ? 'secondary' : 'primary'}
                size="sm"
                onClick={onToggleComplete}
                isLoading={isTogglingComplete}
                icon={
                  lesson.is_completed ? (
                    <BookmarkCheck className="h-4 w-4 text-status-success-text" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4" />
                  )
                }
              >
                {lesson.is_completed ? 'Mark Incomplete' : 'Mark as Complete'}
              </Button>
            </div>
          </div>

          <h1 className="lf-heading-main">{lesson.title}</h1>

          {/* Source Grounding & Duration Pills */}
          <div className="flex flex-wrap items-center gap-2">
            {(formattedPages || printedPageStr) && (
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-soft border border-brand-soft-border text-brand text-xs">
                <FileText className="h-3.5 w-3.5 shrink-0" />
                <span>
                  <strong>Source:</strong>{' '}
                  {printedPageStr ? `${printedPageStr} (${formattedPages})` : formattedPages}
                </span>
              </div>
            )}
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-subtle border border-line text-ink-secondary text-xs">
              <Clock className="h-3.5 w-3.5 text-brand" />
              <span>~{lesson.estimated_minutes || 10} min</span>
            </div>
            {difficultyLevel && (
              <span className="px-3 py-1 rounded-full bg-accent-soft border border-accent-soft-border text-accent text-xs font-semibold capitalize">
                {difficultyLevel}
              </span>
            )}
            {lesson.structured_sections?.grounding_map && (
              <button
                type="button"
                onClick={() => setShowGrounding((prev) => !prev)}
                className="px-3 py-1 rounded-full bg-status-success-bg border border-status-success-border text-status-success-text text-xs font-semibold hover:opacity-85 transition-opacity"
              >
                {showGrounding ? 'Hide Source Mapping' : 'Source Grounding Map'}
              </button>
            )}
          </div>

          {/* Source Grounding & Category Legend */}
          {showGrounding && lesson.structured_sections?.grounding_map && (
            <div className="p-4 rounded-[12px] bg-subtle border border-line space-y-3 text-xs">
              <div className="flex flex-wrap gap-2">
                <span className="px-2 py-0.5 rounded bg-status-success-bg text-status-success-text font-semibold">
                  [SOURCE-BASED] Directly supported by document
                </span>
                <span className="px-2 py-0.5 rounded bg-brand-soft text-brand font-semibold">
                  [SUPPLEMENTARY EXPLANATION] Added examples/walkthroughs
                </span>
                <span className="px-2 py-0.5 rounded bg-status-warning-bg text-status-warning-text font-semibold">
                  [ADVANCED EXTENSION] Beyond source scope
                </span>
              </div>
              {lesson.structured_sections.grounding_map.chunks &&
                lesson.structured_sections.grounding_map.chunks.length > 0 && (
                  <div className="space-y-1.5 pt-2 border-t border-line">
                    <p className="text-ink-primary font-semibold">Retrieved Source Chunks:</p>
                    {lesson.structured_sections.grounding_map.chunks.map((ch, idx) => (
                      <div key={idx} className="p-2.5 rounded-[10px] bg-surface border border-line text-ink-primary">
                        <span className="text-brand font-mono mr-2 font-medium">
                          [Book p.{ch.printed_page || ch.page_number} / PDF p.{ch.page_number}]
                        </span>
                        <span className="text-ink-secondary">{ch.preview}…</span>
                      </div>
                    ))}
                  </div>
                )}
            </div>
          )}
        </div>

        {/* Executive Summary Callout */}
        {lesson.summary && (
          <div className="p-4 md:p-5 rounded-[12px] bg-subtle border border-line text-ink-primary text-sm leading-relaxed space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-accent uppercase tracking-wider">
              <Sparkles className="h-3.5 w-3.5" />
              <span>Lesson Overview</span>
            </div>
            <p className="text-ink-primary">{lesson.summary}</p>
          </div>
        )}

        {/* Failed Generation Banner */}
        {lesson.generation_status === 'failed' && (
          <div className="p-5 md:p-6 rounded-[12px] bg-status-danger-bg border border-status-danger-border text-status-danger-text space-y-3">
            <div className="flex items-center gap-2 font-bold">
              <AlertCircle className="h-5 w-5 shrink-0" />
              <span>Lesson Generation Incomplete</span>
            </div>
            <p className="text-sm opacity-90 leading-relaxed">
              {lesson.generation_error || 'The AI model encountered an issue while generating this lesson.'}
            </p>
            {onRegenerate && (
              <div className="pt-1">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={onRegenerate}
                  isLoading={isRegenerating}
                  icon={<RotateCw className="h-4 w-4" />}
                >
                  Regenerate Lesson
                </Button>
              </div>
            )}
          </div>
        )}

        {/* Generating / Queued In-Progress 10-Stage Pipeline Stepper */}
        {lesson.generation_status === 'generating' || lesson.generation_status === 'queued' ? (
          <div className="py-10 px-4 max-w-xl mx-auto space-y-5">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <Spinner size="md" className="shrink-0" />
                <div>
                  <p className="text-sm font-bold text-ink-primary">
                    {lesson.title}:{' '}
                    {jobStatus?.current_stage ||
                      (lesson.generation_status === 'queued'
                        ? 'Queued for synthesis'
                        : 'Generating lesson content')}
                  </p>
                  <p className="text-xs text-ink-secondary">
                    Elapsed:{' '}
                    <span className="font-mono text-brand font-medium">
                      {Math.round(jobStatus?.elapsed_seconds || 0)}s
                    </span>
                    {jobStatus?.stage_duration_ms != null && (
                      <span> · Stage: {Math.round(jobStatus.stage_duration_ms / 1000)}s</span>
                    )}
                    {jobStatus?.retry_count ? ` · Retry #${jobStatus.retry_count}` : ''}
                    {jobStatus?.generated_tokens ? ` · ${jobStatus.generated_tokens} tokens` : ''}
                  </p>
                </div>
              </div>
              {onCancelGeneration && (
                <Button size="sm" variant="ghost" onClick={onCancelGeneration}>
                  Cancel
                </Button>
              )}
            </div>

            {jobStatus?.progress_percentage != null ? (
              <div className="space-y-1">
                <div className="flex justify-between text-[11px] text-ink-secondary font-mono">
                  <span>
                    Stage {jobStatus.completed_stages ?? 0}/{jobStatus.total_stages ?? 10}
                  </span>
                  <span>{jobStatus.progress_percentage}%</span>
                </div>
                <div className="w-full h-1.5 rounded-full bg-subtle overflow-hidden">
                  <div
                    className="h-full bg-accent transition-all duration-300 rounded-full"
                    style={{ width: `${jobStatus.progress_percentage}%` }}
                  />
                </div>
              </div>
            ) : (
              <div className="space-y-1">
                <div className="flex justify-between text-[11px] text-ink-secondary font-mono">
                  <span>
                    {jobStatus?.status === 'GENERATING'
                      ? 'Streaming local LLM inference…'
                      : 'Preparing stage…'}
                  </span>
                  <span>In progress</span>
                </div>
                <div className="w-full h-1.5 rounded-full bg-subtle overflow-hidden">
                  <div className="h-full w-1/3 bg-accent animate-pulse rounded-full" />
                </div>
              </div>
            )}

            <div className="space-y-1.5 rounded-[12px] bg-subtle border border-line p-4 text-xs">
              {[
                { key: 'CHECKING_CACHE', label: '1. Checking cache' },
                { key: 'CHECKING_DOCUMENT', label: '2. Checking document readiness' },
                { key: 'RETRIEVING_SOURCE', label: '3. Retrieving source passages' },
                { key: 'PREPARING_CONTEXT', label: '4. Preparing context' },
                { key: 'GENERATING', label: '5. Generating lesson' },
                { key: 'VALIDATING', label: '6. Validating content' },
                { key: 'REPAIRING_CODE', label: '7. Repairing invalid code (if needed)' },
                { key: 'PREPARING_EXERCISES', label: '8. Preparing exercises' },
                { key: 'SAVING', label: '9. Saving lesson' },
                { key: 'COMPLETED', label: '10. Completed' },
              ].map((st, idx) => {
                const order = [
                  'CHECKING_CACHE',
                  'CHECKING_DOCUMENT',
                  'RETRIEVING_SOURCE',
                  'PREPARING_CONTEXT',
                  'GENERATING',
                  'VALIDATING',
                  'REPAIRING_CODE',
                  'PREPARING_EXERCISES',
                  'SAVING',
                  'COMPLETED',
                ];
                const curStatus =
                  jobStatus?.status ||
                  (lesson.generation_status === 'queued' ? 'CHECKING_CACHE' : 'GENERATING');
                const rawIdx = order.indexOf(curStatus);
                const curIdx = rawIdx >= 0 ? rawIdx : 0;
                const done = idx < curIdx;
                const active = idx === curIdx;
                return (
                  <div key={st.key} className="flex items-center gap-2.5">
                    <span
                      className={`h-2 w-2 rounded-full shrink-0 ${
                        done
                          ? 'bg-emerald-500'
                          : active
                          ? 'bg-accent animate-pulse'
                          : 'bg-line-strong'
                      }`}
                    />
                    <span
                      className={
                        done
                          ? 'text-status-success-text font-medium'
                          : active
                          ? 'text-ink-primary font-semibold'
                          : 'text-ink-secondary'
                      }
                    >
                      {st.label}
                    </span>
                  </div>
                );
              })}
            </div>

            <div className="flex items-center justify-between text-[11px] text-ink-secondary">
              <span>You can navigate to other ready lessons while this lesson synthesizes.</span>
              {jobStatus?.updated_at && (
                <span className="font-mono">
                  Updated {new Date(jobStatus.updated_at).toLocaleTimeString()}
                </span>
              )}
            </div>
          </div>
        ) : (
          <>
            {/* Rich Lesson Body via MarkdownRenderer */}
            <div className="py-2">
              <MarkdownRenderer content={lesson.content} />
            </div>

            {/* Key Takeaways Section */}
            {lesson.key_takeaways && lesson.key_takeaways.length > 0 && (
              <div className="mt-8 p-5 md:p-6 rounded-[12px] bg-brand-soft border border-brand-soft-border space-y-3.5">
                <h3 className="text-sm md:text-base font-bold text-ink-primary flex items-center gap-2">
                  <ListChecks className="h-5 w-5 text-brand" />
                  <span>Key Takeaways</span>
                </h3>
                <ul className="space-y-2 text-xs md:text-sm text-ink-primary">
                  {lesson.key_takeaways.map((takeaway, idx) => (
                    <li key={idx} className="flex items-start gap-2.5">
                      <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-brand text-[10px] text-white font-bold mt-0.5">
                        ✓
                      </span>
                      <span className="leading-relaxed">{takeaway}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Interactive Concept Cards */}
            {lesson.structured_sections?.concept_cards &&
              lesson.structured_sections.concept_cards.length > 0 && (
                <InteractiveConceptDeck
                  lessonId={lesson.id}
                  cards={lesson.structured_sections.concept_cards}
                />
              )}

            {/* Interactive Matching Exercise */}
            {lesson.structured_sections?.matching_exercise && (
              <InteractiveMatchingCard
                lessonId={lesson.id}
                matching={lesson.structured_sections.matching_exercise}
              />
            )}

            {/* Selectable Architecture Diagram */}
            {lesson.structured_sections?.architecture_diagram && (
              <InteractiveArchitectureDiagram
                diagram={lesson.structured_sections.architecture_diagram}
              />
            )}

            {/* Functional Concept Simulator */}
            {lesson.structured_sections?.simulator && (
              <InteractiveSimulator simulator={lesson.structured_sections.simulator} />
            )}

            {/* Continuous Practical Course Project */}
            {lesson.structured_sections?.project_step && (
              <ProjectMilestoneCard
                lessonId={lesson.id}
                projectStep={lesson.structured_sections.project_step}
              />
            )}

            {/* Interactive Grounded Exercises */}
            {lesson.exercises && lesson.exercises.length > 0 && (
              <LessonExercisesPanel
                lessonId={lesson.id}
                exercises={lesson.exercises}
                onAskTutorHint={onAskTutorHint}
              />
            )}
          </>
        )}

        {/* Bottom Actions & Navigation Bar */}
        <div className="pt-8 border-t border-line space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            {onRegenerate && (
              <Button
                variant="outline"
                size="sm"
                onClick={onRegenerate}
                isLoading={isRegenerating}
                icon={<RotateCw className="h-3.5 w-3.5" />}
                title="Regenerate lesson content while preserving your progress"
              >
                Regenerate
              </Button>
            )}
            <Button
              variant={lesson.is_completed ? 'secondary' : 'primary'}
              onClick={onToggleComplete}
              isLoading={isTogglingComplete}
              icon={<CheckCircle2 className="h-4 w-4" />}
              className="w-full sm:w-auto"
            >
              {lesson.is_completed ? 'Mark as Incomplete' : 'Mark Lesson as Complete'}
            </Button>

            <span className="text-xs text-ink-secondary text-center sm:text-right">
              {lesson.is_completed
                ? '✓ Completed. Ready for the next lesson!'
                : 'Click when you have finished studying this lesson.'}
            </span>
          </div>

          {/* Prev / Next Lesson Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            {prevLesson ? (
              <button
                type="button"
                onClick={() => onSelectLesson(prevLesson.id)}
                className="p-4 rounded-[12px] border border-line bg-subtle hover:bg-hoverbg hover:border-brand-soft-border transition-all text-left flex items-center gap-3 group"
              >
                <div className="h-9 w-9 rounded-[10px] bg-surface border border-line flex items-center justify-center text-ink-secondary group-hover:text-white group-hover:bg-brand group-hover:border-brand transition-colors shrink-0">
                  <ChevronLeft className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <p className="text-[10px] font-semibold text-ink-secondary uppercase tracking-wider">
                    Previous Lesson
                  </p>
                  <p className="text-xs md:text-sm font-semibold text-ink-primary group-hover:text-brand truncate mt-0.5">
                    {prevLesson.title}
                  </p>
                </div>
              </button>
            ) : (
              <div className="p-4 rounded-[12px] border border-dashed border-line text-ink-secondary text-xs flex items-center justify-center">
                First lesson in course
              </div>
            )}

            {nextLesson ? (
              <button
                type="button"
                onClick={() => onSelectLesson(nextLesson.id)}
                className="p-4 rounded-[12px] border border-brand-soft-border bg-brand-soft hover:bg-hoverbg-strong transition-all text-right flex items-center justify-end gap-3 group"
              >
                <div className="min-w-0">
                  <p className="text-[10px] font-semibold text-accent uppercase tracking-wider">
                    Next Lesson
                  </p>
                  <p className="text-xs md:text-sm font-semibold text-ink-primary truncate mt-0.5">
                    {nextLesson.title}
                  </p>
                </div>
                <div className="h-9 w-9 rounded-[10px] bg-brand flex items-center justify-center text-white group-hover:bg-brand-hover transition-colors shrink-0">
                  <ChevronRight className="h-5 w-5" />
                </div>
              </button>
            ) : (
              <button
                type="button"
                onClick={onSelectOverview}
                className="p-4 rounded-[12px] border border-status-success-border bg-status-success-bg hover:opacity-90 text-right flex items-center justify-end gap-3 group transition-opacity"
              >
                <div>
                  <p className="text-[10px] font-semibold text-status-success-text uppercase tracking-wider">
                    Finished Syllabus
                  </p>
                  <p className="text-xs md:text-sm font-semibold text-status-success-text mt-0.5">
                    Back to Course Overview
                  </p>
                </div>
                <div className="h-9 w-9 rounded-[10px] bg-surface border border-status-success-border flex items-center justify-center text-status-success-text shrink-0">
                  <Award className="h-5 w-5" />
                </div>
              </button>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
};
