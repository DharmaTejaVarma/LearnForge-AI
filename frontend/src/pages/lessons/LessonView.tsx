import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { CourseCurriculumSidebar } from '../../components/courses/CourseCurriculumSidebar';
import { CourseOverviewView } from '../../components/courses/CourseOverviewView';
import { LessonContentView } from '../../components/courses/LessonContentView';
import { LessonToolsSidebar } from '../../components/courses/LessonToolsSidebar';
import { AssessmentPanel } from '../../components/courses/AssessmentPanel';
import { Spinner } from '../../components/common/Spinner';
import { Button } from '../../components/common/Button';
import {
  courseService,
  Course,
  Lesson,
  LessonExercise,
  GenerationJob,
  LessonJobStatus,
} from '../../services/courseService';
import {
  ArrowLeft,
  Menu,
  Bot,
  GraduationCap,
  PanelRight,
  Loader2,
} from 'lucide-react';

function formatApiError(err: any, fallback: string): string {
  const status = err?.response?.status;
  const serverMsg = err?.response?.data?.error?.message || err?.response?.data?.detail;
  if (serverMsg) return String(serverMsg);
  if (err?.code === 'ECONNABORTED' || String(err?.message || '').toLowerCase().includes('timeout')) {
    return 'Request timed out while waiting for the server. The lesson job may still be running — wait a moment or click Regenerate Lesson.';
  }
  if (!err?.response) {
    return 'Unable to reach the LearnForge AI backend (http://127.0.0.1:8000). Verify the backend server is running and retry.';
  }
  if (status === 429) return 'Too many requests. Please wait a few seconds before retrying.';
  if (status === 502 || status === 503 || status === 504) {
    return `AI service temporarily unavailable (HTTP ${status}). Verify Ollama is running and click Regenerate Lesson.`;
  }
  if (status >= 500) return `Server error (HTTP ${status}) during lesson synthesis. Click Regenerate Lesson to retry.`;
  return fallback;
}

