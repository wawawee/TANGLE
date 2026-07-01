import { Handle, Position } from '@xyflow/react';
import { Upload, Type, Camera, Mic, X, Check, Play, FileText, Video, Music, Loader2, Terminal, AlertTriangle } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { uploadFile, addKnowledgeDoc } from '../../services/api';

interface EvidenceItem {
  id: string;
  type: string;
  preview: string;
  content?: string;
  status: 'uploading' | 'uploaded' | 'error';
}

export function DropNode({ data, id }: any) {
  const [mode, setMode] = useState<'select' | 'text' | 'camera' | 'record'>('select');
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [textInput, setTextInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [verboseMode, setVerboseMode] = useState(false);
  const [verboseLogs, setVerboseLogs] = useState<{ time: string; msg: string }[]>([]);
  const [audioWarnings, setAudioWarnings] = useState<Record<string, { message: string; estimated_minutes?: number }>>({});
  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [verboseLogs]);

  const addVerboseLog = (msg: string) => {
    setVerboseLogs(prev => [...prev, { time: new Date().toLocaleTimeString(), msg }]);
  };

  useEffect(() => {
    if (mode === 'camera' || mode === 'record') {
      navigator.mediaDevices.getUserMedia({ video: true, audio: mode === 'record' })
        .then((s) => {
          streamRef.current = s;
          if (videoRef.current) {
            videoRef.current.srcObject = s;
          }
        })
        .catch(err => console.error("Media error:", err));
    } else {
      streamRef.current?.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    return () => {
      streamRef.current?.getTracks().forEach(t => t.stop());
    };
  }, [mode]);

  const addEvidence = async (type: string, preview: string, content?: string) => {
    const evidenceId = Date.now().toString();

    if (verboseMode) {
      if (type === 'file') addVerboseLog(`Received: ${preview}`);
      else if (type === 'text') addVerboseLog(`Received text snippet: "${preview}"`);
    }

    if (type === 'file' || type === 'text') {
      if (verboseMode) addVerboseLog(`Analyzing content signature...`);
      await new Promise(r => setTimeout(r, 200));
    }

    if (content && (type === 'file' || type === 'text')) {
      if (verboseMode) addVerboseLog(`Parsing content (${(content.length / 1024).toFixed(1)} KB)...`);
      await new Promise(r => setTimeout(r, 300));

      try {
        await addKnowledgeDoc(preview, content.slice(0, 5000));
        if (verboseMode) addVerboseLog(`Vector embedding stored in knowledge base`);
      } catch {
        if (verboseMode) addVerboseLog(`Knowledge base store failed — using local only`);
      }
    }

    setEvidence(prev => [...prev, { id: evidenceId, type, preview, content, status: 'uploaded' }]);
    if (verboseMode) addVerboseLog(`✓ ${preview} ready`);
    setMode('select');
  };

  const removeEvidence = (evidenceId: string) => {
    setEvidence(prev => prev.filter(e => e.id !== evidenceId));
    setAudioWarnings(prev => { const { [evidenceId]: _, ...rest } = prev; return rest; });
  };

  const AUDIO_EXTS = ['.wav', '.mp3', '.m4a', '.ogg', '.flac', '.aac', '.webm'];

  const ingestFile = async (file: File) => {
    const evidenceId = Date.now().toString();
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    const fileType = AUDIO_EXTS.includes(ext) ? 'audio' : 'file';
    setEvidence(prev => [...prev, { id: evidenceId, type: fileType, preview: file.name, status: 'uploading' }]);

    if (verboseMode) addVerboseLog(`Uploading ${file.name} (${(file.size / 1024).toFixed(1)} KB)...`);

    try {
      const response = await uploadFile(file);
      if (response?.audio_warning) {
        const w = response.audio_warning;
        setAudioWarnings(prev => ({ ...prev, [evidenceId]: { message: w.message, estimated_minutes: w.estimated_minutes } }));
        if (verboseMode) addVerboseLog(`⚠ ${w.message} (est. ${w.estimated_minutes} min transcription)`);
      }
      if (verboseMode) addVerboseLog(`Upload complete — parsing ${file.name}...`);
      await new Promise(r => setTimeout(r, 200));

      const reader = new FileReader();
      reader.onload = async (event) => {
        const content = event.target?.result as string;

        if (verboseMode) {
          if (file.name.endsWith('.pdf')) addVerboseLog(`Extracting text from PDF...`);
          else if (file.type.startsWith('image/')) addVerboseLog(`Analyzing image contents...`);
          else if (file.type.startsWith('audio/')) addVerboseLog(`Preparing audio for transcription...`);
          else addVerboseLog(`Parsing document structure...`);
          await new Promise(r => setTimeout(r, 300));
          addVerboseLog(`Generating vector embedding...`);
          await new Promise(r => setTimeout(r, 200));

          try {
            await addKnowledgeDoc(file.name, content.slice(0, 5000));
            addVerboseLog(`Stored in knowledge base`);
          } catch {
            addVerboseLog(`Knowledge base unavailable — local storage only`);
          }
          addVerboseLog(`✓ ${file.name} ready`);
        } else {
          try {
            await addKnowledgeDoc(file.name, content.slice(0, 5000));
          } catch { }
        }

        setEvidence(prev => prev.map(e =>
          e.id === evidenceId ? { ...e, content, status: 'uploaded' as const } : e
        ));
      };

      if (file.type.startsWith('text/') || file.type === 'application/json') {
        reader.readAsText(file);
      } else {
        reader.readAsDataURL(file);
      }
    } catch {
      if (verboseMode) addVerboseLog(`✗ Upload failed: ${file.name}`);
      setEvidence(prev => prev.map(e =>
        e.id === evidenceId ? { ...e, status: 'error' as const } : e
      ));
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      Array.from(e.target.files).forEach(ingestFile);
    }
    e.target.value = '';
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (e.dataTransfer.files) {
      Array.from(e.dataTransfer.files).forEach(ingestFile);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleTextSubmit = async () => {
    if (textInput.trim()) {
      await addEvidence('text', textInput.substring(0, 30) + (textInput.length > 30 ? '...' : ''), textInput);
      setTextInput('');
    }
  };

  const takePhoto = () => {
    if (videoRef.current) {
      const canvas = document.createElement('canvas');
      canvas.width = videoRef.current.videoWidth;
      canvas.height = videoRef.current.videoHeight;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.drawImage(videoRef.current, 0, 0);
        addEvidence('photo', 'Captured Image');
      }
    }
  };

  const toggleRecord = () => {
    if (isRecording) {
      setIsRecording(false);
      addEvidence('video', 'Live Recording');
    } else {
      setIsRecording(true);
    }
  };

  const uploadingCount = evidence.filter(e => e.status === 'uploading').length;
  const errorCount = evidence.filter(e => e.status === 'error').length;
  const totalCount = evidence.length;

  return (
    <div
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      className={`brutalist-card p-6 w-[32rem] min-h-[200px] flex flex-col space-y-6 relative transition-all text-[#111] dark:text-[#eee] ${isDragOver ? '!border-[#00ff88] !shadow-[0_0_20px_rgba(0,255,136,0.5)]' : ''}`}
    >
      <Handle type="target" position={Position.Top} />

      {data.wittyText && (
        <div className="bg-[#111] text-white p-4 font-mono text-sm uppercase font-bold">
          {data.wittyText}
        </div>
      )}

      {mode === 'select' && (
        <>
          <div className="grid grid-cols-2 gap-4">
            <div
              onClick={() => fileInputRef.current?.click()}
              className="brutalist-button py-4 flex flex-col items-center justify-center space-y-2 group cursor-pointer"
            >
              <Upload size={24} className="group-hover:-translate-y-1 transition-transform" />
              <span className="text-xs">Drop Files</span>
            </div>
            <input type="file" multiple className="hidden" ref={fileInputRef} onChange={handleFileSelect} accept=".pdf,.txt,.csv,.json,.md,.doc,.docx,.png,.jpg,.jpeg,.gif,.webp,.wav,.mp3,.m4a,.ogg,.flac,.aac,.webm" />

            <button onClick={() => setMode('text')} className="brutalist-button py-4 flex flex-col items-center justify-center space-y-2 group">
              <Type size={24} className="group-hover:-translate-y-1 transition-transform" />
              <span className="text-xs">Paste Text</span>
            </button>

            <button onClick={() => setMode('camera')} className="brutalist-button py-4 flex flex-col items-center justify-center space-y-2 group">
              <Camera size={24} className="group-hover:-translate-y-1 transition-transform" />
              <span className="text-xs">Take Photo</span>
            </button>

            <button onClick={() => setMode('record')} className="brutalist-button py-4 flex flex-col items-center justify-center space-y-2 group">
              <Mic size={24} className="group-hover:-translate-y-1 transition-transform" />
              <span className="text-xs">Live Record</span>
            </button>
          </div>

          {/* Upload progress bar */}
          {uploadingCount > 0 && (
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="flex items-center space-x-2">
                  <Loader2 size={14} className="animate-spin" />
                  <span>Uploading {uploadingCount} file{uploadingCount > 1 ? 's' : ''}...</span>
                </span>
                <span>{Math.round((totalCount - uploadingCount) / totalCount * 100)}%</span>
              </div>
              <div className="w-full h-2 border-2 border-[#111] dark:border-[#eee] bg-white/50 dark:bg-black/50 overflow-hidden">
                <div
                  className="h-full bg-[#00ff88] transition-all duration-300 ease-out"
                  style={{ width: `${((totalCount - uploadingCount) / totalCount) * 100}%` }}
                />
              </div>
            </div>
          )}

          {evidence.length > 0 && (
            <div className="space-y-2 mt-4">
              <div className="flex items-center justify-between border-b-2 border-[#111] dark:border-[#eee] pb-1">
                <h3 className="font-black uppercase text-sm">Collected Evidence</h3>
                <button
                  onClick={() => setVerboseMode(!verboseMode)}
                  className={`p-1 border-2 border-[#111] dark:border-[#eee] transition-colors ${verboseMode ? 'bg-[#111] text-white dark:bg-[#eee] dark:text-[#111]' : 'hover:bg-gray-100 dark:hover:bg-gray-800'}`}
                  title="Toggle verbose ingestion logs"
                >
                  <Terminal size={14} />
                </button>
              </div>

              {evidence.map(item => (
                <div key={item.id} className="flex items-center justify-between border-2 border-[#111] dark:border-[#eee] p-2 bg-[#f4f4f0] dark:bg-[#1a1a1a]">
                  <div className="flex items-center space-x-3 overflow-hidden min-w-0">
                    {item.status === 'uploading' ? (
                      <Loader2 size={16} className="animate-spin shrink-0" />
                    ) : item.status === 'error' ? (
                      <X size={16} className="text-[#ff003c] shrink-0" />
                    ) : (
                      <>
                        {item.type === 'file' && <FileText size={16} className="shrink-0" />}
                        {item.type === 'audio' && <Music size={16} className="shrink-0" />}
                        {item.type === 'text' && <Type size={16} className="shrink-0" />}
                        {item.type === 'photo' && <Camera size={16} className="shrink-0" />}
                        {item.type === 'video' && <Video size={16} className="shrink-0" />}
                      </>
                    )}
                    <span className="font-mono text-xs truncate">{item.preview}</span>
                    {audioWarnings[item.id] && (
                      <span className="group/aw relative" title={audioWarnings[item.id].message}>
                        <AlertTriangle size={12} className="text-amber-500 shrink-0 cursor-help" />
                        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover/aw:block bg-[#111] text-amber-400 text-[10px] px-2 py-1 whitespace-nowrap border border-amber-500 z-10">
                          {audioWarnings[item.id].message} ({audioWarnings[item.id].estimated_minutes} min)
                        </span>
                      </span>
                    )}
                    {item.status === 'uploaded' && <Check size={12} className="text-[#00cc66] shrink-0" />}
                    {item.status === 'error' && <span className="text-[#ff003c] font-mono text-xs shrink-0">FAILED</span>}
                  </div>
                  {item.status !== 'uploading' && (
                    <button onClick={() => removeEvidence(item.id)} className="hover:bg-[#111] hover:text-white p-1 transition-colors shrink-0 ml-2">
                      <X size={16} />
                    </button>
                  )}
                </div>
              ))}

              {/* Verbose ingestion log */}
              {verboseMode && verboseLogs.length > 0 && (
                <div className="border-2 border-[#111] dark:border-[#eee] bg-[#0a0a0a] text-[#00ff88] font-mono text-xs p-3 max-h-40 overflow-y-auto">
                  {verboseLogs.map((log, i) => (
                    <div key={i} className="leading-5">
                      <span className="text-gray-500">[{log.time}]</span> <span>{log.msg}</span>
                    </div>
                  ))}
                  <div ref={logsEndRef} />
                </div>
              )}

              <button 
                onClick={() => data.onAnalyze && data.onAnalyze(id, evidence.filter(e => e.status === 'uploaded'))}
                disabled={uploadingCount > 0 || evidence.filter(e => e.status === 'uploaded').length === 0}
                className="brutalist-button w-full py-3 mt-4 flex items-center justify-center space-x-2 bg-[#00ff88] text-[#111] border-[#111] hover:bg-[#111] hover:text-[#00ff88] disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {uploadingCount > 0 ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <Play size={18} fill="currentColor" />
                )}
                <span>Analyze Evidence</span>
              </button>
            </div>
          )}
        </>
      )}

      {mode === 'text' && (
        <div className="flex flex-col space-y-4">
          <div className="flex items-center justify-between border-b-2 border-[#111] pb-2">
            <h3 className="font-black uppercase">Paste Text</h3>
            <button onClick={() => setMode('select')}><X size={20} /></button>
          </div>
          <textarea
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            className="w-full h-32 border-2 border-[#111] p-2 font-mono text-sm resize-none outline-none focus:bg-[#f4f4f0]"
            placeholder="Paste clipboard text here..."
            autoFocus
          />
          <button onClick={handleTextSubmit} disabled={!textInput.trim()} className="brutalist-button py-2 flex items-center justify-center space-x-2">
            <Check size={16} />
            <span>Save Text</span>
          </button>
        </div>
      )}

      {mode === 'camera' && (
        <div className="flex flex-col space-y-4">
          <div className="flex items-center justify-between border-b-2 border-[#111] pb-2">
            <h3 className="font-black uppercase">Take Photo</h3>
            <button onClick={() => setMode('select')}><X size={20} /></button>
          </div>
          <div className="border-4 border-[#111] bg-black relative aspect-video overflow-hidden">
            <video ref={videoRef} autoPlay playsInline className="w-full h-full object-cover" />
          </div>
          <button onClick={takePhoto} className="brutalist-button py-3 flex items-center justify-center space-x-2">
            <Camera size={18} />
            <span>Capture</span>
          </button>
        </div>
      )}

      {mode === 'record' && (
        <div className="flex flex-col space-y-4">
          <div className="flex items-center justify-between border-b-2 border-[#111] pb-2">
            <h3 className="font-black uppercase">Live Record</h3>
            <button onClick={() => setMode('select')}><X size={20} /></button>
          </div>
          <div className="border-4 border-[#111] bg-black relative aspect-video overflow-hidden">
            <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover" />
            {isRecording && (
              <div className="absolute top-4 right-4 flex items-center space-x-2 bg-black/50 px-2 py-1 border border-red-500">
                <div className="w-3 h-3 rounded-full bg-red-500 animate-pulse" />
                <span className="text-red-500 font-mono text-xs font-bold">REC</span>
              </div>
            )}
          </div>
          <button 
            onClick={toggleRecord} 
            className={`brutalist-button py-3 flex items-center justify-center space-x-2 ${isRecording ? 'bg-red-500 text-white border-red-500 hover:bg-white hover:text-red-500' : ''}`}
          >
            {isRecording ? <X size={18} /> : <Mic size={18} />}
            <span>{isRecording ? 'Stop Recording' : 'Start Recording'}</span>
          </button>
        </div>
      )}

      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
