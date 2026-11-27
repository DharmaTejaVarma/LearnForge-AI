import React, { useState, useEffect } from 'react';
import { Lesson, LessonExercise, courseService } from '../../services/courseService';
import { learningService } from '../../services/learningService';
import { Button } from '../common/Button';
import { MarkdownRenderer } from './MarkdownRenderer';
import {
  Bookmark,
  BookmarkCheck,
  Bot,
  List,
  Send,
  Sparkles,
  Check,
  Target,
  X,
} from 'lucide-react';

interface LessonToolsSidebarProps {
  courseId: number;
  documentId?: number;
  lesson: Lesson;
  activeTab: 'outline' | 'tutor';
  onTabChange: (tab: 'outline' | 'tutor') => void;
  onClose?: () => void;
  tutorExerciseTrigger?: { exercise: LessonExercise; nonce: number } | null;
}

interface TutorMsg {
  role: 'user' | 'assistant';
  content: string;
}

export const LessonToolsSidebar: React.FC<LessonToolsSidebarProps> = ({
  courseId,
  documentId,
  lesson,
  activeTab,
  onTabChange,
  onClose,
  tutorExerciseTrigger,
}) => {
  const [noteText, setNoteText] = useState<string>(lesson.note?.content || '');
  const [isBookmarked, setIsBookmarked] = useState<boolean>(!!lesson.note?.is_bookmarked);
  const [noteStatus, setNoteStatus] = useState<'idle' | 'saving' | 'saved'>('idle');

  const [messages, setMessages] = useState<TutorMsg[]>([]);
  const [question, setQuestion] = useState<string>('');
  const [isAsking, setIsAsking] = useState<boolean>(false);
  const [convId, setConvId] = useState<string | undefined>(undefined);

  useEffect(() => {
    setNoteText(lesson.note?.content || '');
    setIsBookmarked(!!lesson.note?.is_bookmarked);
    setNoteStatus('idle');
    setMessages([]);
    setConvId(undefined);
  }, [lesson.id]);

  const sendTutorQuery = async (
    text: string,
    mode?: string,
    exerciseId?: number,
  ) => {
    if (!text.trim() || isAsking) return;
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setQuestion('');
    setIsAsking(true);
    try {
      const res = await learningService.askTutor(
        text,
        documentId,
        courseId,
        lesson.id,
        convId,
        exerciseId,
        mode,
      );
      if (res.conversation_id) setConvId(res.conversation_id);
      setMessages((prev) => [...prev, { role: 'assistant', content: res.answer }]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content:
            err?.response?.data?.error?.message ||
            'Unable to reach AI Tutor right now. Please try again.',
        },
      ]);
    } finally {
      setIsAsking(false);
    }
  };

  useEffect(() => {
    if (tutorExerciseTrigger) {
      onTabChange('tutor');
      sendTutorQuery(
        `Give me a step-by-step hint without revealing the final answer for: "${tutorExerciseTrigger.exercise.title}"`,
        'hint_only',
        tutorExerciseTrigger.exercise.id,
      );
    }
  }, [tutorExerciseTrigger?.nonce]);

  const handleSaveNote = async (bookmarkOverride?: boolean) => {
    setNoteStatus('saving');
    try {
      const nextBm = bookmarkOverride !== undefined ? bookmarkOverride : isBookmarked;
      const saved = await courseService.saveLessonNote(lesson.id, {
        content: noteText,
        is_bookmarked: nextBm,
      });
      setIsBookmarked(saved.is_bookmarked);
      setNoteStatus('saved');
      setTimeout(() => setNoteStatus('idle'), 1800);
    } catch (err) {
      console.error('Save note failed:', err);
      setNoteStatus('idle');
    }
  };

  const tocItems = lesson.structured_sections?.toc || [];

  return (
    <>
      {onClose && (
        <div
          className="fixed inset-0 z-40 bg-black/45 backdrop-blur-[1px]"
          onClick={onClose}
        />
      )}
      <aside className="fixed top-16 right-0 bottom-0 z-50 flex flex-col w-96 max-w-[92vw] border-l border-line bg-surface overflow-hidden shadow-modal">
        {/* Top Switch Tabs + Close */}
        <div className="flex items-center gap-1.5 border-b border-line bg-subtle p-2">
          <div className="grid grid-cols-2 flex-1 gap-1">
            <button
              type="button"
              onClick={() => onTabChange('outline')}
              className={`flex items-center justify-center gap-1.5 py-2 rounded-[10px] text-xs font-semibold transition-all ${
                activeTab === 'outline'
                  ? 'bg-brand text-white shadow-sm'
                  : 'text-ink-secondary hover:text-ink-primary hover:bg-hoverbg'
              }`}
            >
              <List className="h-3.5 w-3.5" />
              <span>Outline &amp; Notes</span>
            </button>

            <button
              type="button"
              onClick={() => onTabChange('tutor')}
              className={`flex items-center justify-center gap-1.5 py-2 rounded-[10px] text-xs font-semibold transition-all ${
                activeTab === 'tutor'
                  ? 'bg-brand text-white shadow-sm'
                  : 'text-ink-secondary hover:text-ink-primary hover:bg-hoverbg'
              }`}
            >
              <Bot className="h-3.5 w-3.5" />
              <span>AI Tutor</span>
            </button>
          </div>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="p-2 rounded-[10px] text-ink-secondary hover:text-ink-primary hover:bg-hoverbg transition-colors"
              aria-label="Close study tools"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {activeTab === 'outline' ? (
          <div className="flex-1 overflow-y-auto p-4 space-y-5">
            {/* Bookmark Action */}
            <button
              type="button"
              onClick={() => {
                const next = !isBookmarked;
                setIsBookmarked(next);
                handleSaveNote(next);
              }}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-[10px] border text-xs font-semibold transition-all ${
                isBookmarked
                  ? 'bg-status-warning-bg border-status-warning-border text-status-warning-text'
                  : 'bg-subtle border-line text-ink-primary hover:bg-hoverbg hover:border-brand-soft-border'
              }`}
            >
              <span className="flex items-center gap-2">
                {isBookmarked ? (
                  <BookmarkCheck className="h-4 w-4" />
                ) : (
                  <Bookmark className="h-4 w-4 text-ink-secondary" />
                )}
                {isBookmarked ? 'Bookmarked Lesson' : 'Bookmark Lesson'}
              </span>
            </button>

            {/* Lesson TOC */}
            {tocItems.length > 0 && (
              <div className="space-y-2">
                <p className="text-[11px] font-bold uppercase tracking-wider text-ink-secondary">
                  On This Page
                </p>
                <nav className="space-y-1">
                  {tocItems.map((item, idx) => (
                    <a
                      key={idx}
                      href={`#${item.slug}`}
                      className="block px-2.5 py-1.5 rounded-[10px] text-xs text-ink-secondary hover:bg-hoverbg hover:text-ink-primary transition-colors truncate"
                    >
                      {item.title}
                    </a>
                  ))}
                  {(lesson.exercises?.length || 0) > 0 && (
                    <a
                      href="#practice-exercises"
                      className="block px-2.5 py-1.5 rounded-[10px] text-xs text-accent hover:bg-hoverbg font-medium transition-colors"
                    >
                      Practice Exercises ({lesson.exercises?.length})
                    </a>
                  )}
                </nav>
              </div>
            )}

            {/* Learning Objectives */}
            {lesson.learning_objectives && lesson.learning_objectives.length > 0 && (
              <div className="space-y-2">
                <p className="text-[11px] font-bold uppercase tracking-wider text-ink-secondary flex items-center gap-1.5">
                  <Target className="h-3.5 w-3.5 text-brand" />
                  Objectives
                </p>
                <ul className="space-y-1.5 text-xs text-ink-primary">
                  {lesson.learning_objectives.slice(0, 3).map((obj, idx) => (
                    <li key={idx} className="leading-relaxed flex items-start gap-2">
                      <span className="text-accent mt-0.5">•</span>
                      <span>{obj}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Personal Study Notes */}
            <div className="space-y-2 pt-3 border-t border-line">
              <div className="flex items-center justify-between">
                <p className="text-[11px] font-bold uppercase tracking-wider text-ink-secondary">
                  Personal Notes
                </p>
                {noteStatus === 'saved' && (
                  <span className="inline-flex items-center gap-1 text-[10px] text-status-success-text font-semibold">
                    <Check className="h-3 w-3" /> Saved
                  </span>
                )}
              </div>
              <textarea
                rows={6}
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                placeholder="Write key insights, doubts, or snippets..."
                className="lf-control w-full p-3 text-xs resize-y"
              />
              <Button
                size="sm"
                variant="secondary"
                className="w-full"
                isLoading={noteStatus === 'saving'}
                onClick={() => handleSaveNote()}
              >
                Save Notes
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col min-h-0">
            {/* Quick Mode Chips */}
            <div className="p-3 border-b border-line flex flex-wrap gap-1.5">
              {[
                { label: 'Explain simply', mode: 'explain_simple', q: `Explain "${lesson.title}" in simple beginner-friendly terms.` },
                { label: 'Explain code', mode: 'explain_code', q: `Walk through the code mechanics in "${lesson.title}" step by step.` },
                { label: 'Practice Q', mode: 'practice_question', q: `Quiz me with one short check question on "${lesson.title}".` },
              ].map((chip) => (
                <button
                  key={chip.mode}
                  type="button"
                  disabled={isAsking}
                  onClick={() => sendTutorQuery(chip.q, chip.mode)}
                  className="px-2.5 py-1 rounded-full bg-subtle hover:bg-hoverbg border border-line hover:border-brand-soft-border text-[11px] text-ink-primary transition-colors"
                >
                  {chip.label}
                </button>
              ))}
            </div>

            {/* Chat Messages */}
            <div className="flex-1 overflow-y-auto p-3 space-y-3">
              {messages.length === 0 ? (
                <div className="text-center py-8 px-3 space-y-2">
                  <Sparkles className="h-6 w-6 text-accent mx-auto" />
                  <p className="text-xs font-semibold text-ink-primary">
                    Lesson-Aware AI Tutor
                  </p>
                  <p className="text-[11px] text-ink-secondary leading-relaxed">
                    Ask anything about <strong>{lesson.title}</strong> or click a quick prompt above.
                  </p>
                </div>
              ) : (
                messages.map((m, i) => (
                  <div
                    key={i}
                    className={`p-3 rounded-[12px] text-xs leading-relaxed ${
                      m.role === 'user'
                        ? 'bg-brand text-white ml-4'
                        : 'bg-subtle border border-line text-ink-primary mr-2'
                    }`}
                  >
                    {m.role === 'assistant' ? (
                      <MarkdownRenderer content={m.content} className="prose-xs" />
                    ) : (
                      <span>{m.content}</span>
                    )}
                  </div>
                ))
              )}
              {isAsking && (
                <div className="p-2.5 rounded-[10px] bg-subtle border border-line text-[11px] text-brand animate-pulse">
                  Thinking with lesson &amp; source context...
                </div>
              )}
            </div>

            {/* Input Box */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                sendTutorQuery(question);
              }}
              className="p-3 border-t border-line flex items-center gap-2 bg-subtle"
            >
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask about this lesson..."
                className="lf-control flex-1 px-3 py-2 text-xs"
              />
              <Button
                size="sm"
                variant="primary"
                type="submit"
                disabled={!question.trim() || isAsking}
                icon={<Send className="h-3.5 w-3.5" />}
              >
                Ask
              </Button>
            </form>
          </div>
        )}
      </aside>
    </>
  );
};
