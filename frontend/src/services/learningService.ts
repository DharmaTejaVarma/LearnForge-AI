import { api } from './api';

export interface Citation {
  document_id: number;
  filename?: string;
  page_number: number;
  similarity_score: number;
}

export interface TutorResponse {
  answer: string;
  citations: Citation[];
  provider_used: string;
  latency_ms: number;
  conversation_id?: string;
  intent?: string;
}

export interface TutorConversationItem {
  id: number;
  conversation_id?: string;
  question: string;
  answer: string;
  citations: Citation[];
  intent?: string;
  created_at: string;
}

export interface Flashcard {
  id: number;
  user_id: number;
  course_id?: number;
  document_id?: number;
  front_prompt: string;
  back_answer: string;
  review_count: number;
  mastery_level: string;
  last_reviewed_at?: string;
}

export interface Question {
  id: number;
  question_text: string;
  options: string[];
  correct_answer: string;
  explanation?: string;
  difficulty: string;
}

export interface Quiz {
  id: number;
  title: string;
  description?: string;
  questions: Question[];
  created_at: string;
}

export interface QuizAttempt {
  id: number;
  quiz_id: number;
  score_percentage: number;
  total_questions: number;
  correct_answers_count: number;
  feedback?: string;
}

export interface QuestionResult {
  question_id: number;
  question_text: string;
  options: string[];
  correct_answer: string;
  selected_answer: string;
  is_correct: boolean;
  explanation: string;
}

export interface QuizAttemptDetail extends QuizAttempt {
  question_results?: QuestionResult[];
}

export interface ProgressStats {
  user_id: number;
  total_courses: number;
  total_documents: number;
  completed_lessons: number;
  total_lessons: number;
  flashcards_mastered: number;
  total_flashcards: number;
  quizzes_taken: number;
  average_quiz_score: number;
  overall_mastery_percentage: number;
  weak_topics: string[];
}

export const learningService = {
  async askTutor(
    question: string,
    documentId?: number,
    courseId?: number,
    lessonId?: number,
    conversationId?: string,
  ): Promise<TutorResponse> {
    const res = await api.post<TutorResponse>('/tutor/chat', {
      question,
      document_id: documentId,
      course_id: courseId,
      lesson_id: lessonId,
      conversation_id: conversationId,
    });
    return res.data;
  },

  async getTutorHistory(
    documentId?: number,
    courseId?: number,
    conversationId?: string,
  ): Promise<TutorConversationItem[]> {
    const params: Record<string, any> = {};
    if (documentId) params.document_id = documentId;
    if (courseId) params.course_id = courseId;
    if (conversationId) params.conversation_id = conversationId;
    const res = await api.get<TutorConversationItem[]>('/tutor/history', { params });
    return res.data;
  },

  async clearTutorHistory(
    documentId?: number,
    courseId?: number,
    conversationId?: string,
  ): Promise<void> {
    const params: Record<string, any> = {};
    if (documentId) params.document_id = documentId;
    if (courseId) params.course_id = courseId;
    if (conversationId) params.conversation_id = conversationId;
    await api.delete('/tutor/history', { params });
  },

  async getTutorSuggestions(
    courseId?: number,
    lessonId?: number,
  ): Promise<string[]> {
    const params: Record<string, any> = {};
    if (courseId) params.course_id = courseId;
    if (lessonId) params.lesson_id = lessonId;
    const res = await api.get<{ suggestions: string[] }>('/tutor/suggestions', { params });
    return res.data.suggestions || [];
  },

  async generateFlashcards(
    documentId?: number,
    courseId?: number,
    count = 5,
    difficulty = 'medium',
  ): Promise<Flashcard[]> {
    const res = await api.post<Flashcard[]>('/flashcards/generate', {
      document_id: documentId,
      course_id: courseId,
      count,
      difficulty,
    });
    return res.data;
  },

  async listFlashcards(
    courseId?: number,
    documentId?: number,
    masteryLevel?: string,
  ): Promise<Flashcard[]> {
    const params: Record<string, any> = {};
    if (courseId) params.course_id = courseId;
    if (documentId) params.document_id = documentId;
    if (masteryLevel) params.mastery_level = masteryLevel;
    const res = await api.get<Flashcard[]>('/flashcards', { params });
    return res.data;
  },

  async reviewFlashcard(id: number, mastered: boolean): Promise<Flashcard> {
    const res = await api.post<Flashcard>(`/flashcards/${id}/review`, { mastered });
    return res.data;
  },

  async deleteFlashcard(id: number): Promise<{ message: string; id: number }> {
    const res = await api.delete<{ message: string; id: number }>(`/flashcards/${id}`);
    return res.data;
  },

  async clearFlashcards(
    courseId?: number,
    documentId?: number,
  ): Promise<{ message: string }> {
    const params: Record<string, any> = {};
    if (courseId) params.course_id = courseId;
    if (documentId) params.document_id = documentId;
    const res = await api.delete<{ message: string }>('/flashcards', { params });
    return res.data;
  },

  async generateQuiz(
    documentId?: number,
    courseId?: number,
    count = 5,
    difficulty = 'medium',
  ): Promise<Quiz> {
    const res = await api.post<Quiz>('/quizzes/generate', {
      document_id: documentId,
      course_id: courseId,
      question_count: count,
      difficulty,
    });
    return res.data;
  },

  async submitQuiz(
    quizId: number,
    answers: Record<number, string>,
  ): Promise<QuizAttemptDetail> {
    const res = await api.post<QuizAttemptDetail>(`/quizzes/${quizId}/submit`, { answers });
    return res.data;
  },

  async deleteQuiz(quizId: number): Promise<{ message: string; id: number }> {
    const res = await api.delete<{ message: string; id: number }>(`/quizzes/${quizId}`);
    return res.data;
  },

  async getProgress(): Promise<ProgressStats> {
    const res = await api.get<ProgressStats>('/progress/stats');
    return res.data;
  },
};
