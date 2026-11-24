import { api } from './api';

export interface Lesson {
  id: number;
  topic_id: number;
  title: string;
  content: string;
  summary?: string;
  key_takeaways?: string[];
  source_pages?: number[];
  is_completed: boolean;
  page_start?: number;
  page_end?: number;
  generation_status?: string;
  generation_error?: string;
}

export interface Topic {
  id: number;
  chapter_id: number;
  title: string;
  order_index: number;
  lesson?: Lesson;
}

export interface Chapter {
  id: number;
  course_id: number;
  title: string;
  description?: string;
  order_index: number;
  topics: Topic[];
}

export interface Course {
  id: number;
  user_id: number;
  document_id?: number;
  title: string;
  description: string;
  difficulty_level: string;
  estimated_duration_hours: number;
  learning_objectives: string[];
  created_at: string;
  chapters?: Chapter[];
}

export const courseService = {
  async list(): Promise<Course[]> {
    const res = await api.get<Course[]>('/courses');
    return res.data;
  },

  async get(id: number): Promise<Course> {
    const res = await api.get<Course>(`/courses/${id}`);
    return res.data;
  },

  async generate(documentId: number, difficulty = 'intermediate', targetChapters = 3): Promise<Course> {
    const res = await api.post<Course>('/courses/generate', {
      document_id: documentId,
      difficulty_level: difficulty,
      target_chapters_count: targetChapters,
    });
    return res.data;
  },

  async delete(id: number): Promise<{ message: string }> {
    const res = await api.delete(`/courses/${id}`);
    return res.data;
  },

  async getLesson(lessonId: number): Promise<Lesson> {
    const res = await api.get<Lesson>(`/lessons/${lessonId}`);
    return res.data;
  },

  async toggleComplete(lessonId: number): Promise<Lesson> {
    const res = await api.post<Lesson>(`/lessons/${lessonId}/toggle-complete`);
    return res.data;
  },

  async regenerateLesson(lessonId: number): Promise<Lesson> {
    const res = await api.post<Lesson>(`/lessons/${lessonId}/regenerate`);
    return res.data;
  },
};