export const LessonView: React.FC = () => {
  const { courseId } = useParams<{ courseId: string }>();

  const [course, setCourse] = useState<Course | null>(null);
  const [activeLesson, setActiveLesson] = useState<Lesson | null>(null);
  const [viewMode, setViewMode] = useState<'overview' | 'lesson' | 'module_assessment' | 'final_assessment'>('overview');
  const [assessmentChapterId, setAssessmentChapterId] = useState<number | null>(null);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isTogglingComplete, setIsTogglingComplete] = useState<boolean>(false);
  const [isRegenerating, setIsRegenerating] = useState<boolean>(false);
  const [isLoadingLesson, setIsLoadingLesson] = useState<boolean>(false);
  const [collapsedChapters, setCollapsedChapters] = useState<Record<number, boolean>>({});
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState<boolean>(false);
  const [showCurriculum, setShowCurriculum] = useState<boolean>(true);

  const [showToolsPane, setShowToolsPane] = useState<boolean>(false);
  const [toolsTab, setToolsTab] = useState<'outline' | 'tutor'>('outline');
  const [tutorTrigger, setTutorTrigger] = useState<{ exercise: LessonExercise; nonce: number } | null>(null);
  const [genJob, setGenJob] = useState<GenerationJob | null>(null);
  const [lessonJobStatus, setLessonJobStatus] = useState<LessonJobStatus | null>(null);

  // Flatten ordered lessons list for Prev/Next navigation
  const flatLessons = useMemo(() => {
    if (!course?.chapters) return [];
    const list: Array<{
      lesson: Lesson;
      chapterTitle: string;
      topicTitle: string;
    }> = [];

    course.chapters.forEach((chap) => {
      chap.topics.forEach((topic) => {
        if (topic.lesson) {
          list.push({
            lesson: topic.lesson,
            chapterTitle: chap.title,
            topicTitle: topic.title,
          });
        }
      });
    });

    return list;
  }, [course]);

  // Determine current, previous, and next lesson
  const currentLessonMeta = useMemo(() => {
    if (!activeLesson) return null;
    const idx = flatLessons.findIndex((item) => item.lesson.id === activeLesson.id);
    if (idx === -1) return null;

    const prev = idx > 0 ? { id: flatLessons[idx - 1].lesson.id, title: flatLessons[idx - 1].lesson.title } : null;
    const next = idx < flatLessons.length - 1 ? { id: flatLessons[idx + 1].lesson.id, title: flatLessons[idx + 1].lesson.title } : null;

    return {
      prev,
      next,
      chapterTitle: flatLessons[idx].chapterTitle,
      topicTitle: flatLessons[idx].topicTitle,
    };
  }, [activeLesson, flatLessons]);

  const handleSelectLesson = useCallback(async (lessonId: number) => {
    setViewMode('lesson');
    setAssessmentChapterId(null);
    setIsMobileSidebarOpen(false);

    if (courseId) {
      localStorage.setItem(`learnforge_last_lesson_${courseId}`, String(lessonId));
    }

    const cached = flatLessons.find((item) => item.lesson.id === lessonId);
    if (cached && cached.lesson.content && cached.lesson.exercises && cached.lesson.exercises.length > 0) {
      setActiveLesson(cached.lesson);
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }

    if (cached) {
      setActiveLesson({
        ...cached.lesson,
        generation_status: cached.lesson.content ? cached.lesson.generation_status : 'queued',
      });
    }
    setIsLoadingLesson(true);

    try {
      const fresh = await courseService.getLesson(lessonId);
      setActiveLesson(fresh);
      setCourse((prev) => {
        if (!prev || !prev.chapters) return prev;
        return {
          ...prev,
          chapters: prev.chapters.map((ch) => ({
            ...ch,
            topics: ch.topics.map((t) =>
              t.lesson?.id === fresh.id ? { ...t, lesson: fresh } : t
            ),
          })),
        };
      });
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err: any) {
      console.error('Failed to load lesson content:', err);
      if (cached) {
        setActiveLesson({
          ...cached.lesson,
          generation_status: 'failed',
          generation_error: formatApiError(
            err,
            'Lesson synthesis failed. Click Regenerate Lesson to retry.',
          ),
        });
      }
    } finally {
      setIsLoadingLesson(false);
    }
  }, [courseId, flatLessons]);

  // Load course details
  const fetchCourse = useCallback(async () => {
    if (!courseId) return;
    setIsLoading(true);
    try {
      const data = await courseService.get(Number(courseId));
      setCourse(data);
      setGenJob(data.active_job || null);

      const savedLessonId = localStorage.getItem(`learnforge_last_lesson_${courseId}`);
      if (savedLessonId) {
        const found = data.chapters?.flatMap((c) => c.topics).find((t) => t.lesson?.id === Number(savedLessonId));
        if (found && found.lesson && found.lesson.content) {
          const fresh = await courseService.getLesson(found.lesson.id);
          setActiveLesson(fresh);
          setViewMode('lesson');
          setIsLoading(false);
          return;
        }
      }

      setViewMode('overview');
    } catch (err) {
      console.error('Failed to load course details:', err);
    } finally {
      setIsLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    fetchCourse();
  }, [fetchCourse]);

  // Real GenerationJob polling while background synthesis runs
  useEffect(() => {
    if (!courseId || !genJob || genJob.status !== 'running') return;
    const timer = setInterval(async () => {
      try {
        const status = await courseService.getGenerationStatus(Number(courseId));
        if (status) {
          setGenJob(status);
          if (status.status !== 'running') {
            const refreshed = await courseService.get(Number(courseId));
            setCourse(refreshed);
          }
        }
      } catch {
        // Ignore transient poll errors
      }
    }, 4500);
    return () => clearInterval(timer);
  }, [courseId, genJob?.status]);

  // Poll lightweight /status endpoint while active lesson is queued or generating
  useEffect(() => {
    if (!activeLesson) return;
    const isPending = activeLesson.generation_status === 'queued' || activeLesson.generation_status === 'generating';
    if (!isPending) {
      setLessonJobStatus(null);
      return;
    }

    let cancelled = false;
    const pollStatus = async () => {
      try {
        const st = await courseService.getLessonStatus(activeLesson.id);
        if (cancelled) return;
        setLessonJobStatus(st);
        if (st.status === 'COMPLETED' || st.status === 'FAILED' || st.status === 'CANCELLED') {
          const fresh = await courseService.getLesson(activeLesson.id);
          if (cancelled) return;
          setActiveLesson(fresh);
          setCourse((prev) => {
            if (!prev || !prev.chapters) return prev;
            return {
              ...prev,
              chapters: prev.chapters.map((ch) => ({
                ...ch,
                topics: ch.topics.map((t) =>
                  t.lesson?.id === fresh.id ? { ...t, lesson: fresh } : t
                ),
              })),
            };
          });
        }
      } catch {
        // Ignore transient errors
      }
    };

    pollStatus();
    const timer = setInterval(pollStatus, 2500);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [activeLesson?.id, activeLesson?.generation_status]);

  // Refresh the full course sidebar every 20s when any lessons are still generating
  useEffect(() => {
    if (!courseId || !course) return;
    const hasQueued = course.chapters?.some((ch) =>
      ch.topics.some(
        (t) => t.lesson?.generation_status === 'queued' || t.lesson?.generation_status === 'generating'
      )
    );
    if (!hasQueued) return;

    const refreshCourse = async () => {
      try {
        const refreshed = await courseService.get(Number(courseId));
        setCourse(refreshed);
      } catch {
        // Ignore
      }
    };

    const timer = setInterval(refreshCourse, 20000);
    return () => clearInterval(timer);
  }, [courseId, course?.chapters?.length]);

  const handleSelectOverview = () => {
    setViewMode('overview');
    setAssessmentChapterId(null);
    setIsMobileSidebarOpen(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleOpenModuleAssessment = (chapterId: number) => {
    setAssessmentChapterId(chapterId);
    setViewMode('module_assessment');
    setIsMobileSidebarOpen(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleOpenFinalAssessment = () => {
    setAssessmentChapterId(null);
    setViewMode('final_assessment');
    setIsMobileSidebarOpen(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleToggleChapter = (chapterId: number) => {
    setCollapsedChapters((prev) => ({
      ...prev,
      [chapterId]: !prev[chapterId],
    }));
  };

  const handleToggleComplete = async () => {
    if (!activeLesson) return;
    setIsTogglingComplete(true);
    try {
      const updated = await courseService.toggleComplete(activeLesson.id);
      setActiveLesson(updated);
      setCourse((prev) => {
        if (!prev || !prev.chapters) return prev;
        return {
          ...prev,
          chapters: prev.chapters.map((ch) => ({
            ...ch,
            topics: ch.topics.map((t) =>
              t.lesson?.id === updated.id ? { ...t, lesson: updated } : t
            ),
          })),
        };
      });
    } catch (err) {
      console.error('Failed to toggle completion:', err);
    } finally {
      setIsTogglingComplete(false);
    }
  };

  const handleRegenerateLesson = async () => {
    if (!activeLesson) return;
    setIsRegenerating(true);
    try {
      const regenerated = await courseService.regenerateLesson(activeLesson.id);
      setActiveLesson(regenerated);
      setCourse((prev) => {
        if (!prev || !prev.chapters) return prev;
        return {
          ...prev,
          chapters: prev.chapters.map((ch) => ({
            ...ch,
            topics: ch.topics.map((t) =>
              t.lesson?.id === regenerated.id ? { ...t, lesson: regenerated } : t
            ),
          })),
        };
      });
    } catch (err: any) {
      console.error('Failed to regenerate lesson:', err);
      setActiveLesson((prev) =>
        prev
          ? {
              ...prev,
              generation_status: 'failed',
              generation_error: formatApiError(
                err,
                'Failed to start lesson regeneration. Please retry.',
              ),
            }
          : prev,
      );
    } finally {
      setIsRegenerating(false);
    }
  };

  if (isLoading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center space-y-4">
        <Spinner size="lg" />
        <p className="text-sm text-slate-400">Loading structured course syllabus...</p>
      </div>
    );
  }

  if (!course) {
    return (
      <div className="py-16 text-center space-y-4 max-w-md mx-auto">
        <div className="h-14 w-14 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center justify-center mx-auto">
          <GraduationCap className="h-7 w-7" />
        </div>
        <h2 className="text-xl font-bold text-white">Course Not Found</h2>
        <p className="text-xs text-slate-400">
          The requested course could not be loaded or was removed.
        </p>
        <Link to="/courses">
          <Button variant="primary" size="sm" icon={<ArrowLeft className="h-4 w-4" />}>
            Return to Courses
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Top Application Bar */}
      <div className="flex items-center justify-between gap-4 pb-2 border-b border-slate-800/80">
        <div className="flex items-center gap-3 min-w-0">
          <Link
            to="/courses"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-white transition-colors shrink-0"
          >
            <ArrowLeft className="h-4 w-4" />
            <span className="hidden sm:inline">All Courses</span>
          </Link>

          <span className="text-slate-700 hidden sm:inline">•</span>

          <h1 className="text-sm font-semibold text-slate-200 truncate hidden md:inline">
            {course.title}
          </h1>
        </div>

        <div className="flex items-center gap-2.5">
          {/* Show job progress from GenerationJob OR from lesson status counts */}
          {(() => {
            const totalLessons = course.chapters?.reduce((acc, ch) => acc + ch.topics.filter(t => t.lesson).length, 0) ?? 0;
            const readyLessons = course.chapters?.reduce((acc, ch) => acc + ch.topics.filter(t => t.lesson?.generation_status === 'ready').length, 0) ?? 0;
            const hasQueued = course.chapters?.some(ch => ch.topics.some(t => t.lesson?.generation_status === 'queued' || t.lesson?.generation_status === 'generating'));
            const showProgress = (genJob && genJob.status === 'running') || hasQueued;
            if (!showProgress || totalLessons === 0) return null;
            const label = genJob?.current_stage || `Synthesizing lessons (${readyLessons}/${totalLessons} ready)`;
            return (
              <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-950/60 border border-indigo-500/30 text-[11px] text-indigo-200">
                <Loader2 className="h-3 w-3 animate-spin text-indigo-400 shrink-0" />
                <span className="truncate max-w-[220px]">{label}</span>
              </div>
            );
          })()}

          <Button
            size="sm"
            variant="outline"
            className="lg:hidden"
            onClick={() => setIsMobileSidebarOpen(true)}
            icon={<Menu className="h-4 w-4" />}
          >
            Curriculum
          </Button>

          <Button
            size="sm"
            variant="ghost"
            className="hidden lg:inline-flex"
            onClick={() => setShowCurriculum((p) => !p)}
            icon={<Menu className="h-4 w-4 text-slate-400" />}
          >
            {showCurriculum ? 'Focus Mode' : 'Show Curriculum'}
          </Button>

          {viewMode === 'lesson' && (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setShowToolsPane((p) => !p)}
              icon={<PanelRight className="h-4 w-4 text-indigo-400" />}
            >
              {showToolsPane ? 'Close Notes & Tutor' : 'Notes & AI Tutor'}
            </Button>
          )}

          <Link to="/tutor">
            <Button size="sm" variant="secondary" icon={<Bot className="h-4 w-4 text-indigo-400" />}>
              <span className="hidden sm:inline">Full AI Tutor</span>
              <span className="sm:hidden">Tutor</span>
            </Button>
          </Link>
        </div>
      </div>

      {/* Main Course Workspace */}
      <div className="flex items-start gap-6">
        {/* Left Pane: Course Curriculum & Assessments (collapsible on desktop via Focus Mode) */}
        <CourseCurriculumSidebar
          course={course}
          activeLessonId={activeLesson?.id || null}
          isOverviewMode={viewMode === 'overview'}
          activeAssessmentChapterId={viewMode === 'module_assessment' ? assessmentChapterId : null}
          isFinalAssessmentMode={viewMode === 'final_assessment'}
          onSelectLesson={handleSelectLesson}
          onSelectOverview={handleSelectOverview}
          onSelectModuleAssessment={handleOpenModuleAssessment}
          onSelectFinalAssessment={handleOpenFinalAssessment}
          collapsedChapters={collapsedChapters}
          onToggleChapter={handleToggleChapter}
          isOpenMobile={isMobileSidebarOpen}
          onCloseMobile={() => setIsMobileSidebarOpen(false)}
          hideOnDesktop={!showCurriculum}
        />

        {/* Center Pane: Overview, Lesson + Interactive Practice, or Assessment */}
        <main className="flex-1 min-w-0">
          {viewMode === 'module_assessment' || viewMode === 'final_assessment' ? (
            <AssessmentPanel
              courseId={course.id}
              chapterId={viewMode === 'module_assessment' ? assessmentChapterId : null}
              onBackToOverview={handleSelectOverview}
              onJumpToLesson={handleSelectLesson}
            />
          ) : viewMode === 'overview' || (!activeLesson && !isLoadingLesson) ? (
            <CourseOverviewView
              course={course}
              onStartOrResume={handleSelectLesson}
              onOpenModuleAssessment={handleOpenModuleAssessment}
              onOpenFinalAssessment={handleOpenFinalAssessment}
            />
          ) : !activeLesson ? (
            <div className="py-24 flex flex-col items-center justify-center space-y-4">
              <Spinner size="lg" />
              <p className="text-sm text-slate-400">Synthesizing lesson content...</p>
            </div>
          ) : (
            <LessonContentView
              lesson={activeLesson}
              chapterTitle={currentLessonMeta?.chapterTitle}
              topicTitle={currentLessonMeta?.topicTitle}
              difficultyLevel={course.difficulty_level}
              prevLesson={currentLessonMeta?.prev || null}
              nextLesson={currentLessonMeta?.next || null}
              onToggleComplete={handleToggleComplete}
              isTogglingComplete={isTogglingComplete}
              onSelectLesson={handleSelectLesson}
              onSelectOverview={handleSelectOverview}
              onRegenerate={handleRegenerateLesson}
              isRegenerating={isRegenerating}
              jobStatus={lessonJobStatus}
              onCancelGeneration={async () => {
                if (!activeLesson) return;
                await courseService.cancelLesson(activeLesson.id);
                setLessonJobStatus(null);
                handleSelectOverview();
              }}
              onAskTutorHint={(ex) => {
                setShowToolsPane(true);
                setToolsTab('tutor');
                setTutorTrigger({ exercise: ex, nonce: Date.now() });
              }}
            />
          )}
        </main>

        {/* Right Slide-Over Drawer: Outline, Personal Notes, Bookmarks & Lesson AI Tutor */}
        {viewMode === 'lesson' && activeLesson && showToolsPane && (
          <LessonToolsSidebar
            courseId={course.id}
            documentId={course.document_id}
            lesson={activeLesson}
            activeTab={toolsTab}
            onTabChange={setToolsTab}
            onClose={() => setShowToolsPane(false)}
            tutorExerciseTrigger={tutorTrigger}
          />
        )}
      </div>
    </div>
  );
};
