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
  RotateCw
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
  // Compute progress & content readiness stats
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
    <div className="flex flex-col h-full bg-slate-900 border-r border-slate-800 text-slate-100 select-none">
      {/* Header & Course Progress */}
      <div className="p-4 border-b border-slate-800 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GraduationCap className="h-5 w-5 text-indigo-400" />
            <h2 className="text-sm font-bold text-white tracking-tight uppercase">
              Course Curriculum
            </h2>
          </div>
          {/* Mobile close button */}
          <button
            onClick={onCloseMobile}
            className="md:hidden p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
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
          className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all ${
            isOverviewMode
              ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
              : 'bg-slate-800/80 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700/60'
          }`}
        >
          <BarChart2 className="h-4 w-4 text-indigo-300 shrink-0" />
          <span className="truncate">Course Overview & Syllabus</span>
        </button>

        {/* Progress Bar Widget */}
        <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1.5">
          <div className="flex items-center justify-between text-[11px] text-slate-400 font-medium">
            <span>Overall Progress</span>
            <span className="text-indigo-300 font-semibold">{progressPercent}%</span>
          </div>
          <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-indigo-500 to-emerald-400 transition-all duration-300 rounded-full"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <div className="text-[10px] text-slate-500 text-right">
            {completedLessons} of {totalLessons} lessons completed
          </div>
          {/* Compact Course Generation Progress Dashboard */}
          <div className="pt-2 border-t border-slate-800/70 space-y-1.5">
            <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
              <span>Course Generation</span>
              {onTogglePrefetch && (
                <button
                  type="button"
                  onClick={onTogglePrefetch}
                  className="inline-flex items-center gap-1 text-[10px] font-medium text-indigo-300 hover:text-indigo-200"
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

            <div className="flex items-center justify-between text-[10px] text-slate-400">
              <span>Curriculum</span>
              <span className="font-mono text-emerald-400">
                {generationProgress?.total_lessons ?? totalLessons}/{generationProgress?.total_lessons ?? totalLessons} ready ({generationProgress?.curriculum_percentage ?? 100}%)
              </span>
            </div>

            <div className="flex items-center justify-between text-[10px] text-slate-400">
              <span>Lesson Content</span>
              <span className="font-mono text-indigo-300">
                {generationProgress?.ready_lessons ?? readyLessons}/{generationProgress?.total_lessons ?? totalLessons} ready ({generationProgress?.content_readiness_percentage ?? (totalLessons > 0 ? Math.round((readyLessons / totalLessons) * 10000) / 100 : 0)}%)
              </span>
            </div>

            <div className="w-full h-1 rounded-full bg-slate-800 overflow-hidden">
              <div
                className="h-full bg-emerald-500 transition-all duration-300 rounded-full"
                style={{
                  width: `${generationProgress?.content_readiness_percentage ?? (totalLessons > 0 ? (readyLessons / totalLessons) * 100 : 0)}%`,
                }}
              />
            </div>

            <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-[10px] text-slate-400 font-mono">
              <span>{generationProgress?.queued_lessons ?? queuedLessons} queued</span>
              <span>{generationProgress?.generating_lessons ?? generatingLessons} generating</span>
              {(generationProgress?.failed_lessons ?? failedLessons) > 0 && (
                <span className="text-rose-400">{generationProgress?.failed_lessons ?? failedLessons} failed</span>
              )}
            </div>

            {generationProgress?.active_lesson_title && (
              <div className="p-2 rounded-lg bg-slate-900/90 border border-indigo-500/20 space-y-1 text-[10px]">
                <div className="flex items-center justify-between gap-1">
                  <span className="text-indigo-300 font-semibold truncate">
                    <Loader2 className="h-2.5 w-2.5 inline animate-spin mr-1" />
                    {generationProgress.active_lesson_title}
                  </span>
                  <span className="font-mono text-slate-400 shrink-0">
                    {Math.round(generationProgress.active_elapsed_seconds || 0)}s
                  </span>
                </div>
                <div className="flex items-center justify-between gap-1 text-slate-400">
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
                className="w-full inline-flex items-center justify-center gap-1 py-1 rounded-lg bg-rose-500/15 border border-rose-500/30 text-[10px] font-semibold text-rose-300 hover:bg-rose-500/25"
              >
                <RotateCw className="h-3 w-3" />
                Retry Failed Lessons ({generationProgress?.failed_lessons ?? failedLessons})
              </button>
            )}

            {generationProgress?.documents_progress && generationProgress.documents_progress.length > 0 && (
              <div className="pt-1.5 border-t border-slate-800/60 space-y-1">
                {generationProgress.documents_progress.slice(0, 2).map((doc, idx) => (
                  <div key={doc.document_id} className="text-[10px] text-slate-400">
                    <div className="flex items-center justify-between gap-1">
                      <span className="font-semibold text-slate-300 truncate">
                        DOC {idx + 1}: {doc.filename}
                      </span>
                      <span className="font-mono text-emerald-400 shrink-0">
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

            // Count completed lessons in this chapter
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
                className="rounded-xl border border-slate-800/80 bg-slate-950/40 overflow-hidden transition-all"
              >
                {/* Chapter Accordion Header */}
                <button
                  type="button"
                  onClick={() => onToggleChapter(chap.id)}
                  className="w-full flex items-center justify-between p-3 text-left hover:bg-slate-800/50 transition-colors group"
                >
                  <div className="flex items-start gap-2 pr-2 min-w-0">
                    <span className="text-slate-400 group-hover:text-indigo-400 mt-0.5 shrink-0 transition-transform">
                      {isCollapsed ? (
                        <ChevronRight className="h-4 w-4" />
                      ) : (
                        <ChevronDown className="h-4 w-4" />
                      )}
                    </span>
                    <div className="min-w-0">
                      <p className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider">
                        Module {cIdx + 1}
                      </p>
                      <h4 className="text-xs font-semibold text-slate-200 group-hover:text-white truncate mt-0.5">
                        {chap.title}
                      </h4>
                    </div>
                  </div>

                  {/* Chapter lesson count badge */}
                  <span className="text-[10px] font-mono shrink-0 px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700/50">
                    {chapCompleted}/{chapTotal}
                  </span>
                </button>

                {/* Topics & Lessons */}
                {!isCollapsed && (
                  <div className="border-t border-slate-800/60 p-1.5 space-y-1 bg-slate-900/40">
                    {chap.topics.map((topic) => {
                      const lesson = topic.lesson;
                      if (!lesson) {
                        return (
                          <div
                            key={topic.id}
                            className="px-3 py-1.5 text-xs text-slate-400 italic"
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
                          className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-left text-xs transition-all ${
                            isSelected
                              ? 'bg-indigo-600 text-white font-medium shadow-md shadow-indigo-600/30'
                              : isPending
                              ? 'text-slate-400 hover:bg-slate-800/70 hover:text-slate-200'
                              : 'text-slate-300 hover:bg-slate-800/70 hover:text-white'
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
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-40"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
                              </span>
                            ) : isFailed ? (
                              <Circle className="h-3.5 w-3.5 shrink-0 text-rose-500" />
                            ) : (
                              <Circle
                                className={`h-3.5 w-3.5 shrink-0 ${
                                  isSelected ? 'text-indigo-200' : 'text-slate-600'
                                }`}
                              />
                            )}
                            <span className="truncate leading-tight">
                              {lesson.title || topic.title}
                            </span>
                          </div>

                          {isDone && !isSelected && (
                            <span className="text-[9px] uppercase font-semibold text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded shrink-0">
                              Done
                            </span>
                          )}
                          {isPending && !isSelected && (
                            <span className="text-[9px] text-indigo-400 shrink-0">AI…</span>
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
                        className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-left text-xs font-medium transition-all mt-1 border-t border-slate-800/70 ${
                          activeAssessmentChapterId === chap.id
                            ? 'bg-indigo-600/30 text-indigo-200 border border-indigo-500/40'
                            : 'text-indigo-300/90 hover:bg-slate-800/70 hover:text-indigo-200'
                        }`}
                      >
                        <span className="flex items-center gap-2">
                          <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
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
          <p className="text-xs text-slate-500 italic p-3 text-center">
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
            className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl border text-xs font-bold transition-all ${
              isFinalAssessmentMode
                ? 'bg-emerald-600/25 border-emerald-500/50 text-emerald-200'
                : 'bg-slate-950/70 border-slate-800 text-emerald-300 hover:bg-slate-800/70'
            }`}
          >
            <span className="flex items-center gap-2">
              <GraduationCap className="h-4 w-4 text-emerald-400" />
              <span>Final Course Assessment</span>
            </span>
          </button>
        )}
      </div>

      {/* Footer Branding */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/80 text-[11px] text-slate-500 flex items-center justify-between">
        <span className="flex items-center gap-1.5">
          <Sparkles className="h-3 w-3 text-indigo-400" />
          <span>Interactive Syllabus</span>
        </span>
        <span className="text-slate-600">{course.difficulty_level}</span>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sticky Sidebar */}
      {!hideOnDesktop && (
        <aside className="hidden lg:block w-72 shrink-0 h-[calc(100vh-6rem)] sticky top-20 rounded-2xl overflow-hidden border border-slate-800 shadow-xl">
          {sidebarContent}
        </aside>
      )}

      {/* Mobile Drawer Backdrop */}
      {isOpenMobile && (
        <div
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm lg:hidden"
          onClick={onCloseMobile}
        />
      )}

      {/* Mobile Drawer */}
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
