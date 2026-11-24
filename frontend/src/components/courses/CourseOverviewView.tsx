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
  Award
} from 'lucide-react';

interface CourseOverviewViewProps {
  course: Course;
  onStartOrResume: (lessonId: number) => void;
}

export const CourseOverviewView: React.FC<CourseOverviewViewProps> = ({
  course,
  onStartOrResume,
}) => {
  // Compute metrics
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
      {/* Hero Course Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-950 via-slate-900 to-slate-950 border border-indigo-500/20 p-6 md:p-10 shadow-2xl">
        <div className="absolute top-0 right-0 -mr-16 -mt-16 w-80 h-80 rounded-full bg-indigo-600/10 blur-3xl pointer-events-none" />

        <div className="relative z-10 max-w-3xl space-y-4">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
              {course.difficulty_level || 'Modular Course'}
            </span>
            <span className="px-3 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700/80 flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-indigo-400" />
              ~{course.estimated_duration_hours || 4} Hours Total
            </span>
            {isFinished && (
              <span className="px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1.5">
                <Award className="h-3.5 w-3.5" />
                Course Completed!
              </span>
            )}
          </div>

          <h1 className="text-3xl md:text-4xl font-extrabold text-white tracking-tight leading-tight">
            {course.title}
          </h1>

          <p className="text-slate-300 text-sm md:text-base leading-relaxed">
            {course.description}
          </p>

          {/* Action Call to Action */}
          <div className="pt-3 flex flex-wrap items-center gap-4">
            {targetLessonId ? (
              <Button
                variant="primary"
                size="lg"
                onClick={() => onStartOrResume(targetLessonId)}
                icon={<PlayCircle className="h-5 w-5" />}
                className="shadow-lg shadow-indigo-600/30 text-base px-6 py-3"
              >
                {isStarted && !isFinished
                  ? 'Continue Learning'
                  : isFinished
                  ? 'Review Course from Start'
                  : 'Start Learning'}
              </Button>
            ) : null}

            <div className="text-xs text-slate-400 font-medium">
              {completedLessons} of {totalLessons} lessons finished ({progressPercent}%)
            </div>
          </div>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="p-4 bg-slate-900/90 border-slate-800 flex items-center gap-3.5">
          <div className="h-11 w-11 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shrink-0">
            <Layers className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs text-slate-400 font-medium">Modules</p>
            <p className="text-xl font-bold text-white mt-0.5">
              {course.chapters?.length || 0}
            </p>
          </div>
        </Card>

        <Card className="p-4 bg-slate-900/90 border-slate-800 flex items-center gap-3.5">
          <div className="h-11 w-11 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 shrink-0">
            <BookOpen className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs text-slate-400 font-medium">Lessons</p>
            <p className="text-xl font-bold text-white mt-0.5">{totalLessons}</p>
          </div>
        </Card>

        <Card className="p-4 bg-slate-900/90 border-slate-800 flex items-center gap-3.5">
          <div className="h-11 w-11 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400 shrink-0">
            <Clock className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs text-slate-400 font-medium">Est. Duration</p>
            <p className="text-xl font-bold text-white mt-0.5">
              ~{course.estimated_duration_hours || 4}h
            </p>
          </div>
        </Card>

        <Card className="p-4 bg-slate-900/90 border-slate-800 flex items-center gap-3.5">
          <div className="h-11 w-11 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0">
            <CheckCircle2 className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs text-slate-400 font-medium">Completion</p>
            <p className="text-xl font-bold text-white mt-0.5">{progressPercent}%</p>
          </div>
        </Card>
      </div>

      {/* Learning Objectives */}
      {course.learning_objectives && course.learning_objectives.length > 0 && (
        <Card className="p-6 md:p-8 bg-slate-900/90 border-slate-800 space-y-4">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <Target className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white tracking-tight">Learning Objectives</h2>
              <p className="text-xs text-slate-400">Key competencies and knowledge outcomes of this course</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
            {course.learning_objectives.map((obj, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-xl bg-slate-800/40 border border-slate-700/60 flex items-start gap-3 hover:border-indigo-500/40 transition-colors"
              >
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-500/10 border border-indigo-500/30 text-[11px] font-bold text-indigo-400">
                  {idx + 1}
                </span>
                <p className="text-xs md:text-sm text-slate-300 leading-relaxed">{obj}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Comprehensive Course Syllabus */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GraduationCap className="h-5 w-5 text-indigo-400" />
            <h2 className="text-xl font-bold text-white tracking-tight">Detailed Syllabus</h2>
          </div>
          <span className="text-xs text-slate-400">
            {course.chapters?.length || 0} Modules • {totalLessons} Lessons
          </span>
        </div>

        <div className="space-y-4">
          {course.chapters?.map((chap, cIdx) => (
            <Card
              key={chap.id}
              className="p-5 md:p-6 bg-slate-900/80 border-slate-800 hover:border-slate-700 transition-all space-y-4"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-800">
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400 bg-indigo-500/10 px-2.5 py-0.5 rounded-full border border-indigo-500/20">
                    Module {cIdx + 1}
                  </span>
                  <h3 className="text-base md:text-lg font-bold text-white mt-1.5">{chap.title}</h3>
                  {chap.description && (
                    <p className="text-xs text-slate-400 mt-1">{chap.description}</p>
                  )}
                </div>
                <span className="text-xs text-slate-500 self-start sm:self-center font-mono">
                  {chap.topics.length} topics
                </span>
              </div>

              {/* Topic / Lesson List */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {chap.topics.map((topic, tIdx) => {
                  const lesson = topic.lesson;
                  const isDone = lesson?.is_completed;

                  return (
                    <div
                      key={topic.id}
                      onClick={() => lesson && onStartOrResume(lesson.id)}
                      className={`p-3 rounded-xl border transition-all flex items-center justify-between cursor-pointer ${
                        isDone
                          ? 'bg-slate-900/90 border-emerald-500/30 hover:border-emerald-500/60'
                          : 'bg-slate-800/40 border-slate-700/60 hover:bg-slate-800/80 hover:border-indigo-500/40'
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0 pr-2">
                        {isDone ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                        ) : (
                          <div className="h-4 w-4 rounded-full border border-slate-600 flex items-center justify-center shrink-0">
                            <span className="text-[9px] text-slate-500 font-mono">{tIdx + 1}</span>
                          </div>
                        )}
                        <span className="text-xs font-medium text-slate-200 truncate">
                          {lesson?.title || topic.title}
                        </span>
                      </div>

                      <ChevronRight className="h-4 w-4 text-slate-500 shrink-0" />
                    </div>
                  );
                })}
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
};
