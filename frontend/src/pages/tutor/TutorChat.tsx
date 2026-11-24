import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Spinner } from '../../components/common/Spinner';
import { Button } from '../../components/common/Button';
import { MarkdownRenderer } from '../../components/courses/MarkdownRenderer';
import { learningService, Citation } from '../../services/learningService';
import { courseService, Course } from '../../services/courseService';
import { documentService, UploadedDocument } from '../../services/documentService';
import { formatDocumentTitle } from '../../utils/formatters';
import { 
  Bot, 
  Send, 
  User, 
  FileText,
  Trash2,
  Plus,
  Sparkles,
  BookOpen,
  HelpCircle,
  GraduationCap
} from 'lucide-react';

interface ChatMessage {
  id: string;
  sender: 'user' | 'tutor';
  text: string;
  citations?: Citation[];
  intent?: string;
  provider?: string;
  latency?: number;
}

export const TutorChat: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'tutor',
      text: "Hello! I am your **LearnForge AI Socratic Tutor**. I'm here to help you deeply understand your study materials. Ask me any question, request real-world examples, or say 'Summarize this topic' to get started!",
    },
  ]);
  const [inputQuestion, setInputQuestion] = useState('');
  const [courses, setCourses] = useState<Course[]>([]);
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<number | undefined>(undefined);
  const [selectedDocId, setSelectedDocId] = useState<number | undefined>(undefined);
  const [conversationId, setConversationId] = useState<string>(() => `conv_${Math.random().toString(36).substring(2, 10)}`);
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load courses and documents
  useEffect(() => {
    const loadContexts = async () => {
      try {
        const [coursesData, docsData] = await Promise.all([
          courseService.list(),
          documentService.list(),
        ]);
        setCourses(coursesData);
        setDocuments(docsData);
        if (coursesData.length > 0 && !selectedCourseId) {
          setSelectedCourseId(coursesData[0].id);
        }
      } catch (err) {
        console.error('Failed to load courses or documents:', err);
      }
    };
    loadContexts();
  }, []);

  // Fetch dynamic suggestions when course changes
  const fetchSuggestions = useCallback(async () => {
    try {
      const suggestions = await learningService.getTutorSuggestions(selectedCourseId);
      setSuggestedQuestions(suggestions);
    } catch (err) {
      setSuggestedQuestions([
        "Explain the key concepts of this course.",
        "Give me a practical real-world example.",
        "What are the most important formulas or principles?",
        "Test my understanding with a conceptual practice question.",
      ]);
    }
  }, [selectedCourseId]);

  useEffect(() => {
    fetchSuggestions();
  }, [fetchSuggestions]);

  // Load chat history when course or document or conversation changes
  useEffect(() => {
    const loadHistory = async () => {
      try {
        const history = await learningService.getTutorHistory(selectedDocId, selectedCourseId, conversationId);
        if (history && history.length > 0) {
          const loadedMsgs: ChatMessage[] = [];
          for (const item of history) {
            loadedMsgs.push({
              id: `q_${item.id}`,
              sender: 'user',
              text: item.question,
            });
            loadedMsgs.push({
              id: `a_${item.id}`,
              sender: 'tutor',
              text: item.answer,
              citations: item.citations,
              intent: item.intent,
            });
          }
          setMessages([
            {
              id: 'welcome',
              sender: 'tutor',
              text: "Welcome back! Here is your active dialogue. What would you like to explore next?",
            },
            ...loadedMsgs,
          ]);
        }
      } catch (err) {
        console.debug('No prior tutor history to restore:', err);
      }
    };
    loadHistory();
  }, [selectedCourseId, selectedDocId, conversationId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isThinking]);

  const handleSend = async (questionText?: string) => {
    const q = (questionText || inputQuestion).trim();
    if (!q || isThinking) return;

    const userMsg: ChatMessage = {
      id: Math.random().toString(36).substring(7),
      sender: 'user',
      text: q,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuestion('');
    setIsThinking(true);

    try {
      const res = await learningService.askTutor(
        q,
        selectedDocId,
        selectedCourseId,
        undefined, // lessonId
        conversationId,
      );

      // Keep conversationId synchronized
      if (res.conversation_id) {
        setConversationId(res.conversation_id);
      }

      const tutorMsg: ChatMessage = {
        id: Math.random().toString(36).substring(7),
        sender: 'tutor',
        text: res.answer,
        citations: res.citations,
        intent: res.intent,
        provider: res.provider_used,
        latency: res.latency_ms,
      };
      setMessages((prev) => [...prev, tutorMsg]);
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || "Failed to reach AI Tutor.";
      const errMsg: ChatMessage = {
        id: Math.random().toString(36).substring(7),
        sender: 'tutor',
        text: `**Notice:** ${msg}. Please check your selected course material and try again.`,
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsThinking(false);
    }
  };

  const handleStartNewChat = () => {
    const newConvId = `conv_${Math.random().toString(36).substring(2, 10)}`;
    setConversationId(newConvId);
    setMessages([
      {
        id: 'welcome_new',
        sender: 'tutor',
        text: "Started a fresh conversation session. What concept would you like to study today?",
      },
    ]);
  };

  const handleClearHistory = async () => {
    if (!window.confirm("Clear all conversation history for this course?")) return;
    try {
      await learningService.clearTutorHistory(selectedDocId, selectedCourseId);
      handleStartNewChat();
    } catch (err) {
      console.error('Failed to clear conversation history:', err);
    }
  };

  const activeCourse = courses.find((c) => c.id === selectedCourseId);

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col space-y-4 max-w-5xl mx-auto animate-fadeIn">
      {/* Top Application Header: Context Scope & Action Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-3 border-b border-slate-800 gap-3">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white shadow-lg shadow-indigo-600/30 shrink-0">
            <Bot className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold text-white tracking-tight flex items-center gap-2">
              Socratic AI Tutor
              {activeCourse && (
                <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300">
                  {activeCourse.title}
                </span>
              )}
            </h1>
            <p className="text-xs text-slate-400">Contextual dialogue, intent routing, and verified page citations</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {/* Course Scope Selector */}
          {courses.length > 0 && (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-slate-400 flex items-center gap-1">
                <GraduationCap className="h-3.5 w-3.5 text-indigo-400" />
                Course:
              </span>
              <select
                value={selectedCourseId || ''}
                onChange={(e) => {
                  setSelectedCourseId(e.target.value ? Number(e.target.value) : undefined);
                  handleStartNewChat();
                }}
                className="bg-slate-900 border border-slate-700 text-xs rounded-xl px-2.5 py-1.5 text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 max-w-[180px] truncate"
              >
                <option value="">All Courses</option>
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Document Scope Selector */}
          {documents.length > 0 && (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-slate-400 flex items-center gap-1">
                <BookOpen className="h-3.5 w-3.5 text-purple-400" />
                Doc:
              </span>
              <select
                value={selectedDocId || ''}
                onChange={(e) => {
                  setSelectedDocId(e.target.value ? Number(e.target.value) : undefined);
                  handleStartNewChat();
                }}
                className="bg-slate-900 border border-slate-700 text-xs rounded-xl px-2.5 py-1.5 text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 max-w-[150px] truncate"
              >
                <option value="">All Uploads</option>
                {documents.map((d) => (
                  <option key={d.id} value={d.id}>
                    {formatDocumentTitle(d.original_filename)}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* New Chat Button */}
          <Button
            size="sm"
            variant="outline"
            onClick={handleStartNewChat}
            icon={<Plus className="h-3.5 w-3.5" />}
            title="Start a new chat thread"
          >
            New Chat
          </Button>

          {/* Reset / Clear Button */}
          {messages.length > 1 && (
            <button
              onClick={handleClearHistory}
              title="Clear all conversation history"
              className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded-lg transition-colors text-xs flex items-center gap-1 border border-slate-700/50"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Chat Messages Viewport */}
      <div className="flex-1 overflow-y-auto space-y-5 pr-2">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex items-start gap-3.5 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.sender === 'tutor' && (
              <div className="h-8 w-8 rounded-xl bg-indigo-600/90 border border-indigo-500/30 flex items-center justify-center text-white shrink-0 shadow mt-1">
                <Bot className="h-4 w-4" />
              </div>
            )}

            <div
              className={`max-w-3xl rounded-2xl p-5 text-sm leading-relaxed shadow-xl ${
                msg.sender === 'user'
                  ? 'bg-indigo-600 text-white rounded-tr-none shadow-indigo-600/20'
                  : 'bg-slate-900/95 border border-slate-800 text-slate-200 rounded-tl-none space-y-4'
              }`}
            >
              {msg.sender === 'user' ? (
                <div className="font-normal whitespace-pre-wrap">{msg.text}</div>
              ) : (
                <div className="space-y-3">
                  <MarkdownRenderer content={msg.text} />

                  {/* Verified Citations List */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="pt-3 border-t border-slate-800 space-y-2">
                      <p className="text-[11px] font-bold text-indigo-400 uppercase tracking-wider flex items-center gap-1.5">
                        <FileText className="h-3.5 w-3.5" />
                        Verified Grounding References:
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {msg.citations.map((c, idx) => (
                          <span
                            key={idx}
                            className="inline-flex items-center gap-1 text-[11px] bg-slate-800/80 text-indigo-300 px-2.5 py-1 rounded-lg border border-slate-700/80 font-mono shadow-sm"
                          >
                            <span>{formatDocumentTitle(c.filename || 'Curriculum')}</span>
                            <span className="text-slate-500">•</span>
                            <span className="text-white font-semibold">Page {c.page_number}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Latency & Provider Telemetry (Subtle) */}
                  {msg.latency && msg.latency > 0 && (
                    <div className="text-[10px] text-slate-500 flex items-center justify-between pt-1">
                      <span>Generated via {msg.provider || 'local model'}</span>
                      <span>~{(msg.latency / 1000).toFixed(2)}s</span>
                    </div>
                  )}
                </div>
              )}
            </div>

            {msg.sender === 'user' && (
              <div className="h-8 w-8 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 shrink-0 mt-1 shadow">
                <User className="h-4 w-4" />
              </div>
            )}
          </div>
        ))}

        {/* Thinking Indicator */}
        {isThinking && (
          <div className="flex items-start gap-3.5">
            <div className="h-8 w-8 rounded-xl bg-indigo-600 flex items-center justify-center text-white shrink-0 mt-1 animate-pulse shadow">
              <Bot className="h-4 w-4" />
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-2xl rounded-tl-none p-4 text-xs text-slate-300 flex items-center gap-3 shadow-xl">
              <Spinner size="sm" />
              <div className="space-y-0.5">
                <p className="font-semibold text-indigo-300">Evaluating inquiry & course grounding...</p>
                <p className="text-[11px] text-slate-500">Retrieving syllabus evidence passages and formulating Socratic response</p>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Dynamic Suggested Question Chips */}
      {suggestedQuestions.length > 0 && !isThinking && (
        <div className="pt-1">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-400 mb-1.5">
            <Sparkles className="h-3 w-3 text-indigo-400" />
            <span>Suggested Inquiries:</span>
          </div>
          <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs no-scrollbar">
            {suggestedQuestions.map((prompt, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleSend(prompt)}
                className="shrink-0 px-3 py-1.5 rounded-full bg-slate-900 hover:bg-indigo-600/20 text-slate-300 hover:text-indigo-300 border border-slate-800 hover:border-indigo-500/40 transition-colors text-left flex items-center gap-1.5"
              >
                <HelpCircle className="h-3 w-3 text-indigo-400 shrink-0" />
                <span className="truncate max-w-[280px]">{prompt}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input Message Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className="relative pt-1"
      >
        <input
          type="text"
          value={inputQuestion}
          onChange={(e) => setInputQuestion(e.target.value)}
          placeholder={
            activeCourse
              ? `Ask a question about ${activeCourse.title} (e.g. 'Can you explain this concept with an analogy?')`
              : "Ask your AI tutor anything about your learning materials..."
          }
          disabled={isThinking}
          className="w-full bg-slate-900/90 border border-slate-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-2xl py-3.5 pl-4 pr-12 text-xs md:text-sm text-white placeholder-slate-500 focus:outline-none shadow-xl"
        />
        <button
          type="submit"
          disabled={!inputQuestion.trim() || isThinking}
          className="absolute right-2.5 top-3.5 p-2 rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shadow-md shadow-indigo-600/30"
          title="Send inquiry"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
};
