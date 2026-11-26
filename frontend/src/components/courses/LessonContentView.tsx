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
  Clock
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
  const formattedPages = lesson.page_start && lesson.page_end
    ? (lesson.page_start === lesson.page_end ? `PDF Page ${lesson.page_start}` : `PDF Pages ${lesson.page_start}–${lesson.page_end}`)
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
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-white transition-colors group"
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
      <Card className="bg-slate-900/90 border-slate-800 p-6 md:p-10 space-y-8 shadow-2xl">
        {/* Lesson Header */}
        <div className="space-y-4 pb-6 border-b border-slate-800">
          <div className="flex flex-wrap items-center justify-between gap-3">
            {/* Module Breadcrumb Pill */}
            <div className="flex flex-wrap items-center gap-2 text-xs">
              {chapterTitle && (
                <span className="px-2.5 py-1 rounded-md bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 font-medium">
                  {chapterTitle}
                </span>
              )}
              {topicTitle && (
                <span className="text-slate-400">
                  / <span className="text-slate-300">{topicTitle}</span>
                </span>
              )}
            </div>

            {/* Status & Mark Complete Button */}
            <div className="flex items-center gap-3">
              {lesson.is_completed ? (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Completed
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-slate-800 border border-slate-700 text-slate-400">
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
                    <BookmarkCheck className="h-4 w-4 text-emerald-400" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4" />
                  )
                }
              >
                {lesson.is_completed ? 'Mark Incomplete' : 'Mark as Complete'}
              </Button>
            </div>
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight leading-tight">
            {lesson.title}
          </h1>

          {/* Source Grounding & Duration Pills */}
          <div className="flex flex-wrap items-center gap-2">
            {(formattedPages || printedPageStr) && (
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-950/40 border border-indigo-500/20 text-indigo-300 text-xs">
                <FileText className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
                <span>
                  <strong>Source:</strong>{' '}
                  {printedPageStr ? `${printedPageStr} (${formattedPages})` : formattedPages}
                </span>
              </div>
            )}
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700 text-slate-300 text-xs">
              <Clock className="h-3.5 w-3.5 text-indigo-400" />
              <span>~{lesson.estimated_minutes || 10} min</span>
            </div>
            {difficultyLevel && (
              <span className="px-3 py-1 rounded-full bg-purple-500/15 border border-purple-500/30 text-purple-300 text-xs font-semibold capitalize">
                {difficultyLevel}
              </span>
            )}
            {lesson.structured_sections?.grounding_map && (
              <button
                type="button"
                onClick={() => setShowGrounding((prev) => !prev)}
                className="px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/25 text-emerald-300 text-xs font-semibold hover:bg-emerald-500/20 transition-colors"
              >
                {showGrounding ? 'Hide Source Mapping' : 'Source Grounding Map'}
              </button>
            )}
          </div>

          {/* Source Grounding & Category Legend */}
          {showGrounding && lesson.structured_sections?.grounding_map && (
            <div className="p-4 rounded-xl bg-slate-950/80 border border-emerald-500/20 space-y-3 text-xs">
              <div className="flex flex-wrap gap-2">
                <span className="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 font-semibold">[SOURCE-BASED] Directly supported by document</span>
                <span className="px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-300 font-semibold">[SUPPLEMENTARY EXPLANATION] Added examples/walkthroughs</span>
                <span className="px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 font-semibold">[ADVANCED EXTENSION] Beyond source scope</span>
              </div>
              {lesson.structured_sections.grounding_map.chunks && lesson.structured_sections.grounding_map.chunks.length > 0 && (
                <div className="space-y-1.5 pt-1 border-t border-slate-800">
                  <p className="text-slate-400 font-semibold">Retrieved Source Chunks:</p>
                  {lesson.structured_sections.grounding_map.chunks.map((ch, idx) => (
                    <div key={idx} className="p-2 rounded bg-slate-900/90 border border-slate-800 text-slate-300">
                      <span className="text-indigo-300 font-mono mr-2">
                        [Book p.{ch.printed_page || ch.page_number} / PDF p.{ch.page_number}]
                      </span>
                      <span className="text-slate-400">{ch.preview}…</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Executive Summary Callout (if available) */}
        {lesson.summary && (
          <div className="p-4 md:p-5 rounded-xl bg-slate-950/60 border border-slate-800 text-slate-300 text-sm leading-relaxed space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-indigo-400 uppercase tracking-wider">
              <Sparkles className="h-3.5 w-3.5" />
              <span>Lesson Overview</span>
            </div>
            <p className="text-slate-300">{lesson.summary}</p>
          </div>
        )}

        {/* Failed Generation Banner */}
        {lesson.generation_status === 'failed' && (
          <div className="p-5 md:p-6 rounded-xl bg-red-950/30 border border-red-500/30 text-red-200 space-y-3">
            <div className="flex items-center gap-2 font-bold text-red-400">
              <AlertCircle className="h-5 w-5 shrink-0" />
              <span>Lesson Generation Incomplete</span>
            </div>
            <p className="text-sm text-red-300/90 leading-relaxed">
              {lesson.generation_error || "The AI model encountered an issue while generating this lesson."}
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

        {/* Generating / Queued In-Progress Pipeline Stepper */}
        {(lesson.generation_status === 'generating' || lesson.generation_status === 'queued') ? (
          <div className="py-10 px-4 max-w-xl mx-auto space-y-5">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <Spinner size="md" className="text-indigo-400 shrink-0" />
                <div>
                  <p className="text-sm font-bold text-white">
                    {jobStatus?.current_stage || (lesson.generation_status === 'queued' ? 'Preparing source material' : 'Generating lesson content')}
                  </p>
                  <p className="text-xs text-slate-400">
                    Elapsed: <span className="font-mono text-indigo-300">{Math.round(jobStatus?.elapsed_seconds || 0)}s</span>
                    {jobStatus?.retry_count ? ` · Retry #${jobStatus.retry_count}` : ''}
                  </p>
                </div>
              </div>
              {onCancelGeneration && (
                <Button size="sm" variant="ghost" onClick={onCancelGeneration}>
                  Cancel
                </Button>
              )}
            </div>

            <div className="space-y-2 rounded-xl bg-slate-950/70 border border-slate-800 p-4 text-xs">
              {[
                { key: 'QUEUED', label: 'Preparing source material' },
                { key: 'RETRIEVING_SOURCE', label: 'Retrieving relevant sections' },
                { key: 'GENERATING', label: 'Generating lesson content' },
                { key: 'VALIDATING', label: 'Validating technical explanations & exercises' },
                { key: 'COMPLETED', label: 'Saving lesson' },
              ].map((st, idx) => {
                const order = ['QUEUED', 'RETRIEVING_SOURCE', 'GENERATING', 'VALIDATING', 'SAVING', 'COMPLETED'];
                const curStatus = jobStatus?.status || (lesson.generation_status === 'queued' ? 'QUEUED' : 'GENERATING');
                const curIdx = Math.max(0, order.indexOf(curStatus));
                const done = idx < curIdx;
                const active = idx === curIdx;
                return (
                  <div key={st.key} className="flex items-center gap-2.5">
                    <span
                      className={`h-2 w-2 rounded-full shrink-0 ${
                        done ? 'bg-emerald-400' : active ? 'bg-indigo-400 animate-pulse' : 'bg-slate-700'
                      }`}
                    />
                    <span className={done ? 'text-emerald-300' : active ? 'text-white font-semibold' : 'text-slate-500'}>
                      {st.label}
                    </span>
                  </div>
                );
              })}
            </div>

            <p className="text-xs text-slate-400 text-center">
              You can navigate to other ready lessons while this lesson synthesizes in the background.
            </p>
          </div>
        ) : (
          <>
            {/* Rich Lesson Body via MarkdownRenderer */}
            <div className="py-2">
              <MarkdownRenderer content={lesson.content} />
            </div>

            {/* Key Takeaways Section */}
            {lesson.key_takeaways && lesson.key_takeaways.length > 0 && (
              <div className="mt-8 p-5 md:p-6 rounded-2xl bg-gradient-to-br from-slate-950 to-indigo-950/30 border border-indigo-500/20 space-y-3.5 shadow-lg">
                <h3 className="text-sm md:text-base font-bold text-white flex items-center gap-2">
                  <ListChecks className="h-5 w-5 text-emerald-400" />
                  Key Takeaways
                </h3>
                <ul className="space-y-2 text-xs md:text-sm text-slate-300">
                  {lesson.key_takeaways.map((takeaway, idx) => (
                    <li key={idx} className="flex items-start gap-2.5">
                      <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-indigo-500/20 text-[10px] text-indigo-300 font-bold mt-0.5">
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
                <InteractiveConceptDeck cards={lesson.structured_sections.concept_cards} />
              )}

            {/* Interactive Matching Exercise */}
            {lesson.structured_sections?.matching_exercise && (
              <InteractiveMatchingCard matching={lesson.structured_sections.matching_exercise} />
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
        <div className="pt-8 border-t border-slate-800 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <Button
              variant={lesson.is_completed ? 'secondary' : 'primary'}
              onClick={onToggleComplete}
              isLoading={isTogglingComplete}
              icon={<CheckCircle2 className="h-4 w-4" />}
              className="w-full sm:w-auto"
            >
              {lesson.is_completed ? 'Mark as Incomplete' : 'Mark Lesson as Complete'}
            </Button>

            <span className="text-xs text-slate-400 text-center sm:text-right">
              {lesson.is_completed
                ? '✓ Completed. Ready for the next lesson!'
                : 'Click when you have finished studying this lesson.'}
            </span>
          </div>

          {/* Prev / Next Lesson Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            {/* Previous Lesson Card */}
            {prevLesson ? (
              <button
                type="button"
                onClick={() => onSelectLesson(prevLesson.id)}
                className="p-4 rounded-xl border border-slate-800 bg-slate-950/40 hover:bg-slate-800/60 hover:border-slate-700 transition-all text-left flex items-center gap-3 group"
              >
                <div className="h-9 w-9 rounded-lg bg-slate-800 flex items-center justify-center text-slate-400 group-hover:text-white group-hover:bg-indigo-600 transition-colors shrink-0">
                  <ChevronLeft className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                    Previous Lesson
                  </p>
                  <p className="text-xs md:text-sm font-semibold text-slate-200 group-hover:text-white truncate mt-0.5">
                    {prevLesson.title}
                  </p>
                </div>
              </button>
            ) : (
              <div className="p-4 rounded-xl border border-dashed border-slate-800/60 text-slate-500 text-xs flex items-center justify-center">
                First lesson in course
              </div>
            )}

            {/* Next Lesson Card */}
            {nextLesson ? (
              <button
                type="button"
                onClick={() => onSelectLesson(nextLesson.id)}
                className="p-4 rounded-xl border border-indigo-500/30 bg-indigo-950/20 hover:bg-indigo-900/30 hover:border-indigo-500/50 transition-all text-right flex items-center justify-end gap-3 group"
              >
                <div className="min-w-0">
                  <p className="text-[10px] font-semibold text-indigo-400 uppercase tracking-wider">
                    Next Lesson
                  </p>
                  <p className="text-xs md:text-sm font-semibold text-slate-200 group-hover:text-white truncate mt-0.5">
                    {nextLesson.title}
                  </p>
                </div>
                <div className="h-9 w-9 rounded-lg bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-indigo-300 group-hover:text-white group-hover:bg-indigo-600 transition-colors shrink-0">
                  <ChevronRight className="h-5 w-5" />
                </div>
              </button>
            ) : (
              <button
                type="button"
                onClick={onSelectOverview}
                className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-950/20 hover:bg-emerald-900/30 text-right flex items-center justify-end gap-3 group"
              >
                <div>
                  <p className="text-[10px] font-semibold text-emerald-400 uppercase tracking-wider">
                    Finished Syllabus
                  </p>
                  <p className="text-xs md:text-sm font-semibold text-emerald-300 mt-0.5">
                    Back to Course Overview
                  </p>
                </div>
                <div className="h-9 w-9 rounded-lg bg-emerald-600/20 flex items-center justify-center text-emerald-400 shrink-0">
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
