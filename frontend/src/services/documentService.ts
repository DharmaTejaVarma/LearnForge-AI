import { api } from './api';

export interface DocumentSection {
  title: string;
  level?: number;
  page_start?: number;
  page_end?: number;
}

export interface UploadedDocument {
  id: number;
  user_id: number;
  original_filename: string;
  file_size: number;
  mime_type: string;
  page_count: number;
  character_count: number;
  processing_status: 'uploaded' | 'processed' | 'indexed' | 'failed';
  error_message?: string | null;
  structure?: DocumentSection[] | null;
  created_at: string;
  updated_at: string;
}

export const documentService = {
  async upload(file: File): Promise<UploadedDocument> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<UploadedDocument>('/documents/upload', formData, {
      timeout: 180000,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  async list(search?: string, statusFilter?: string): Promise<UploadedDocument[]> {
    const params: Record<string, string> = {};
    if (search && search.trim()) params.search = search.trim();
    if (statusFilter) params.status = statusFilter;
    const response = await api.get<UploadedDocument[]>('/documents', { params });
    return response.data;
  },

  async get(id: number): Promise<UploadedDocument> {
    const response = await api.get<UploadedDocument>(`/documents/${id}`);
    return response.data;
  },

  async reprocess(id: number): Promise<UploadedDocument> {
    const response = await api.post<UploadedDocument>(`/documents/${id}/reprocess`, {}, { timeout: 180000 });
    return response.data;
  },

  async delete(id: number): Promise<{ message: string; document_id: number }> {
    const response = await api.delete(`/documents/${id}`);
    return response.data;
  },
};
