import React from 'react';
import { Course } from '../../services/courseService';
import { 
  CheckCircle2, 
  Circle, 
  ChevronDown, 
  ChevronRight, 
  GraduationCap,
  Sparkles,
  BarChart2,
  X
} from 'lucide-react';

interface CourseCurriculumSidebarProps {
  course: Course;
  activeLessonId: number | null;
  isOverviewMode: boolean;
  onSelectLesson: (lessonId: number) => void;
  onSelectOverview: () => void;
  collapsedChapters: Record<number, boolean>;
  onToggleChapter: (chapterId: number) => void;
  isOpenMobile: boolean;
  onCloseMobile: () => void;
}

export const CourseCurriculumSidebar: React.FC<CourseCurriculumSidebarProps> = ({
  course,
  activeLessonId,
  isOverviewMode,
  onSelectLesson,
  onSelectOverview,
  collapsedChapters,
  onToggleChapter,
  isOpenMobile,
  onCloseMobile,
}) => {
  // Compute progress stats
  let totalLessons = 0;
  let completedLessons = 0;

  course.chapters?.forEach((chap) => {
    chap.topics.forEach((topic) => {
      if (topic.lesson) {
        totalLessons += 1;
        if (topic.lesson.is_completed) {
          completedLessons += 1;
        }
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
                        </button>
                      );
                    })}
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
      <aside className="hidden lg:block w-80 shrink-0 h-[calc(100vh-5.5rem)] sticky top-20 rounded-2xl overflow-hidden border border-slate-800 shadow-xl">
        {sidebarContent}
      </aside>

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
