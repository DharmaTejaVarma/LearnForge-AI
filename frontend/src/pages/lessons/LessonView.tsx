import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { CourseCurriculumSidebar } from '../../components/courses/CourseCurriculumSidebar';
import { CourseOverviewView } from '../../components/courses/CourseOverviewView';
import { LessonContentView } from '../../components/courses/LessonContentView';
import { Spinner } from '../../components/common/Spinner';
import { Button } from '../../components/common/Button';
import { courseService, Course, Lesson } from '../../services/courseService';
import { 
  ArrowLeft, 
  Menu, 
  Bot, 
  GraduationCap
} from 'lucide-react';

export const LessonView: React.FC = () => {
  const { courseId } = useParams<{ courseId: string }>();

  const [course, setCourse] = useState<Course | null>(null);
  const [activeLesson, setActiveLesson] = useState<Lesson | null>(null);
  const [isOverviewMode, setIsOverviewMode] = useState<boolean>(true);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isTogglingComplete, setIsTogglingComplete] = useState<boolean>(false);
  const [isRegenerating, setIsRegenerating] = useState<boolean>(false);
  const [collapsedChapters, setCollapsedChapters] = useState<Record<number, boolean>>({});
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState<boolean>(false);

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

  // Load course details
  const fetchCourse = useCallback(async () => {
    if (!courseId) return;
    setIsLoading(true);
    try {
      const data = await courseService.get(Number(courseId));
      setCourse(data);

      // Check if user has a saved last viewed lesson
      const savedLessonId = localStorage.getItem(`learnforge_last_lesson_${courseId}`);
      if (savedLessonId) {
        const found = data.chapters?.flatMap((c) => c.topics).find((t) => t.lesson?.id === Number(savedLessonId));
        if (found && found.lesson) {
          setActiveLesson(found.lesson);
          setIsOverviewMode(false);
          setIsLoading(false);
          return;
        }
      }

      // Default: show overview mode first
      setIsOverviewMode(true);
    } catch (err) {
      console.error('Failed to load course details:', err);
    } finally {
      setIsLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    fetchCourse();
  }, [fetchCourse]);

  // Select and load a lesson
  const handleSelectLesson = async (lessonId: number) => {
    setIsOverviewMode(false);
    setIsMobileSidebarOpen(false);

    // Save to local storage for learning position resumption
    if (courseId) {
      localStorage.setItem(`learnforge_last_lesson_${courseId}`, String(lessonId));
    }

    // Check if lesson is already in flat list
    const cached = flatLessons.find((item) => item.lesson.id === lessonId);
    if (cached && cached.lesson.content) {
      setActiveLesson(cached.lesson);
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }

    // Otherwise fetch fresh from backend
    try {
      const fresh = await courseService.getLesson(lessonId);
      setActiveLesson(fresh);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      console.error('Failed to load lesson content:', err);
    }
  };

  const handleSelectOverview = () => {
    setIsOverviewMode(true);
    setIsMobileSidebarOpen(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleToggleChapter = (chapterId: number) => {
    setCollapsedChapters((prev) => ({
      ...prev,
      [chapterId]: !prev[chapterId],
    }));
  };

  // Toggle completion with backend
  const handleToggleComplete = async () => {
    if (!activeLesson) return;
    setIsTogglingComplete(true);
    try {
      const updated = await courseService.toggleComplete(activeLesson.id);
      setActiveLesson(updated);

      // Update in course state to keep progress bar and checkmarks synchronized
      setCourse((prev) => {
        if (!prev || !prev.chapters) return prev;
        const updatedChapters = prev.chapters.map((ch) => ({
          ...ch,
          topics: ch.topics.map((t) =>
            t.lesson?.id === updated.id ? { ...t, lesson: updated } : t
          ),
        }));
        return { ...prev, chapters: updatedChapters };
      });
    } catch (err) {
      console.error('Failed to toggle completion:', err);
    } finally {
      setIsTogglingComplete(false);
    }
  };

  // Regenerate failed or low-quality lesson
  const handleRegenerateLesson = async () => {
    if (!activeLesson) return;
    setIsRegenerating(true);
    try {
      const regenerated = await courseService.regenerateLesson(activeLesson.id);
      setActiveLesson(regenerated);

      setCourse((prev) => {
        if (!prev || !prev.chapters) return prev;
        const updatedChapters = prev.chapters.map((ch) => ({
          ...ch,
          topics: ch.topics.map((t) =>
            t.lesson?.id === regenerated.id ? { ...t, lesson: regenerated } : t
          ),
        }));
        return { ...prev, chapters: updatedChapters };
      });
    } catch (err) {
      console.error('Failed to regenerate lesson:', err);
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
    <div className="space-y-6">
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

        {/* Action Controls */}
        <div className="flex items-center gap-2.5">
          {/* Mobile Curriculum Toggle */}
          <Button
            size="sm"
            variant="outline"
            className="lg:hidden"
            onClick={() => setIsMobileSidebarOpen(true)}
            icon={<Menu className="h-4 w-4" />}
          >
            Curriculum
          </Button>

          {/* AI Tools quick navigation */}
          <Link to="/tutor">
            <Button size="sm" variant="secondary" icon={<Bot className="h-4 w-4 text-indigo-400" />}>
              <span className="hidden sm:inline">Ask AI Tutor</span>
              <span className="sm:hidden">Tutor</span>
            </Button>
          </Link>
        </div>
      </div>

      {/* Main Course Layout: Sticky Curriculum Sidebar + Content Area */}
      <div className="flex items-start gap-8">
        {/* Course Curriculum Sidebar */}
        <CourseCurriculumSidebar
          course={course}
          activeLessonId={activeLesson?.id || null}
          isOverviewMode={isOverviewMode}
          onSelectLesson={handleSelectLesson}
          onSelectOverview={handleSelectOverview}
          collapsedChapters={collapsedChapters}
          onToggleChapter={handleToggleChapter}
          isOpenMobile={isMobileSidebarOpen}
          onCloseMobile={() => setIsMobileSidebarOpen(false)}
        />

        {/* Main Content Area */}
        <main className="flex-1 min-w-0">
          {isOverviewMode || !activeLesson ? (
            <CourseOverviewView
              course={course}
              onStartOrResume={handleSelectLesson}
            />
          ) : (
            <LessonContentView
              lesson={activeLesson}
              chapterTitle={currentLessonMeta?.chapterTitle}
              topicTitle={currentLessonMeta?.topicTitle}
              prevLesson={currentLessonMeta?.prev || null}
              nextLesson={currentLessonMeta?.next || null}
              onToggleComplete={handleToggleComplete}
              isTogglingComplete={isTogglingComplete}
              onSelectLesson={handleSelectLesson}
              onSelectOverview={handleSelectOverview}
              onRegenerate={handleRegenerateLesson}
              isRegenerating={isRegenerating}
            />
          )}
        </main>
      </div>
    </div>
  );
};
