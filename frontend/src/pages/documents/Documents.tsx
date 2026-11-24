import React, { useState, useEffect, useRef } from 'react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Spinner } from '../../components/common/Spinner';
import { documentService, UploadedDocument } from '../../services/documentService';
import { formatDocumentTitle, formatFileSize, formatFriendlyDate } from '../../utils/formatters';
import { 
  UploadCloud, 
  FileText, 
  Trash2, 
  CheckCircle, 
  AlertCircle, 
  FileUp, 
  Clock
} from 'lucide-react';

export const Documents: React.FC = () => {
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchDocuments = async () => {
    try {
      const data = await documentService.list();
      setDocuments(data);
    } catch (err: any) {
      console.error('Failed to load documents:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadError(null);
    setUploadSuccess(null);
    setIsUploading(true);

    try {
      const doc = await documentService.upload(file);
      setUploadSuccess(`Successfully added "${formatDocumentTitle(doc.original_filename)}" (${doc.page_count} pages)`);
      await fetchDocuments();
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || 'Unable to process document. Please ensure it has selectable text.';
      setUploadError(msg);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDelete = async (id: number, filename: string) => {
    const cleanName = formatDocumentTitle(filename);
    if (!window.confirm(`Are you sure you want to remove "${cleanName}"?`)) return;

    try {
      await documentService.delete(id);
      await fetchDocuments();
    } catch (err: any) {
      alert('Unable to delete document right now. Please try again.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.txt,.pptx,.md,.markdown"
        onChange={handleFileUpload}
        className="hidden"
      />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Study Materials</h1>
          <p className="text-sm text-slate-400 mt-1">
            Upload textbooks, lecture notes, or syllabi to generate interactive courses and study tools.
          </p>
        </div>
        <Button
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          className="gap-2 shadow-lg shadow-indigo-600/20"
        >
          {isUploading ? <Spinner size="sm" /> : <UploadCloud className="h-4 w-4" />}
          <span>{isUploading ? 'Analyzing...' : 'Upload Notes'}</span>
        </Button>
      </div>

      {/* Notifications */}
      {uploadError && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm flex items-start gap-3">
          <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">Upload failed</p>
            <p className="text-xs text-rose-300/80 mt-0.5">{uploadError}</p>
          </div>
        </div>
      )}

      {uploadSuccess && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm flex items-center gap-3">
          <CheckCircle className="h-5 w-5 shrink-0" />
          <span>{uploadSuccess}</span>
        </div>
      )}

      {/* Upload Dropzone */}
      <div
        onClick={() => fileInputRef.current?.click()}
        className="cursor-pointer border-2 border-dashed border-slate-700 hover:border-indigo-500/60 rounded-2xl p-8 text-center bg-slate-900/40 hover:bg-slate-900/80 transition-all duration-200 group"
      >
        <div className="h-14 w-14 rounded-2xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center mx-auto text-indigo-400 group-hover:scale-110 transition-transform">
          <FileUp className="h-7 w-7" />
        </div>
        <h3 className="text-base font-semibold text-white mt-4">
          Click to upload or drag & drop course notes
        </h3>
        <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
          Supported formats: PDF, DOCX, TXT, PPTX, and Markdown documents (up to 25MB)
        </p>
        <div className="mt-4 flex justify-center gap-2">
          <span className="text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
            PDF, DOCX, TXT, PPTX & Markdown
          </span>
          <span className="text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
            Smart Course Generation
          </span>
          <span className="text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
            1-on-1 AI Tutor Ready
          </span>
        </div>
      </div>

      {/* Document Library */}
      <Card
        title={`Uploaded Materials (${documents.length})`}
        subtitle="Course assets indexed and ready for learning generation"
        className="bg-slate-900/80 border-slate-800"
      >
        {isLoading ? (
          <Spinner size="md" />
        ) : documents.length === 0 ? (
          <div className="py-12 text-center space-y-3">
            <div className="h-12 w-12 rounded-full bg-slate-800 flex items-center justify-center mx-auto text-slate-500">
              <FileText className="h-6 w-6" />
            </div>
            <h4 className="text-sm font-semibold text-slate-300">No study materials uploaded yet</h4>
            <p className="text-xs text-slate-500 max-w-xs mx-auto">
              Upload your lecture notes or syllabus to start generating chapters, lessons, and flashcards.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-slate-800">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 group"
              >
                <div className="flex items-start gap-3.5">
                  <div className="h-10 w-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shrink-0">
                    <FileText className="h-5 w-5" />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-white group-hover:text-indigo-400 transition-colors">
                      {formatDocumentTitle(doc.original_filename)}
                    </h4>
                    <p className="text-[11px] text-slate-500 truncate max-w-xs">
                      {doc.original_filename}
                    </p>
                    <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 mt-1">
                      <span>{formatFileSize(doc.file_size)}</span>
                      <span>•</span>
                      <span>{doc.page_count} {doc.page_count === 1 ? 'page' : 'pages'}</span>
                      <span>•</span>
                      <span className="flex items-center gap-1 text-slate-500">
                        <Clock className="h-3 w-3" />
                        {formatFriendlyDate(doc.created_at)}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 self-end sm:self-center">
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                      doc.processing_status === 'processed' || doc.processing_status === 'indexed'
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        : doc.processing_status === 'failed'
                        ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                        : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                    }`}
                  >
                    {doc.processing_status === 'indexed' ? 'Ready for Learning' : doc.processing_status.toUpperCase()}
                  </span>

                  <button
                    onClick={() => handleDelete(doc.id, doc.original_filename)}
                    className="p-2 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                    title="Delete document"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};
