import React from 'react';
import { Course, CourseGenerationProgress } from '../../services/courseService';
import {
  CheckCircle2,
  Circle,
  ChevronDown,
  ChevronRight,
  GraduationCap,
  Sparkles,
  BarChart2,
  X,
  Loader2,
  Pause,
  Play,
  RotateCw,
} from 'lucide-react';

interface CourseCurriculumSidebarProps {
  course: Course;
  activeLessonId: number | null;
  isOverviewMode: boolean;
  activeAssessmentChapterId?: number | null;
  isFinalAssessmentMode?: boolean;
  onSelectLesson: (lessonId: number) => void;
  onSelectOverview: () => void;
  onSelectModuleAssessment?: (chapterId: number) => void;
  onSelectFinalAssessment?: () => void;
  collapsedChapters: Record<number, boolean>;
  onToggleChapter: (chapterId: number) => void;
  isOpenMobile: boolean;
  onCloseMobile: () => void;
  hideOnDesktop?: boolean;
  generationProgress?: CourseGenerationProgress | null;
  onTogglePrefetch?: () => void;
  onRetryFailed?: () => void;
  onCancelActiveJob?: (lessonId: number) => void;
}

export const CourseCurriculumSidebar: React.FC<CourseCurriculumSidebarProps> = ({
  course,
  activeLessonId,
  isOverviewMode,
  activeAssessmentChapterId = null,
  isFinalAssessmentMode = false,
  onSelectLesson,
  onSelectOverview,
  onSelectModuleAssessment,
  onSelectFinalAssessment,
  collapsedChapters,
  onToggleChapter,
  isOpenMobile,
  onCloseMobile,
  hideOnDesktop = false,
  generationProgress = null,
  onTogglePrefetch,
  onRetryFailed,
  onCancelActiveJob,
}) => {
  let totalLessons = 0;
  let completedLessons = 0;
  let readyLessons = 0;
  let queuedLessons = 0;
  let generatingLessons = 0;
  let failedLessons = 0;

  course.chapters?.forEach((chap) => {
    chap.topics.forEach((topic) => {
      if (topic.lesson) {
        totalLessons += 1;
        if (topic.lesson.is_completed) completedLessons += 1;
        const st = topic.lesson.generation_status;
        if (st === 'ready') readyLessons += 1;
        else if (st === 'generating') generatingLessons += 1;
        else if (st === 'failed') failedLessons += 1;
        else queuedLessons += 1;
      }
    });
  });

  const progressPercent = totalLessons > 0 ? Math.round((completedLessons / totalLessons) * 100) : 0;

  const sidebarContent = (
    <div className="flex flex-col h-full bg-sidebar border-r border-sidebar-border text-sidebar-text select-none">
      {/* Header & Course Progress */}
      <div className="p-4 border-b border-sidebar-border space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GraduationCap className="h-5 w-5 text-violet-300" />
            <h2 className="text-sm font-bold text-sidebar-text tracking-tight uppercase">
              Course Curriculum
            </h2>
          </div>
          <button
            onClick={onCloseMobile}
            className="lg:hidden p-1.5 rounded-[10px] text-sidebar-muted hover:text-sidebar-text hover:bg-sidebar-hover transition-colors"
            aria-label="Close curriculum sidebar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Course Overview Link Button */}
        <button
          onClick={() => {
            onSelectOverview();
            onCloseMobile();
          }}
          className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-[10px] text-xs font-semibold transition-all ${
            isOverviewMode
              ? 'bg-sidebar-active text-white shadow-sm'
              : 'bg-sidebar-surface hover:bg-sidebar-hover text-sidebar-muted hover:text-sidebar-text border border-sidebar-border'
          }`}
        >
          <BarChart2 className="h-4 w-4 shrink-0" />
          <span className="truncate">Course Overview &amp; Syllabus</span>
        </button>

        {/* Progress Bar Widget */}
        <div className="p-3 rounded-[12px] bg-sidebar-surface border border-sidebar-border space-y-1.5">
          <div className="flex items-center justify-between text-[11px] text-sidebar-muted font-medium">
            <span>Overall Progress</span>
            <span className="text-violet-300 font-semibold">{progressPercent}%</span>
          </div>
          <div className="w-full h-1.5 rounded-full bg-white/10 overflow-hidden">
            <div
              className="h-full lf-gradient-highlight transition-all duration-300 rounded-full"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <div className="text-[10px] text-sidebar-muted/85 text-right">
            {completedLessons} of {totalLessons} lessons completed
          </div>

          {/* Compact Course Generation Progress Dashboard */}
          <div className="pt-2 border-t border-sidebar-border space-y-1.5">
            <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-sidebar-muted">
              <span>Course Generation</span>
              {onTogglePrefetch && (
                <button
                  type="button"
                  onClick={onTogglePrefetch}
                  className="inline-flex items-center gap-1 text-[10px] font-medium text-violet-300 hover:text-white transition-colors"
                >
                  {generationProgress?.prefetch_paused ? (
                    <>
                      <Play className="h-2.5 w-2.5" /> Resume Prefetch
                    </>
                  ) : (
                    <>
                      <Pause className="h-2.5 w-2.5" /> Pause Prefetch
                    </>
                  )}
                </button>
              )}
            </div>

            <div className="flex items-center justify-between text-[10px] text-sidebar-muted">
              <span>Curriculum</span>
              <span className="font-mono text-emerald-300">
                {generationProgress?.total_lessons ?? totalLessons}/{generationProgress?.total_lessons ?? totalLessons} ready ({generationProgress?.curriculum_percentage ?? 100}%)
              </span>
            </div>

            <div className="flex items-center justify-between text-[10px] text-sidebar-muted">
              <span>Lesson Content</span>
              <span className="font-mono text-indigo-200">
                {generationProgress?.ready_lessons ?? readyLessons}/{generationProgress?.total_lessons ?? totalLessons} ready ({generationProgress?.content_readiness_percentage ?? (totalLessons > 0 ? Math.round((readyLessons / totalLessons) * 10000) / 100 : 0)}%)
              </span>
            </div>

            <div className="w-full h-1 rounded-full bg-white/10 overflow-hidden">
              <div
                className="h-full bg-emerald-400 transition-all duration-300 rounded-full"
                style={{
                  width: `${generationProgress?.content_readiness_percentage ?? (totalLessons > 0 ? (readyLessons / totalLessons) * 100 : 0)}%`,
                }}
              />
            </div>

            <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-[10px] text-sidebar-muted font-mono">
              <span>{generationProgress?.queued_lessons ?? queuedLessons} queued</span>
              <span>{generationProgress?.generating_lessons ?? generatingLessons} generating</span>
              {(generationProgress?.failed_lessons ?? failedLessons) > 0 && (
                <span className="text-rose-300">{generationProgress?.failed_lessons ?? failedLessons} failed</span>
              )}
            </div>

            {generationProgress?.active_lesson_title && (
              <div className="p-2 rounded-[10px] bg-white/10 border border-sidebar-border space-y-1 text-[10px]">
                <div className="flex items-center justify-between gap-1">
                  <span className="text-violet-200 font-semibold truncate">
                    <Loader2 className="h-2.5 w-2.5 inline animate-spin mr-1" />
                    {generationProgress.active_lesson_title}
                  </span>
                  <span className="font-mono text-sidebar-muted shrink-0">
                    {Math.round(generationProgress.active_elapsed_seconds || 0)}s
                  </span>
                </div>
                <div className="flex items-center justify-between gap-1 text-sidebar-muted">
                  <span className="truncate">{generationProgress.active_stage || 'Generating'}</span>
                  {onCancelActiveJob && generationProgress.active_lesson_id && (
                    <button
                      type="button"
                      onClick={() => onCancelActiveJob(generationProgress.active_lesson_id!)}
                      className="text-rose-300 hover:text-rose-200 shrink-0"
                    >
                      Cancel
                    </button>
                  )}
                </div>
              </div>
            )}

            {(generationProgress?.failed_lessons ?? failedLessons) > 0 && onRetryFailed && (
              <button
                type="button"
                onClick={onRetryFailed}
                className="w-full inline-flex items-center justify-center gap-1 py-1.5 rounded-[10px] bg-rose-500/20 border border-rose-400/30 text-[10px] font-semibold text-rose-200 hover:bg-rose-500/30 transition-colors"
              >
                <RotateCw className="h-3 w-3" />
                Retry Failed Lessons ({generationProgress?.failed_lessons ?? failedLessons})
              </button>
            )}

            {generationProgress?.documents_progress && generationProgress.documents_progress.length > 0 && (
              <div className="pt-1.5 border-t border-sidebar-border space-y-1">
                {generationProgress.documents_progress.slice(0, 2).map((doc, idx) => (
                  <div key={doc.document_id} className="text-[10px] text-sidebar-muted">
                    <div className="flex items-center justify-between gap-1">
                      <span className="font-semibold text-sidebar-text truncate">
                        DOC {idx + 1}: {doc.filename}
                      </span>
                      <span className="font-mono text-emerald-300 shrink-0">
                        {doc.indexing_status === 'complete' ? 'Indexed' : doc.embedding_status === 'running' ? 'Embedding' : doc.extraction_status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Chapters & Topics List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {course.chapters && course.chapters.length > 0 ? (
          course.chapters.map((chap, cIdx) => {
            const isCollapsed = !!collapsedChapters[chap.id];

            let chapTotal = 0;
            let chapCompleted = 0;
            chap.topics.forEach((t) => {
              if (t.lesson) {
                chapTotal += 1;
                if (t.lesson.is_completed) chapCompleted += 1;
              }
            });

            return (
              <div
                key={chap.id}
                className="rounded-[12px] border border-sidebar-border bg-sidebar-surface overflow-hidden transition-all"
              >
                {/* Chapter Accordion Header */}
                <button
                  type="button"
                  onClick={() => onToggleChapter(chap.id)}
                  className="w-full flex items-center justify-between p-3 text-left hover:bg-sidebar-hover transition-colors group"
                >
                  <div className="flex items-start gap-2 pr-2 min-w-0">
                    <span className="text-sidebar-muted group-hover:text-violet-300 mt-0.5 shrink-0 transition-colors">
                      {isCollapsed ? (
                        <ChevronRight className="h-4 w-4" />
                      ) : (
                        <ChevronDown className="h-4 w-4" />
                      )}
                    </span>
                    <div className="min-w-0">
                      <p className="text-[10px] font-bold text-violet-300 uppercase tracking-wider">
                        Module {cIdx + 1}
                      </p>
                      <h4 className="text-xs font-semibold text-sidebar-text truncate mt-0.5">
                        {chap.title}
                      </h4>
                    </div>
                  </div>

                  <span className="text-[10px] font-mono shrink-0 px-2 py-0.5 rounded-full bg-white/10 text-sidebar-muted border border-sidebar-border">
                    {chapCompleted}/{chapTotal}
                  </span>
                </button>

                {/* Topics & Lessons */}
                {!isCollapsed && (
                  <div className="border-t border-sidebar-border p-1.5 space-y-1">
                    {chap.topics.map((topic) => {
                      const lesson = topic.lesson;
                      if (!lesson) {
                        return (
                          <div
                            key={topic.id}
                            className="px-3 py-1.5 text-xs text-sidebar-muted italic"
                          >
                            {topic.title} (Draft)
                          </div>
                        );
                      }

                      const isSelected = !isOverviewMode && activeLessonId === lesson.id;
                      const isDone = lesson.is_completed;
                      const isPending = lesson.generation_status === 'queued' || lesson.generation_status === 'generating';
                      const isFailed = lesson.generation_status === 'failed';

                      return (
                        <button
                          key={topic.id}
                          onClick={() => {
                            onSelectLesson(lesson.id);
                            onCloseMobile();
                          }}
                          type="button"
                          className={`w-full flex items-center justify-between px-3 py-2 rounded-[10px] text-left text-xs transition-all ${
                            isSelected
                              ? 'bg-sidebar-active text-white font-medium shadow-sm'
                              : isPending
                              ? 'text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-text'
                              : 'text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-text'
                          }`}
                        >
                          <div className="flex items-center gap-2.5 min-w-0 pr-2">
                            {isDone ? (
                              <CheckCircle2
                                className={`h-4 w-4 shrink-0 ${
                                  isSelected ? 'text-white' : 'text-emerald-400'
                                }`}
                              />
                            ) : isPending ? (
                              <span className="relative shrink-0 flex h-3.5 w-3.5 items-center justify-center">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-40" />
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-violet-300" />
                              </span>
                            ) : isFailed ? (
                              <Circle className="h-3.5 w-3.5 shrink-0 text-rose-400" />
                            ) : (
                              <Circle
                                className={`h-3.5 w-3.5 shrink-0 ${
                                  isSelected ? 'text-indigo-200' : 'text-sidebar-muted/60'
                                }`}
                              />
                            )}
                            <span className="truncate leading-tight">
                              {lesson.title || topic.title}
                            </span>
                          </div>

                          {isDone && !isSelected && (
                            <span className="text-[9px] uppercase font-semibold text-emerald-300 bg-emerald-500/15 px-1.5 py-0.5 rounded shrink-0">
                              Done
                            </span>
                          )}
                          {isPending && !isSelected && (
                            <span className="text-[9px] text-violet-300 shrink-0">AI…</span>
                          )}
                        </button>
                      );
                    })}

                    {onSelectModuleAssessment && chapTotal > 0 && (
                      <button
                        type="button"
                        onClick={() => {
                          onSelectModuleAssessment(chap.id);
                          onCloseMobile();
                        }}
                        className={`w-full flex items-center justify-between px-3 py-2 rounded-[10px] text-left text-xs font-medium transition-all mt-1 border-t border-sidebar-border ${
                          activeAssessmentChapterId === chap.id
                            ? 'bg-sidebar-active text-white'
                            : 'text-violet-200 hover:bg-sidebar-hover hover:text-white'
                        }`}
                      >
                        <span className="flex items-center gap-2">
                          <Sparkles className="h-3.5 w-3.5 text-violet-300" />
                          <span>Module {cIdx + 1} Assessment</span>
                        </span>
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })
        ) : (
          <p className="text-xs text-sidebar-muted italic p-3 text-center">
            No modules generated for this course.
          </p>
        )}

        {onSelectFinalAssessment && totalLessons > 0 && (
          <button
            type="button"
            onClick={() => {
              onSelectFinalAssessment();
              onCloseMobile();
            }}
            className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-[10px] border text-xs font-bold transition-all ${
              isFinalAssessmentMode
                ? 'bg-sidebar-active border-indigo-400 text-white'
                : 'bg-sidebar-surface border-sidebar-border text-emerald-300 hover:bg-sidebar-hover'
            }`}
          >
            <span className="flex items-center gap-2">
              <GraduationCap className="h-4 w-4 text-emerald-300" />
              <span>Final Course Assessment</span>
            </span>
          </button>
        )}
      </div>

      {/* Footer Branding */}
      <div className="p-3 border-t border-sidebar-border bg-sidebar-surface text-[11px] text-sidebar-muted flex items-center justify-between">
        <span className="flex items-center gap-1.5">
          <Sparkles className="h-3 w-3 text-violet-300" />
          <span>Interactive Syllabus</span>
        </span>
        <span className="capitalize">{course.difficulty_level}</span>
      </div>
    </div>
  );

  return (
    <>
      {!hideOnDesktop && (
        <aside className="hidden lg:block w-72 shrink-0 h-[calc(100vh-6rem)] sticky top-20 rounded-[12px] overflow-hidden border border-sidebar-border shadow-card">
          {sidebarContent}
        </aside>
      )}

      {isOpenMobile && (
        <div
          className="fixed inset-0 z-50 bg-black/65 backdrop-blur-sm lg:hidden"
          onClick={onCloseMobile}
        />
      )}

      <div
        className={`fixed inset-y-0 left-0 z-50 w-80 max-w-[85vw] transform transition-transform duration-300 ease-in-out lg:hidden ${
          isOpenMobile ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {sidebarContent}
      </div>
    </>
  );
};
