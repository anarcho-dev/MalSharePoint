import { useState, useCallback, useRef, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  FileText,
  X,
  Check,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import clsx from 'clsx';
import { filesApi } from '../api/files';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function Upload() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState('');
  const [isPublic, setIsPublic] = useState(false);
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);

  const selectFile = (f: File) => setFile(f);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) selectFile(dropped);
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    setProgress(0);
    setResult(null);

    const fd = new FormData();
    fd.append('file', file);
    fd.append('description', description);
    fd.append('tags', tags);
    fd.append('is_public', String(isPublic));

    try {
      const { data } = await filesApi.upload(fd, setProgress);
      setResult({ success: true, message: data.message });
      setTimeout(() => navigate('/files'), 1500);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { error?: string } } })?.response?.data?.error ??
        'Upload failed';
      setResult({ success: false, message: msg });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Upload File</h1>
        <p className="text-sm text-slate-500 mt-1">Add a new payload to the repository</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Drop zone */}
        <div
          className={clsx(
            'relative border-2 border-dashed rounded-xl p-10 text-center transition-all cursor-pointer',
            isDragging && 'border-red-500 bg-red-500/5 scale-[1.01]',
            !isDragging && !file && 'border-slate-700 hover:border-slate-600 bg-slate-900/40',
            file && 'border-emerald-500/40 bg-emerald-500/5'
          )}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => !file && fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) selectFile(f);
            }}
          />

          {file ? (
            <div className="flex items-center justify-center gap-3">
              <FileText className="text-emerald-400 flex-shrink-0" size={22} />
              <div className="text-left min-w-0">
                <p className="text-sm font-medium text-slate-100 truncate max-w-[280px]">
                  {file.name}
                </p>
                <p className="text-xs text-slate-500 mt-0.5">{formatBytes(file.size)}</p>
              </div>
              <button
                type="button"
                className="ml-2 p-1 rounded text-slate-500 hover:text-red-400 hover:bg-red-400/10 transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                  if (fileInputRef.current) fileInputRef.current.value = '';
                }}
              >
                <X size={15} />
              </button>
            </div>
          ) : (
            <>
              <UploadCloud
                className="mx-auto text-slate-700 mb-3"
                size={36}
              />
              <p className="text-sm text-slate-400">
                Drag & drop a file here, or{' '}
                <span className="text-red-400 hover:text-red-300">click to browse</span>
              </p>
              <p className="text-xs text-slate-600 mt-1">
                Executables, scripts, archives, documents
              </p>
            </>
          )}
        </div>

        {/* Description */}
        <div>
          <label className="label">Description</label>
          <textarea
            className="input resize-none h-24"
            placeholder="Describe this payload, its purpose, or campaign notes…"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        {/* Tags */}
        <div>
          <label className="label">Tags</label>
          <input
            type="text"
            className="input"
            placeholder="e.g. ransomware, reverse-shell, c2, loader (comma-separated)"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
          />
        </div>

        {/* Public toggle */}
        <div className="flex items-center justify-between p-4 rounded-xl bg-slate-900 border border-slate-800">
          <div>
            <p className="text-sm font-medium text-slate-100">Public Access</p>
            <p className="text-xs text-slate-500 mt-0.5">
              Visible and downloadable by all authenticated users
            </p>
          </div>
          <button
            type="button"
            onClick={() => setIsPublic((v) => !v)}
            className={clsx(
              'relative w-11 h-6 rounded-full transition-colors flex-shrink-0',
              isPublic ? 'bg-red-600' : 'bg-slate-700'
            )}
            role="switch"
            aria-checked={isPublic}
          >
            <span
              className={clsx(
                'absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform',
                isPublic ? 'translate-x-5' : 'translate-x-0'
              )}
            />
          </button>
        </div>

        {/* Progress bar */}
        {uploading && (
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs text-slate-500">
              <span>Uploading…</span>
              <span>{progress}%</span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-red-600 transition-all duration-200"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Result message */}
        {result && (
          <div
            className={clsx(
              'flex items-center gap-2.5 px-4 py-3 rounded-lg border text-sm',
              result.success
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                : 'bg-red-500/10 border-red-500/30 text-red-400'
            )}
          >
            {result.success ? <Check size={15} /> : <AlertCircle size={15} />}
            {result.message}
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          className="btn-primary"
          disabled={!file || uploading}
        >
          {uploading ? (
            <Loader2 size={15} className="animate-spin" />
          ) : (
            <UploadCloud size={15} />
          )}
          {uploading ? `Uploading ${progress}%` : 'Upload File'}
        </button>
      </form>
    </div>
  );
}
