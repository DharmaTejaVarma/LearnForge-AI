import { api } from './api';

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
  created_at: string;
  updated_at: string;
}

export const documentService = {
  async upload(file: File): Promise<UploadedDocument> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<UploadedDocument>('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  async list(): Promise<UploadedDocument[]> {
    const response = await api.get<UploadedDocument[]>('/documents');
    return response.data;
  },

  async get(id: number): Promise<UploadedDocument> {
    const response = await api.get<UploadedDocument>(`/documents/${id}`);
    return response.data;
  },

  async delete(id: number): Promise<{ message: string; document_id: number }> {
    const response = await api.delete(`/documents/${id}`);
    return response.data;
  },
};
