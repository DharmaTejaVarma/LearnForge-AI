import React, { useState, useEffect, useRef, useCallback } from 'react';
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
  Clock,
  Search,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  BookOpen,
} from 'lucide-react';

export const Documents: React.FC = () => {
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [reprocessingId, setReprocessingId] = useState<number | null>(null);
  const [expandedDocId, setExpandedDocId] = useState<number | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchTerm), 280);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const fetchDocuments = useCallback(async () => {
    try {
      const data = await documentService.list(debouncedSearch, statusFilter);
      setDocuments(data);
    } catch (err: any) {
      console.error('Failed to load documents:', err);
    } finally {
      setIsLoading(false);
    }
  }, [debouncedSearch, statusFilter]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Auto-refresh while any uploaded document is still finishing background vector indexing
  useEffect(() => {
    const hasPendingIndex = documents.some(
      (d) => d.processing_status === 'processed' || d.processing_status === 'uploaded'
    );
    if (!hasPendingIndex) return;
    const timer = setInterval(fetchDocuments, 5000);
    return () => clearInterval(timer);
  }, [documents, fetchDocuments]);

  const processFile = async (file: File) => {
    setUploadError(null);
    setUploadSuccess(null);
    setIsUploading(true);

    try {
      const doc = await documentService.upload(file);
      setUploadSuccess(`Successfully indexed "${formatDocumentTitle(doc.original_filename)}" (${doc.page_count} pages)`);
      await fetchDocuments();
    } catch (err: any) {
      const msg =
        err.response?.data?.error?.message ||
        err.response?.data?.detail ||
        'Unable to process document. Please ensure it is a valid, readable file.';
      setUploadError(msg);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) await processFile(file);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isUploading) setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (isUploading) return;
    const file = e.dataTransfer.files?.[0];
    if (file) await processFile(file);
  };

  const handleReprocess = async (doc: UploadedDocument) => {
    setReprocessingId(doc.id);
    setUploadError(null);
    setUploadSuccess(null);
    try {
      const updated = await documentService.reprocess(doc.id);
      setUploadSuccess(`Reprocessed & re-indexed "${formatDocumentTitle(updated.original_filename)}".`);
      await fetchDocuments();
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || 'Unable to reprocess document right now.';
      setUploadError(msg);
    } finally {
      setReprocessingId(null);
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
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.txt,.pptx,.md,.markdown"
        onChange={handleFileUpload}
        className="hidden"
      />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-line pb-5">
        <div>
          <h1 className="lf-heading-main">Study Materials</h1>
          <p className="text-sm text-ink-secondary mt-1">
            Upload textbooks, lecture notes, or syllabi to generate interactive courses and study tools.
          </p>
        </div>
        <Button
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
        >
          {isUploading ? <Spinner size="sm" /> : <UploadCloud className="h-4 w-4" />}
          <span>{isUploading ? 'Analyzing & Indexing...' : 'Upload Notes'}</span>
        </Button>
      </div>

      {/* Notifications */}
      {uploadError && (
        <div className="p-4 rounded-[12px] bg-status-danger-bg border border-status-danger-border text-status-danger-text text-sm flex items-start gap-3">
          <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">Document action notice</p>
            <p className="text-xs opacity-90 mt-0.5">{uploadError}</p>
          </div>
        </div>
      )}

      {uploadSuccess && (
        <div className="p-4 rounded-[12px] bg-status-success-bg border border-status-success-border text-status-success-text text-sm flex items-center gap-3">
          <CheckCircle className="h-5 w-5 shrink-0" />
          <span>{uploadSuccess}</span>
        </div>
      )}

      {/* Interactive Drag & Drop Upload Dropzone */}
      <div
        onClick={() => !isUploading && fileInputRef.current?.click()}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`cursor-pointer border-2 border-dashed rounded-[12px] p-8 text-center transition-all duration-200 group shadow-card ${
          isDragging
            ? 'border-accent bg-accent-soft scale-[1.01]'
            : 'border-line-strong hover:border-brand bg-surface hover:bg-hoverbg'
        }`}
      >
        <div className="h-14 w-14 rounded-[12px] bg-brand-soft border border-brand-soft-border flex items-center justify-center mx-auto text-brand group-hover:scale-105 transition-transform">
          {isUploading ? <Spinner size="md" /> : <FileUp className="h-7 w-7" />}
        </div>
        <h3 className="lf-heading-card mt-4">
          {isDragging ? 'Drop file to upload & index' : 'Click to upload or drag & drop course notes'}
        </h3>
        <p className="text-xs text-ink-secondary mt-1 max-w-sm mx-auto">
          Supported formats: PDF, DOCX, TXT, PPTX, and Markdown documents (up to 25MB)
        </p>
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          <span className="text-xs font-medium px-2.5 py-0.5 rounded-full bg-subtle text-ink-secondary border border-line">
            Structure-Aware RAG Indexing
          </span>
          <span className="text-xs font-medium px-2.5 py-0.5 rounded-full bg-subtle text-ink-secondary border border-line">
            Duplicate Protection
          </span>
          <span className="text-xs font-medium px-2.5 py-0.5 rounded-full bg-subtle text-ink-secondary border border-line">
            1-on-1 AI Tutor Ready
          </span>
        </div>
      </div>

      {/* Search & Filter Controls */}
      <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
        <div className="relative flex-1 max-w-md">
          <Search className="h-4 w-4 text-ink-secondary absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search uploaded files..."
            aria-label="Search uploaded documents"
            className="lf-control w-full pl-9 pr-3 py-2 text-sm"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="Filter by indexing status"
          className="lf-control px-3 py-2 text-sm"
        >
          <option value="">All Statuses</option>
          <option value="indexed">Ready for Learning</option>
          <option value="processed">Processed</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {/* Document Library */}
      <Card
        title={`Uploaded Materials (${documents.length})`}
        subtitle="Course assets indexed and ready for learning generation"
      >
        {isLoading ? (
          <Spinner size="md" />
        ) : documents.length === 0 ? (
          <div className="py-12 text-center space-y-3">
            <div className="h-12 w-12 rounded-full bg-subtle border border-line flex items-center justify-center mx-auto text-ink-secondary">
              <FileText className="h-6 w-6" />
            </div>
            <h4 className="text-sm font-semibold text-ink-primary">No study materials found</h4>
            <p className="text-xs text-ink-secondary max-w-xs mx-auto">
              Upload your lecture notes or syllabus to start generating chapters, lessons, and flashcards.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-line">
            {documents.map((doc) => {
              const hasStructure = Array.isArray(doc.structure) && doc.structure.length > 0;
              const isExpanded = expandedDocId === doc.id;
              return (
                <div key={doc.id} className="py-4 space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 group">
                    <div className="flex items-start gap-3.5">
                      <div className="h-10 w-10 rounded-[10px] bg-brand-soft border border-brand-soft-border flex items-center justify-center text-brand shrink-0">
                        <FileText className="h-5 w-5" />
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-ink-primary group-hover:text-brand transition-colors">
                          {formatDocumentTitle(doc.original_filename)}
                        </h4>
                        <p className="text-[11px] text-ink-secondary truncate max-w-xs">
                          {doc.original_filename}
                        </p>
                        <div className="flex flex-wrap items-center gap-3 text-xs text-ink-secondary mt-1">
                          <span>{formatFileSize(doc.file_size)}</span>
                          <span>•</span>
                          <span>{doc.page_count} {doc.page_count === 1 ? 'page' : 'pages'}</span>
                          <span>•</span>
                          <span>{doc.character_count.toLocaleString()} chars</span>
                          <span>•</span>
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatFriendlyDate(doc.created_at)}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 self-end sm:self-center">
                      {hasStructure && (
                        <button
                          type="button"
                          onClick={() => setExpandedDocId(isExpanded ? null : doc.id)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-[10px] text-xs font-medium bg-subtle hover:bg-hoverbg text-ink-primary border border-line transition-colors"
                        >
                          {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                          Sections ({doc.structure!.length})
                        </button>
                      )}

                      <span
                        className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                          doc.processing_status === 'processed' || doc.processing_status === 'indexed'
                            ? 'bg-status-success-bg text-status-success-text border-status-success-border'
                            : doc.processing_status === 'failed'
                            ? 'bg-status-danger-bg text-status-danger-text border-status-danger-border'
                            : 'bg-status-warning-bg text-status-warning-text border-status-warning-border'
                        }`}
                      >
                        {doc.processing_status === 'indexed' ? 'Ready for Learning' : doc.processing_status.toUpperCase()}
                      </span>

                      <button
                        type="button"
                        onClick={() => handleReprocess(doc)}
                        disabled={reprocessingId === doc.id}
                        className="p-2 rounded-[10px] text-ink-secondary hover:text-brand hover:bg-hoverbg transition-colors disabled:opacity-50"
                        title="Reprocess and re-index document"
                      >
                        <RefreshCw className={`h-4 w-4 ${reprocessingId === doc.id ? 'animate-spin' : ''}`} />
                      </button>

                      <button
                        type="button"
                        onClick={() => handleDelete(doc.id, doc.original_filename)}
                        className="p-2 rounded-[10px] text-ink-secondary hover:text-status-danger-text hover:bg-status-danger-bg transition-colors"
                        title="Delete document"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>

                  {isExpanded && hasStructure && (
                    <div className="pl-4 border-l-2 border-accent space-y-1.5 text-xs text-ink-primary bg-subtle rounded-r-[12px] p-3.5">
                      <p className="text-xs font-semibold uppercase tracking-wider text-accent flex items-center gap-1.5 mb-2">
                        <BookOpen className="h-3.5 w-3.5" />
                        Extracted Document Outline
                      </p>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5 max-h-48 overflow-y-auto pr-1">
                        {doc.structure!.slice(0, 24).map((sec, idx) => (
                          <div key={idx} className="flex items-center justify-between bg-surface px-2.5 py-1.5 rounded-[10px] border border-line">
                            <span className="truncate pr-2 text-ink-primary">{sec.title}</span>
                            {sec.page_start && (
                              <span className="text-[11px] text-ink-secondary font-mono shrink-0">
                                p.{sec.page_start}{sec.page_end && sec.page_end > sec.page_start ? `–${sec.page_end}` : ''}
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
};
