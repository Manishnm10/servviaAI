'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, Plus, Mic, Send, ImagePlus, FileText, User, HeartPulse, ShieldCheck, ChevronRight, Volume2, Bot, Leaf, AlertTriangle, Pill, Shield, Clock, Square, Languages, Search, CheckCheck, Settings, PenLine, Microscope, ImageIcon, Camera, Stethoscope } from 'lucide-react';
import { AmbientBackground } from '@/components/AmbientBackground';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

type AppState = 'LOGIN' | 'ONBOARDING' | 'CHAT';

const FA_TO_LUCIDE: Record<string, any> = {
  'fa-shield-alt': ShieldCheck,
  'fa-clock': Clock,
  'fa-language': Languages,
  'fa-search': Search,
  'fa-leaf': Leaf,
  'fa-robot': Bot,
  'fa-check-double': CheckCheck,
  'fa-cog': Settings,
  'fa-pen': PenLine,
  'fa-microscope': Microscope,
  'fa-image': ImageIcon,
};

const formatPhaseLabel = (p?: string) => {
  if (!p) return '';
  return p.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
};

const parseProfileArray = (str: any) => {
  if (!str) return [];
  if (Array.isArray(str)) return str;
  return str.split(',').map((s: string) => s.trim()).filter((s: string) => s.length > 0);
};

// Convert a recorded audio Blob (webm/opus on Chrome) to 16-bit PCM WAV mono,
// which the backend Gemini STT accepts (it does not take webm). Web Audio API only.
async function blobToWav(blob: Blob): Promise<Blob> {
  const arrayBuffer = await blob.arrayBuffer();
  const AudioCtx = (window.AudioContext || (window as any).webkitAudioContext);
  const ctx = new AudioCtx();
  const audioBuffer = await ctx.decodeAudioData(arrayBuffer);
  const len = audioBuffer.length, rate = audioBuffer.sampleRate, ch = audioBuffer.numberOfChannels;
  const mono = new Float32Array(len);
  for (let c = 0; c < ch; c++) { const d = audioBuffer.getChannelData(c); for (let i = 0; i < len; i++) mono[i] += d[i] / ch; }
  ctx.close();
  const buf = new ArrayBuffer(44 + len * 2), view = new DataView(buf);
  const ws = (o: number, s: string) => { for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i)); };
  ws(0, 'RIFF'); view.setUint32(4, 36 + len * 2, true); ws(8, 'WAVE'); ws(12, 'fmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, rate, true); view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  ws(36, 'data'); view.setUint32(40, len * 2, true);
  let off = 44; for (let i = 0; i < len; i++) { const s = Math.max(-1, Math.min(1, mono[i])); view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7FFF, true); off += 2; }
  return new Blob([view], { type: 'audio/wav' });
}

const stripMarkdownForTTS = (text: string) => {
  return text
    .replace(/#{1,6}\s/g, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/\|/g, ', ')
    .replace(/---+/g, '')
    .replace(/-\s/g, ', ')
    .replace(/\n+/g, '. ')
    .replace(/[🔬📋🏥📊🔍💊⚠️✅❌🟢🟡🔴👤🎯📚🧠💪🥗🩺📌📈❓🚨⚡🌿⏰💧📅🔗👋⚕️]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .substring(0, 3000);
};

const MemoizedMarkdown = React.memo(({ text }: { text: string }) => {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({...props}) => <h1 className="text-2xl font-bold mt-6 mb-4 text-white" {...props}/>,
        h2: ({...props}) => {
          const extractText = (childs: any): string => {
            if (typeof childs === 'string') return childs;
            if (Array.isArray(childs)) return childs.map(extractText).join('');
            if (childs?.props?.children) return extractText(childs.props.children);
            return '';
          };
          const rawText = extractText(props.children);
          const m = rawText.match(/^Clinical Assessment\s*[—–-]\s*(.+)$/i);
          if (m) {
            return (
              <h2 className="text-white mt-6 mb-2 py-2.5 px-4 bg-[rgba(20,184,166,0.06)] border-l-[3px] border-[#14b8a6] rounded-r-[10px] text-[1.05rem] font-bold">
                Clinical Assessment <span className="text-white/30">—</span> <span className="text-[#ef4444] drop-shadow-[0_0_12px_var(--color-primary-glow)]">{m[1]}</span>
              </h2>
            );
          }
          return <h2 className="text-white mt-6 mb-2 py-2.5 px-4 bg-[rgba(20,184,166,0.06)] border-l-[3px] border-[#14b8a6] rounded-r-[10px] text-[1.05rem] font-bold" {...props}/>;
        },
        h3: ({...props}) => {
          const childrenArr = React.Children.toArray(props.children);
          const rawText = childrenArr.join('').toLowerCase();
          if (rawText.includes('when to see a doctor')) {
            return <div className="bg-[#0f1115] border-l-[3px] border-teal-500 rounded-[8px] p-4 my-5"><h3 className="text-lg font-bold text-white shadow-none" {...props}/></div>;
          }
          return <h3 className="text-white mt-5 mb-2 py-3 px-4 bg-[rgba(220,38,38,0.06)] border-l-[3px] border-[#dc2626] rounded-r-[10px] text-[1rem] font-semibold" {...props}/>;
        },
        h4: ({...props}) => <h4 className="text-white mt-4 mb-1.5 text-base font-bold tracking-[0.2px]" {...props}/>,
        p: ({...props}) => <p className="text-white/90 leading-[1.8] my-3" {...props}/>,
        ul: ({...props}) => <ul className="list-disc leading-relaxed text-white/90 pl-8 my-4" {...props}/>,
        ol: ({...props}) => <ol className="list-decimal leading-relaxed text-white/90 pl-8 my-4" {...props}/>,
        li: ({...props}) => <li className="my-2 leading-[1.7] text-white/85" {...props}/>,
        strong: ({...props}) => {
          const text = React.Children.toArray(props.children).join('');
          return <strong className={`font-semibold text-[#dc2626] ${text === '▋' ? 'animate-[pulse_1s_ease-in-out_infinite] text-lg inline-block ml-0.5 align-text-bottom' : ''}`} {...props}/>;
        },
        em: ({...props}) => <em className="text-[var(--color-muted)] italic" {...props}/>,
        a: ({...props}) => <a className="text-[#38bdf8] no-underline border-b border-dashed border-[rgba(56,189,248,0.3)] hover:text-[#7dd3fc] hover:border-[rgba(125,211,252,0.5)] transition-all" target="_blank" rel="noopener noreferrer" {...props}/>,
        blockquote: ({...props}) => <blockquote className="border-l-[3px] border-[rgba(220,38,38,0.35)] px-4 py-3 my-4 bg-[rgba(220,38,38,0.04)] rounded-r-[10px] text-white/80" {...props}/>,
        code: ({...props}) => <code className="bg-[rgba(220,38,38,0.1)] text-[#ef4444] px-1.5 py-0.5 rounded-[6px] text-[0.9em]" {...props}/>,
        hr: () => <hr className="border-none h-px bg-[rgba(220,38,38,0.12)] my-5" />,
        table: ({...props}) => <div className="overflow-x-auto my-4"><table className="w-full text-left border-collapse" {...props}/></div>,
        th: ({...props}) => <th className="border-b border-primary/30 bg-primary/10 p-3 text-white font-bold" {...props}/>,
        td: ({...props}) => <td className="border-b border-white/10 p-3 text-white/80" {...props}/>,
      }}
    >
      {text.replace(/<br\s*\/?>/gi, '\n\n')}
    </ReactMarkdown>
  );
});
MemoizedMarkdown.displayName = 'MemoizedMarkdown';

export default function AppHome() {
  const [appState, setAppState] = useState<AppState>('LOGIN');
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [email, setEmail] = useState('');
  const [profileForm, setProfileForm] = useState({ name: '', allergies: '', conditions: '', medications: '' });
  const [userProfile, setUserProfile] = useState<any>(null);
  const [sessionId, setSessionId] = useState<string>('');

  const [messages, setMessages] = useState<any[]>([]);
  const [inputVal, setInputVal] = useState('');
  const [showAttachmentMenu, setShowAttachmentMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const plusBtnRef = useRef<HTMLButtonElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const skinFileInputRef = useRef<HTMLInputElement>(null);
  const skinCameraRef = useRef<HTMLInputElement>(null);
  const labFileInputRef = useRef<HTMLInputElement>(null);
  const labCameraRef = useRef<HTMLInputElement>(null);
  const [skinMode, setSkinMode] = useState<'edge' | 'cloud'>('cloud');
  const [isRecording, setIsRecording] = useState(false);
  const recognitionRef = useRef<any>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const [currentAudio, setCurrentAudio] = useState<HTMLAudioElement | null>(null);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speakingMsgIdx, setSpeakingMsgIdx] = useState<number | null>(null);

  useEffect(() => {
    setSessionId(crypto.randomUUID());
  }, []);

  // Voice input — backend Whisper, auto-detects ANY language.
  // Records audio and sends it to /api/proxy/chat/transcribe/. Whisper auto-detects
  // the spoken language and returns the transcript in its native script; we drop it
  // into the input and submit, and the pipeline replies in that same language.
  // No language selector, no hardcoded 'en-US' recognizer.
  const autoSubmit = () => {
    setTimeout(() => {
      const textarea = document.querySelector('textarea') as HTMLTextAreaElement;
      if (textarea && textarea.value.trim()) {
        const form = textarea.closest('form');
        if (form) form.requestSubmit();
      }
    }, 50);
  };

  const toggleVoiceInput = async () => {
    if (isRecording) {
      const mr = mediaRecorderRef.current;
      if (mr && mr.state !== 'inactive') mr.stop();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micStreamRef.current = stream;
      audioChunksRef.current = [];
      const mime = (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported('audio/webm')) ? 'audio/webm' : '';
      const mr = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      mediaRecorderRef.current = mr;
      mr.ondataavailable = (e) => { if (e.data && e.data.size > 0) audioChunksRef.current.push(e.data); };
      mr.onstop = async () => {
        if (micStreamRef.current) { micStreamRef.current.getTracks().forEach((t) => t.stop()); micStreamRef.current = null; }
        setIsRecording(false);
        const mt = mr.mimeType || 'audio/webm';
        const blob = new Blob(audioChunksRef.current, { type: mt });
        if (!blob.size) return;
        try {
          const wav = await blobToWav(blob);
          const fd = new FormData();
          fd.append('audio', wav, 'voice.wav');
          fd.append('email_id', email || '');
          const r = await fetch('/api/proxy/chat/transcribe/', { method: 'POST', body: fd });
          const d = await r.json();
          if (d && d.transcript && d.transcript.trim()) {
            setInputVal(d.transcript.trim());
            autoSubmit();
          }
        } catch (err) { console.error(err); }
      };
      mr.start();
      setIsRecording(true);
    } catch (e) {
      console.error(e);
      alert('Could not access microphone.');
      setIsRecording(false);
    }
  };

  // TTS with server fallback
  const stopSpeech = useCallback(() => {
    if (currentAudio) { currentAudio.pause(); setCurrentAudio(null); }
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    setIsSpeaking(false);
    setSpeakingMsgIdx(null);
  }, [currentAudio]);

  const handleSpeech = async (text: string, msgIdx: number) => {
    if (isSpeaking && speakingMsgIdx === msgIdx) { stopSpeech(); return; }
    if (isSpeaking) stopSpeech();
    const cleanText = stripMarkdownForTTS(text);
    if (!cleanText) return;
    setIsSpeaking(true);
    setSpeakingMsgIdx(msgIdx);
    try {
      const r = await fetch('/api/proxy/chat/synthesise_audio/', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email_id: email, text: cleanText })
      });
      const d = await r.json();
      if (d.audio && !d.error) {
        const ad = atob(d.audio);
        const ab = new ArrayBuffer(ad.length);
        const v = new Uint8Array(ab);
        for (let i = 0; i < ad.length; i++) v[i] = ad.charCodeAt(i);
        const bl = new Blob([ab], { type: 'audio/ogg' });
        const audio = new Audio(URL.createObjectURL(bl));
        setCurrentAudio(audio);
        audio.onended = () => stopSpeech();
        audio.onerror = () => { stopSpeech(); useBrowserTTS(cleanText); };
        await audio.play();
        return;
      }
    } catch (e) { /* fall through to browser TTS */ }
    useBrowserTTS(cleanText);
  };

  const useBrowserTTS = (text: string) => {
    if (!('speechSynthesis' in window)) { stopSpeech(); return; }
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text.substring(0, 1000));
    u.lang = 'en-IN'; u.rate = 0.9;
    u.onend = () => stopSpeech();
    u.onerror = () => stopSpeech();
    window.speechSynthesis.speak(u);
  };

  // Click outside to close menu
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        menuRef.current && !menuRef.current.contains(event.target as Node) &&
        plusBtnRef.current && !plusBtnRef.current.contains(event.target as Node)
      ) {
        setShowAttachmentMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };
  useEffect(() => { if (appState === 'CHAT') scrollToBottom(); }, [messages, appState]);
  useEffect(() => { if (appState === 'CHAT') setTimeout(() => inputRef.current?.focus(), 100); }, [appState]);

  // Direct skin upload — show preview + auto-send
  const handleDirectSkinUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 5 * 1024 * 1024) { alert('Max 5MB'); return; }
    setShowAttachmentMenu(false);
    const reader = new FileReader();
    reader.onload = (ev) => {
      // Show image preview as user message
      setMessages(prev => [...prev, {
        type: 'user', text: 'Skin image uploaded',
        imageUrl: ev.target?.result as string
      }]);
      // Auto-trigger analysis
      analyzeSkin(f);
    };
    reader.readAsDataURL(f);
    e.target.value = '';
  };

  // Direct lab upload — show file list + auto-send
  const handleDirectLabUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fs = e.target.files;
    if (!fs || !fs.length) return;
    for (let i = 0; i < fs.length; i++) {
      if (fs[i].size > 10 * 1024 * 1024) { alert(`${fs[i].name} too large. Max 10MB`); return; }
    }
    setShowAttachmentMenu(false);
    const files = Array.from(fs);
    // Show file list as user message
    setMessages(prev => [...prev, {
      type: 'user', text: `Uploaded ${files.length} file${files.length > 1 ? 's' : ''}`,
      labFiles: files.map(f => ({ name: f.name, isPdf: f.type.includes('pdf') }))
    }]);
    analyzeLab(files);
    e.target.value = '';
  };

  // Skin analysis SSE
  const analyzeSkin = async (file: File) => {
    const fd = new FormData();
    fd.append('email_id', email.trim());
    fd.append('session_id', sessionId);
    fd.append('image', file);
    fd.append('analysis_mode', skinMode);
    setMessages(prev => [...prev, { type: 'ai', text: '', isStreaming: true, stage: 'Preparing analysis...', completedStages: [] }]);
    await streamSSE('/api/proxy/skin/analyze/stream/', { method: 'POST', body: fd });
  };

  // Lab analysis SSE
  const analyzeLab = async (files: File[]) => {
    const fd = new FormData();
    fd.append('email_id', email.trim());
    fd.append('session_id', sessionId);
    for (const f of files) fd.append('report', f);
    setMessages(prev => [...prev, { type: 'ai', text: '', isStreaming: true, stage: 'Preparing analysis...', completedStages: [] }]);
    await streamSSE('/api/proxy/lab-report/analyze/stream/', { method: 'POST', body: fd });
  };

  // Generic SSE stream handler (skin/lab) — uses same buffered render loop
  const streamSSE = async (url: string, fetchOptions: RequestInit) => {
    try {
      const response = await fetch(url, fetchOptions);
      if (!response.ok || !response.body) throw new Error('Stream Failed');
      await streamSSEFromResponse(response);
    } catch (err) {
      console.error('Stream error:', err);
      setMessages(prev => {
        const msgs = [...prev];
        if (msgs.length > 0) {
          msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], text: 'Connection error. Please try again.', isStreaming: false, stage: null };
        }
        return msgs;
      });
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    try {
      const res = await fetch('/api/proxy/profile/profile/check_profile/', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email_id: email.trim() })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      if (data.exists && data.is_complete && data.profile) {
        setUserProfile(data.profile);
        setProfileForm({
          name: data.profile.first_name || email.split('@')[0],
          allergies: data.profile.allergies || '',
          conditions: data.profile.medical_conditions || '',
          medications: data.profile.current_medications || '',
        });
        setAppState('CHAT');
      } else {
        if (data.profile) {
          setUserProfile(data.profile);
          setProfileForm({
            name: data.profile.first_name || '',
            allergies: data.profile.allergies || '',
            conditions: data.profile.medical_conditions || '',
            medications: data.profile.current_medications || '',
          });
        }
        setAppState('ONBOARDING');
      }
    } catch (err) {
      console.error(err);
      alert(`ServVia Backend Error: ${err instanceof Error ? err.message : String(err)}. Please ensure Django server is running on localhost:9000.`);
    }
  };

  const editProfile = () => {
    setIsEditingProfile(true);
    if (userProfile) {
      setProfileForm({
        name: userProfile.first_name || '',
        allergies: userProfile.allergies || '',
        conditions: userProfile.medical_conditions || '',
        medications: userProfile.current_medications || '',
      });
    }
    setAppState('ONBOARDING');
  };

  const handleOnboardingSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profileForm.name) return;
    try {
      const res = await fetch('/api/proxy/profile/profile/create_or_update_profile/', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email_id: email.trim(),
          first_name: profileForm.name,
          allergies: profileForm.allergies,
          medical_conditions: profileForm.conditions,
          current_medications: profileForm.medications
        })
      });
      const data = await res.json();
      if (data.success) {
        setUserProfile(data.profile);
        setIsEditingProfile(false);
        setAppState('CHAT');
      } else { alert('Error saving profile'); }
    } catch (err) { console.error(err); }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    const msg = inputVal.trim();
    if (!msg) return;
    setMessages(prev => [...prev, { type: 'user', text: msg }]);
    setInputVal('');
    setMessages(prev => [...prev, { type: 'ai', text: '', isStreaming: true, stage: 'Connecting...', completedStages: [] }]);
    try {
      const response = await fetch('/api/proxy/chat/stream/', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email_id: email.trim(), query: msg, session_id: sessionId })
      });
      if (!response.ok || !response.body) throw new Error('Stream Failed');
      await streamSSEFromResponse(response);
    } catch (err) {
      console.error(err);
      // Fallback to non-streaming
      try {
        const fbRes = await fetch('/api/proxy/chat/get_answer_for_text_query/', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email_id: email.trim(), query: msg })
        });
        if (fbRes.ok) {
          const fbData = await fbRes.json();
          setMessages(prev => {
            const msgs = [...prev];
            msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], text: fbData.response || 'No response.', isStreaming: false, stage: null, pipelineData: fbData };
            return msgs;
          });
          return;
        }
      } catch (e) { /* fallback failed */ }
      setMessages(prev => {
        const msgs = [...prev];
        msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], text: 'Connection lost to ServVia Agent.', isStreaming: false, stage: null };
        return msgs;
      });
    }
  };

  // Buffered SSE stream — tokens accumulate in a ref, 70ms render loop syncs to React state
  // This matches index.html's setInterval(RENDER_INTERVAL=70) pattern exactly
  const streamSSEFromResponse = async (response: Response) => {
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let sseBuffer = '';
    let currentEvent = '';

    // Accumulation buffer (NOT React state — no re-renders per token)
    let accumulatedText = '';
    let renderedText = '';
    let pipelineData: any = null;
    let completedStages: { label: string; icon: string }[] = [];
    let currentStage = 'Connecting...';
    let currentStageIcon = 'fa-circle-notch';
    let streamDone = false;
    let streamingStarted = false;

    // 70ms render loop — syncs accumulated text to React state at a smooth pace
    const RENDER_INTERVAL = 70;
    const renderLoop = setInterval(() => {
      if (accumulatedText !== renderedText) {
        renderedText = accumulatedText;
        // Compute chunks for the two-div incremental render
        let frozenLen = 0;
        const chunks: string[] = [];
        let remaining = accumulatedText;
        // Freeze completed paragraphs
        while (remaining.length > 0) {
          const paraBreak = remaining.indexOf('\n\n');
          if (paraBreak > 0 && remaining.length - paraBreak > 2) {
            chunks.push(remaining.slice(0, paraBreak + 2));
            frozenLen += paraBreak + 2;
            remaining = remaining.slice(paraBreak + 2);
          } else break;
        }
        setMessages(prev => {
          const msgs = [...prev];
          const last = { ...msgs[msgs.length - 1] };
          last.stage = null;
          last.text = accumulatedText;
          last.chunks = chunks.length > 0 ? chunks : undefined;
          last.activeText = remaining;
          last.frozenLen = frozenLen;
          msgs[msgs.length - 1] = last;
          return msgs;
        });
      }
      if (streamDone) clearInterval(renderLoop);
    }, RENDER_INTERVAL);

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      sseBuffer += decoder.decode(value, { stream: true });
      const lines = sseBuffer.split('\n');
      sseBuffer = lines.pop() || '';
      for (const line of lines) {
        if (line.startsWith('event: ')) { currentEvent = line.substring(7).trim(); }
        else if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.substring(6));
            if (currentEvent === 'stage') {
              if (data.id === 'streaming' || data.id === 'emergency') continue;
              if (currentStage && currentStage !== 'Connecting...' && currentStage !== 'Preparing analysis...') {
                if (!completedStages.some(s => s.label === currentStage)) {
                  completedStages.push({ label: currentStage, icon: currentStageIcon });
                }
              }
              currentStage = data.label;
              currentStageIcon = data.icon || 'fa-cog';
              // Update stage in React immediately (stages should show instantly)
              setMessages(prev => {
                const msgs = [...prev];
                const last = { ...msgs[msgs.length - 1] };
                last.stage = currentStage;
                last.stageIcon = currentStageIcon;
                last.completedStages = [...completedStages];
                msgs[msgs.length - 1] = last;
                return msgs;
              });
            } else if (currentEvent === 'token') {
              if (!streamingStarted) {
                streamingStarted = true;
                // Hide stages, show text — done via the render loop when accumulatedText grows
              }
              accumulatedText += (data.text || '');
            } else if (currentEvent === 'emergency') {
              accumulatedText = data.response || '';
              pipelineData = data;
              streamDone = true;
              clearInterval(renderLoop);
              setMessages(prev => {
                const msgs = [...prev];
                msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], text: accumulatedText, isStreaming: false, stage: null, pipelineData: data };
                return msgs;
              });
            } else if (currentEvent === 'done') {
              pipelineData = data;
            } else if (currentEvent === 'error') {
              streamDone = true;
              clearInterval(renderLoop);
              setMessages(prev => {
                const msgs = [...prev];
                msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], text: data.message || 'An error occurred.', isStreaming: false, stage: null, isError: true };
                return msgs;
              });
            }
          } catch (err) { /* parse error */ }
        }
      }
    }

    // Stream finished — final render with full text
    streamDone = true;
    clearInterval(renderLoop);
    setMessages(prev => {
      if (prev.length === 0) return prev;
      const msgs = [...prev];
      msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], text: accumulatedText, isStreaming: false, stage: null, pipelineData: pipelineData, chunks: undefined, activeText: undefined };
      return msgs;
    });
  };

  const allAllergens = parseProfileArray(userProfile?.allergies);
  const allConditions = parseProfileArray(userProfile?.medical_conditions);

  return (
    <main className="w-full h-screen overflow-hidden relative text-white selection:bg-primary/30 font-sans">
      <AmbientBackground isVisible={appState === 'LOGIN'} />

      <div className="max-w-[1200px] mx-auto h-screen flex flex-col relative z-10">
        {/* ── HEADER ── */}
        <header className="flex items-center justify-between px-8 py-5 border-b border-[var(--color-border)] bg-[#050505]/85 backdrop-blur-xl">
          <div className="flex items-center gap-4">
            <div className="w-[44px] h-[44px] rounded-[12px] flex items-center justify-center text-[1.4rem] shadow-[0_0_16px_var(--color-primary-glow)]" style={{ background: 'linear-gradient(135deg, #dc2626, #991b1b)' }}>
              <i className="fas fa-heartbeat text-white" />
            </div>
            <div>
              <h1 className="text-[1.6rem] font-extrabold tracking-[-0.5px]" style={{ background: 'linear-gradient(135deg, #fff 0%, #dc2626 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>ServVia</h1>
              <p className="text-[0.7rem] text-[var(--color-muted)] tracking-[3px] uppercase">AI Healthcare Intelligence</p>
            </div>
          </div>
          <div className="flex items-center gap-6">
            {appState !== 'LOGIN' && userProfile && (
              <div className="flex flex-col items-end gap-1.5">
                <span className="font-semibold text-base">{userProfile.first_name || 'User'}</span>
                <div className="flex gap-2 flex-wrap justify-end">
                  {allAllergens.length > 0 && (
                    <span className="bg-[rgba(220,38,38,0.08)] border border-[rgba(220,38,38,0.25)] px-3 py-1 rounded-[20px] text-[0.75rem] text-[#dc2626] font-medium flex items-center gap-1.5 backdrop-blur-[8px]">
                      <Shield className="w-3 h-3 fill-current" /> Protected from {allAllergens.length} allergen{allAllergens.length > 1 ? 's' : ''}
                    </span>
                  )}
                  {allConditions.length > 0 && (
                    <span className="bg-[rgba(220,38,38,0.08)] border border-[rgba(220,38,38,0.25)] px-3 py-1 rounded-[20px] text-[0.75rem] text-[#dc2626] font-medium flex items-center gap-1.5 backdrop-blur-[8px]">
                      <FileText className="w-3 h-3" /> {allConditions.length} condition{allConditions.length > 1 ? 's' : ''}
                    </span>
                  )}
                </div>
              </div>
            )}
            {appState === 'CHAT' && (
              <button onClick={editProfile} className="bg-[rgba(220,38,38,0.08)] border border-[rgba(220,38,38,0.25)] text-[#dc2626] px-4 py-2 rounded-[10px] text-[0.85rem] font-medium hover:bg-[rgba(220,38,38,0.15)] hover:-translate-y-px transition-all flex items-center gap-2">
                <User className="w-4 h-4" /> Edit Profile
              </button>
            )}
            <div className="flex items-center gap-2 text-[0.85rem] text-[var(--color-muted)]">
              <div className="w-2 h-2 bg-[#22c55e] rounded-full animate-pulse shadow-[0_0_8px_#22c55e]" />
              <span>Online</span>
            </div>
          </div>
        </header>

        {/* ── MAIN ── */}
        <div className="flex-1 flex flex-col overflow-hidden px-8 py-6">
          <div id="chat" className={`flex-1 overflow-x-hidden p-8 bg-transparent rounded-[20px] border border-[var(--color-border)] mb-5 relative ${appState === 'LOGIN' ? 'overflow-y-hidden' : 'overflow-y-auto'}`}>

            <AnimatePresence mode="wait">
              {/* === LOGIN === */}
              {appState === 'LOGIN' && (
                <motion.div key="login" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="min-h-[400px] flex flex-col items-center justify-center text-center h-full">
                  {/* Spinning border card */}
                  <div className="w-full max-w-[480px] relative mx-auto p-[2px] rounded-3xl shadow-[0_0_40px_rgba(220,38,38,0.15)]">
                    <div className="absolute inset-0 overflow-hidden rounded-3xl pointer-events-none">
                      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[250%] h-[250%] animate-[spin_8s_linear_infinite] bg-[conic-gradient(from_0deg,transparent_0_300deg,var(--color-primary)_360deg)] opacity-90" />
                    </div>
                    <div className="relative bg-[#080808]/95 backdrop-blur-2xl p-10 rounded-[calc(1.5rem-2px)] z-10 flex flex-col items-center">
                      <div className="mb-8 animate-[floatIcon_3s_ease-in-out_infinite] text-[4rem]">
                        <i className="fas fa-stethoscope" style={{ background: 'linear-gradient(135deg, #fff, #dc2626)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }} />
                      </div>
                      <h2 className="text-[2.5rem] font-extrabold mb-3 tracking-[-1px] bg-clip-text text-transparent" style={{ backgroundImage: 'linear-gradient(135deg, #fff 30%, #dc2626 100%)' }}>Welcome to ServVia</h2>
                      <p className="text-[1.1rem] text-[var(--color-muted)] mb-10">Your Personalized AI Health Companion</p>
                      <form onSubmit={handleLogin} className="w-full max-w-[480px] space-y-4">
                        <input
                          type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                          placeholder="Enter your email address"
                          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleLogin(e); } }}
                          className="w-full bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[14px] px-5 py-[0.9rem] text-white text-base placeholder-white/25 outline-none focus:bg-white/[0.06] focus:border-[#dc2626] focus:shadow-[0_0_0_3px_rgba(220,38,38,0.1),0_0_20px_rgba(220,38,38,0.08)] transition-all font-sans"
                        />
                        <button type="submit" className="w-full py-4 bg-gradient-to-br from-[#dc2626] to-[#991b1b] rounded-[14px] font-semibold text-base hover:-translate-y-[2px] hover:shadow-[0_8px_30px_rgba(220,38,38,0.45)] transition-all shadow-[0_4px_20px_var(--color-primary-glow)]">
                          Continue
                        </button>
                      </form>
                    </div>
                  </div>
                  {/* Feature Cards */}
                  <div className="grid grid-cols-3 gap-4 mt-12 max-w-[480px] w-full">
                    {[
                      { icon: Bot, label: 'Multi-Agent AI' },
                      { icon: ShieldCheck, label: 'Safety Verified' },
                      { icon: Leaf, label: 'Natural Remedies' },
                    ].map((card, i) => (
                      <div key={i}
                        className="group relative bg-[#080808]/95 backdrop-blur-2xl border border-[var(--color-border)] rounded-[16px] p-5 text-center overflow-hidden hover:-translate-y-[6px] hover:border-[rgba(220,38,38,0.35)] hover:shadow-[0_12px_40px_rgba(220,38,38,0.1)] transition-all duration-[400ms]">
                        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(220,38,38,0.08),transparent_70%)] opacity-0 group-hover:opacity-100 transition-opacity duration-[400ms]" />
                        <card.icon className="w-8 h-8 text-[#dc2626] mb-3 mx-auto relative z-10" />
                        <p className="text-[0.85rem] text-[var(--color-muted)] font-medium relative z-10">{card.label}</p>
                      </div>
                    ))}
                  </div>
                </motion.div>
              )}

              {/* === ONBOARDING === */}
              {appState === 'ONBOARDING' && (
                <motion.div key="onboarding" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex flex-col items-center text-center py-8">
                  <div className="text-[4rem] mb-8 animate-[floatIcon_3s_ease-in-out_infinite]">
                    <i className="fas fa-clipboard-list" style={{ background: 'linear-gradient(135deg, #fff, #dc2626)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }} />
                  </div>
                  <h2 className="text-[2.5rem] font-extrabold mb-3 tracking-[-1px]" style={{ background: 'linear-gradient(135deg, #fff 30%, #dc2626 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                    {isEditingProfile ? 'Update Your Profile' : 'Tell Us About Yourself'}
                  </h2>
                  <p className="text-[1.1rem] text-[var(--color-muted)] mb-10">This helps us provide safe, personalized health recommendations</p>
                  <div className="w-full max-w-[480px] text-left">
                    <form onSubmit={handleOnboardingSubmit} className="space-y-6">
                      <div>
                        <label className="block mb-2 text-white/80 text-[0.85rem] font-medium">What&apos;s your name?</label>
                        <input required type="text" value={profileForm.name} onChange={(e) => setProfileForm({ ...profileForm, name: e.target.value })}
                          placeholder="Your first name"
                          className="w-full bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[14px] px-5 py-[0.9rem] text-white placeholder-white/25 outline-none focus:bg-white/[0.06] focus:border-[#dc2626] focus:shadow-[0_0_0_3px_rgba(220,38,38,0.1),0_0_20px_rgba(220,38,38,0.08)] transition-all font-sans" />
                      </div>
                      <div>
                        <label className="block mb-2 text-white/80 text-[0.85rem] font-medium flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-[#dc2626]" /> Do you have any allergies?</label>
                        <textarea value={profileForm.allergies} onChange={(e) => setProfileForm({ ...profileForm, allergies: e.target.value })}
                          placeholder="e.g., peanuts, shellfish, penicillin (or leave blank)"
                          className="w-full bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[14px] px-5 py-[0.9rem] text-white placeholder-white/25 outline-none focus:bg-white/[0.06] focus:border-[#dc2626] focus:shadow-[0_0_0_3px_rgba(220,38,38,0.1),0_0_20px_rgba(220,38,38,0.08)] transition-all font-sans resize-y min-h-[80px]" />
                        <p className="mt-2 text-[0.75rem] text-[var(--color-muted)]">Separate multiple allergies with commas</p>
                      </div>
                      <div>
                        <label className="block mb-2 text-white/80 text-[0.85rem] font-medium flex items-center gap-2"><FileText className="w-4 h-4 text-[#dc2626]" /> Any existing medical conditions?</label>
                        <textarea value={profileForm.conditions} onChange={(e) => setProfileForm({ ...profileForm, conditions: e.target.value })}
                          placeholder="e.g., diabetes, hypertension (or leave blank)"
                          className="w-full bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[14px] px-5 py-[0.9rem] text-white placeholder-white/25 outline-none focus:bg-white/[0.06] focus:border-[#dc2626] focus:shadow-[0_0_0_3px_rgba(220,38,38,0.1),0_0_20px_rgba(220,38,38,0.08)] transition-all font-sans resize-y min-h-[80px]" />
                        <p className="mt-2 text-[0.75rem] text-[var(--color-muted)]">This helps us recommend safe remedies</p>
                      </div>
                      <div>
                        <label className="block mb-2 text-white/80 text-[0.85rem] font-medium flex items-center gap-2"><Pill className="w-4 h-4 text-[#dc2626]" /> Current medications?</label>
                        <textarea value={profileForm.medications} onChange={(e) => setProfileForm({ ...profileForm, medications: e.target.value })}
                          placeholder="e.g., aspirin, metformin (or leave blank)"
                          className="w-full bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[14px] px-5 py-[0.9rem] text-white placeholder-white/25 outline-none focus:bg-white/[0.06] focus:border-[#dc2626] focus:shadow-[0_0_0_3px_rgba(220,38,38,0.1),0_0_20px_rgba(220,38,38,0.08)] transition-all font-sans resize-y min-h-[80px]" />
                        <p className="mt-2 text-[0.75rem] text-[var(--color-muted)]">We&apos;ll check for potential interactions</p>
                      </div>
                      <button type="submit" className="w-full py-4 bg-gradient-to-br from-[#dc2626] to-[#991b1b] rounded-[14px] font-semibold hover:-translate-y-[2px] hover:shadow-[0_8px_30px_rgba(220,38,38,0.45)] transition-all flex items-center justify-center gap-2 shadow-[0_4px_20px_var(--color-primary-glow)]">
                        <ShieldCheck className="w-5 h-5" /> Save Profile &amp; Continue
                      </button>
                    </form>
                  </div>
                </motion.div>
              )}

              {/* === CHAT === */}
              {appState === 'CHAT' && (
                <motion.div key="chat" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="w-full h-full flex flex-col">
                  {/* Welcome state */}
                  {messages.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-10 my-auto text-center">
                      <div className="text-[2.5rem] mb-4"><HeartPulse className="inline-block text-[#dc2626]" style={{ width: 48, height: 48 }} /></div>
                      <h2 className="text-[1.5rem] font-bold mb-2 text-white">Welcome back, {userProfile?.first_name || profileForm.name}!</h2>
                      <p className="text-[var(--color-muted)] mb-6">ServVia — Multi-Agent AI Verified Healthcare</p>
                      {allAllergens.length > 0 && (
                        <div className="inline-flex items-center gap-2 bg-[rgba(220,38,38,0.08)] border border-[rgba(220,38,38,0.2)] px-6 py-3 rounded-[10px] mb-4">
                          <Shield className="w-4 h-4 text-[#dc2626] fill-current" />
                          <span className="text-[#dc2626]">Protected from: {allAllergens.join(', ')}</span>
                        </div>
                      )}
                      <div className="mt-6 flex gap-3 justify-center flex-wrap">
                        <span className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-[20px] text-[0.72rem] font-semibold tracking-[0.3px] bg-[rgba(139,92,246,0.1)] border border-[rgba(139,92,246,0.25)] text-[#a78bfa]"><Bot className="w-3.5 h-3.5" /> Proposer</span>
                        <span className="text-white/20">&rarr;</span>
                        <span className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-[20px] text-[0.72rem] font-semibold tracking-[0.3px] bg-[rgba(139,92,246,0.1)] border border-[rgba(139,92,246,0.25)] text-[#a78bfa]"><Search className="w-3.5 h-3.5" /> Critic</span>
                        <span className="text-white/20">&rarr;</span>
                        <span className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-[20px] text-[0.72rem] font-semibold tracking-[0.3px] bg-[rgba(34,197,94,0.1)] border border-[rgba(34,197,94,0.25)] text-[#22c55e]"><ShieldCheck className="w-3.5 h-3.5" /> Verified</span>
                      </div>
                      <p className="mt-8 text-[var(--color-muted)]">How can I help you today?</p>
                    </div>
                  )}

                  {/* Messages */}
                  <div className="flex flex-col gap-5 pb-4">
                    {messages.map((msg, idx) => (
                      <motion.div key={idx} initial={{ opacity: 0, y: 16, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                        className={`${msg.type === 'user' ? 'float-right clear-both self-end' : 'float-left clear-both self-start'} w-full flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                        {msg.type === 'user' ? (
                          <div className="max-w-[82%] md:max-w-[82%]">
                            {msg.imageUrl && (
                              <div className="text-center mb-2">
                                <img src={msg.imageUrl} className="max-w-[300px] max-h-[300px] rounded-[14px] inline-block" alt="Skin" />
                              </div>
                            )}
                            {msg.labFiles && (
                              <div className="text-center mb-2">
                                <FileText className="w-12 h-12 text-[#dc2626] mx-auto mb-2" />
                                <ul className="list-none p-0 mt-2 text-sm">
                                  {msg.labFiles.map((f: any, i: number) => (
                                    <li key={i}><FileText className="w-4 h-4 inline mr-1" />{f.name}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            <div className="bg-gradient-to-br from-[#dc2626] to-[#991b1b] text-white px-6 py-4 rounded-[20px_20px_4px_20px] inline-block shadow-[0_4px_16px_rgba(220,38,38,0.25)] leading-relaxed">
                              {msg.text}
                            </div>
                          </div>
                        ) : msg.isStreaming && !msg.text ? (
                          /* ── Streaming stage indicator (exact index.html replica) ── */
                          <div className="bg-white/[0.025] border border-[var(--color-border)] rounded-[20px_20px_20px_4px] p-6 max-w-[92%] md:max-w-[82%] leading-[1.8]">
                            {/* Completed stages trail */}
                            {msg.completedStages?.length > 0 && (
                              <div className="flex flex-col gap-[0.15rem] mb-3 pb-2" style={{ borderBottom: '1px solid rgba(220, 38, 38, 0.08)' }}>
                                {msg.completedStages.map((s: any, i: number) => (
                                  <div key={i} className="flex items-center gap-2 transition-all duration-300" style={{ fontSize: '0.7rem', color: 'rgba(255, 255, 255, 0.25)' }}>
                                    <i className="fas fa-check" style={{ color: 'rgba(34, 197, 94, 0.5)', fontSize: '0.65rem' }} />
                                    <span>{s.label}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                            {/* Current stage */}
                            <div className="flex items-center gap-3 py-3 transition-all duration-300">
                              <i className={`fas ${msg.stageIcon || 'fa-circle-notch'} animate-[stagePulse_2s_ease-in-out_infinite]`} style={{ color: '#dc2626', fontSize: '1rem', width: 20, textAlign: 'center' }} />
                              <span style={{ fontSize: '0.85rem', color: 'rgba(255, 255, 255, 0.55)', fontWeight: 500 }}>{msg.stage || 'Connecting...'}</span>
                              <div className="flex gap-[3px] ml-1">
                                <span className="rounded-full bg-[#dc2626] animate-[typingBounce_1.4s_infinite_ease-in-out]" style={{ width: 4, height: 4 }} />
                                <span className="rounded-full bg-[#dc2626] animate-[typingBounce_1.4s_infinite_ease-in-out]" style={{ width: 4, height: 4, animationDelay: '0.15s' }} />
                                <span className="rounded-full bg-[#dc2626] animate-[typingBounce_1.4s_infinite_ease-in-out]" style={{ width: 4, height: 4, animationDelay: '0.3s' }} />
                              </div>
                            </div>
                          </div>
                        ) : (
                          /* ── Bot message content (exact index.html replica) ── */
                          <div className="max-w-[92%] md:max-w-[82%] bg-white/[0.025] border border-[var(--color-border)] text-white rounded-[20px_20px_20px_4px] leading-[1.8]">
                            {/* Message text */}
                            <div className="p-6">
                              {msg.isError ? (
                                <div className="text-red-500 font-medium whitespace-pre-wrap">{msg.text}</div>
                              ) : msg.isStreaming && msg.chunks ? (
                                <>
                                  {msg.chunks.map((chk: string, i: number) => <MemoizedMarkdown key={i} text={chk} />)}
                                  {msg.activeText !== undefined && <MemoizedMarkdown text={msg.activeText + ' **▋**'} />}
                                </>
                              ) : (
                                <MemoizedMarkdown text={msg.text} />
                              )}

                              {/* Pipeline meta — matching index.html addToChatWindow exactly */}
                              {msg.pipelineData && (
                                <div className="flex items-center flex-wrap gap-2 mt-4 pt-3" style={{ borderTop: '1px solid rgba(220, 38, 38, 0.08)' }}>
                                  {msg.pipelineData.pipeline === 'emergency_intercept' && (
                                    <span className="inline-flex items-center gap-[0.4rem] px-[0.85rem] py-[0.35rem] rounded-[20px] text-[0.72rem] font-semibold tracking-[0.3px] mr-2" style={{ background: 'rgba(239, 68, 68, 0.12)', border: '1px solid rgba(239, 68, 68, 0.35)', color: '#ef4444' }}>
                                      <i className="fas fa-exclamation-triangle" /> Emergency Protocol
                                    </span>
                                  )}
                                  {msg.pipelineData.pipeline === 'safety_blocked' && (
                                    <span className="inline-flex items-center gap-[0.4rem] px-[0.85rem] py-[0.35rem] rounded-[20px] text-[0.72rem] font-semibold tracking-[0.3px] mr-2" style={{ background: 'rgba(251, 191, 36, 0.1)', border: '1px solid rgba(251, 191, 36, 0.25)', color: '#fbbf24' }}>
                                      <i className="fas fa-ban" /> Safety Blocked
                                    </span>
                                  )}
                                </div>
                              )}

                              {/* Chrono card — matching index.html .chrono-card exactly */}
                              {msg.pipelineData?.bio_state && (
                                <div className="flex items-start gap-3 mt-3 p-3 px-4 rounded-[12px]" style={{ background: 'rgba(99, 102, 241, 0.04)', border: '1px solid rgba(99, 102, 241, 0.15)' }}>
                                  <span className="flex-shrink-0 mt-[0.1rem]" style={{ fontSize: '1rem' }}>
                                    <i className="fas fa-clock" style={{ color: '#818cf8' }} />
                                  </span>
                                  <div style={{ fontSize: '0.78rem', color: 'rgba(255, 255, 255, 0.55)', lineHeight: 1.6 }}>
                                    <div style={{ color: 'rgba(255, 255, 255, 0.75)', fontWeight: 600, fontSize: '0.78rem', marginBottom: '0.25rem' }}>Biological Context</div>
                                    <span className="inline-block mr-[0.35rem] mt-1 px-2 py-[0.15rem] rounded-[6px]" style={{ background: 'rgba(99, 102, 241, 0.08)', fontSize: '0.68rem', color: 'rgba(165, 168, 252, 0.9)' }}>{formatPhaseLabel(msg.pipelineData.bio_state.circadian_phase)}</span>
                                    <span className="inline-block mr-[0.35rem] mt-1 px-2 py-[0.15rem] rounded-[6px]" style={{ background: 'rgba(99, 102, 241, 0.08)', fontSize: '0.68rem', color: 'rgba(165, 168, 252, 0.9)' }}>{formatPhaseLabel(msg.pipelineData.bio_state.seasonal_influence)}</span>
                                    <span className="inline-block mr-[0.35rem] mt-1 px-2 py-[0.15rem] rounded-[6px]" style={{ background: 'rgba(99, 102, 241, 0.08)', fontSize: '0.68rem', color: 'rgba(165, 168, 252, 0.9)' }}>Sleep: {formatPhaseLabel(msg.pipelineData.bio_state.sleep_pressure)}</span>
                                    {msg.pipelineData.bio_state.is_misaligned && (
                                      <span className="inline-block mr-[0.35rem] mt-1 px-2 py-[0.15rem] rounded-[6px]" style={{ background: 'rgba(239, 68, 68, 0.1)', fontSize: '0.68rem', color: '#fca5a5' }}>Misaligned</span>
                                    )}
                                  </div>
                                </div>
                              )}
                            </div>

                            {/* Speaker button — matching index.html .message-actions .speaker-btn */}
                            {!msg.isStreaming && msg.text && (
                              <div className="flex justify-end mt-3 pt-3 px-6 pb-4" style={{ borderTop: '1px solid rgba(220, 38, 38, 0.06)' }}>
                                <button onClick={() => handleSpeech(msg.text, idx)} title={isSpeaking && speakingMsgIdx === idx ? 'Stop' : 'Listen'}
                                  className={`w-[34px] h-[34px] rounded-full flex items-center justify-center transition-all ${isSpeaking && speakingMsgIdx === idx ? 'animate-[speakerPulse_1.5s_infinite]' : 'hover:scale-105'}`}
                                  style={isSpeaking && speakingMsgIdx === idx
                                    ? { background: 'rgba(220, 38, 38, 0.25)', color: '#dc2626' }
                                    : { background: 'rgba(220, 38, 38, 0.08)', border: '1px solid rgba(220, 38, 38, 0.15)', color: 'rgba(255, 255, 255, 0.5)' }}>
                                  <i className={`fas ${isSpeaking && speakingMsgIdx === idx ? 'fa-stop' : 'fa-volume-up'}`} style={{ fontSize: '0.85rem' }} />
                                </button>
                              </div>
                            )}
                          </div>
                        )}
                      </motion.div>
                    ))}
                    <div ref={chatEndRef} />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* ── INPUT BAR ── */}
          {appState === 'CHAT' && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="relative mx-8 mb-6">
              {/* Options menu */}
              <AnimatePresence>
                {showAttachmentMenu && (
                  <motion.div ref={menuRef} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 10 }}
                    className="absolute bottom-[70px] left-0 bg-[rgba(10,10,10,0.97)] border border-[rgba(220,38,38,0.25)] rounded-[16px] p-2 flex flex-col gap-1 min-w-[200px] shadow-[0_12px_40px_rgba(0,0,0,0.6)] z-40">
                    <div className="px-4 py-2 text-[0.7rem] text-white/35 uppercase tracking-[1px]">Skin Analysis</div>
                    <div className="flex mx-2 mb-1 bg-white/[0.06] rounded-[8px] p-[3px] gap-[2px]">
                      <button type="button" onClick={() => setSkinMode('edge')} className={`flex-1 py-1.5 px-2 rounded-[6px] text-[0.7rem] transition-all leading-[1.3] ${skinMode === 'edge' ? 'bg-[#dc2626] text-white font-semibold' : 'text-white/45 hover:text-white/70 hover:bg-white/5'}`}>Edge AI (Completely Private)</button>
                      <button type="button" onClick={() => setSkinMode('cloud')} className={`flex-1 py-1.5 px-2 rounded-[6px] text-[0.7rem] transition-all leading-[1.3] ${skinMode === 'cloud' ? 'bg-[#dc2626] text-white font-semibold' : 'text-white/45 hover:text-white/70 hover:bg-white/5'}`}>Cloud (Better Accuracy)</button>
                    </div>
                    <button className="camera-option flex items-center gap-3 px-4 py-3 rounded-[10px] text-white/80 hover:bg-[rgba(220,38,38,0.08)] hover:text-white transition-all text-[0.9rem]" onClick={() => { skinCameraRef.current?.click(); setShowAttachmentMenu(false); }}>
                      <Camera className="w-[1.15rem] h-[1.15rem] text-[#dc2626] w-[22px]" /><span>Take Photo</span>
                    </button>
                    <button className="flex items-center gap-3 px-4 py-3 rounded-[10px] text-white/80 hover:bg-[rgba(220,38,38,0.08)] hover:text-white transition-all text-[0.9rem]" onClick={() => { skinFileInputRef.current?.click(); setShowAttachmentMenu(false); }}>
                      <ImagePlus className="w-[1.15rem] h-[1.15rem] text-[#dc2626] w-[22px]" /><span>Choose from Gallery</span>
                    </button>
                    <div className="h-px bg-[rgba(220,38,38,0.15)] my-2" />
                    <div className="px-4 py-2 text-[0.7rem] text-white/35 uppercase tracking-[1px]">Lab Report</div>
                    <button className="camera-option flex items-center gap-3 px-4 py-3 rounded-[10px] text-white/80 hover:bg-[rgba(220,38,38,0.08)] hover:text-white transition-all text-[0.9rem]" onClick={() => { labCameraRef.current?.click(); setShowAttachmentMenu(false); }}>
                      <Camera className="w-[1.15rem] h-[1.15rem] text-[#dc2626] w-[22px]" /><span>Take Photo</span>
                    </button>
                    <button className="flex items-center gap-3 px-4 py-3 rounded-[10px] text-white/80 hover:bg-[rgba(220,38,38,0.08)] hover:text-white transition-all text-[0.9rem]" onClick={() => { labFileInputRef.current?.click(); setShowAttachmentMenu(false); }}>
                      <FileText className="w-[1.15rem] h-[1.15rem] text-[#dc2626] w-[22px]" /><span>Upload Files</span>
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Hidden file inputs */}
              <input type="file" ref={skinFileInputRef} className="hidden" accept="image/*" onChange={handleDirectSkinUpload} />
              <input type="file" ref={skinCameraRef} className="hidden" accept="image/*" capture="environment" onChange={handleDirectSkinUpload} />
              <input type="file" ref={labFileInputRef} className="hidden" multiple onChange={handleDirectLabUpload} />
              <input type="file" ref={labCameraRef} className="hidden" accept="image/*" capture="environment" onChange={handleDirectLabUpload} />

              {/* Input form */}
              <form onSubmit={handleSendMessage}
                className="flex items-center gap-[0.65rem] bg-white/[0.025] border border-white/[0.08] rounded-[28px] px-3 py-[0.4rem] focus-within:border-[rgba(220,38,38,0.35)] focus-within:bg-white/[0.04] focus-within:shadow-[0_0_30px_rgba(220,38,38,0.06)] transition-all">
                <button ref={plusBtnRef} type="button" disabled={isRecording} onClick={() => setShowAttachmentMenu(!showAttachmentMenu)} title="Add attachments"
                  className="w-10 h-10 bg-transparent border-none rounded-full text-white/45 hover:bg-white/[0.08] hover:text-[#dc2626] flex items-center justify-center flex-shrink-0 disabled:opacity-50 transition-colors">
                  <Plus className={`w-5 h-5 transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] ${showAttachmentMenu ? 'rotate-[585deg] text-[#dc2626]' : 'rotate-0'}`} />
                </button>
                <textarea ref={inputRef} rows={1} value={inputVal}
                  onChange={(e) => { setInputVal(e.target.value); e.target.style.height = 'auto'; e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`; }}
                  onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (inputVal.trim()) handleSendMessage(e as any); } }}
                  placeholder="Ask about symptoms, remedies, or health concerns..."
                  style={{ maxHeight: '120px' }}
                  className="flex-1 bg-transparent border-none text-white text-base outline-none py-3 px-2 font-sans resize-none overflow-y-auto min-h-[24px] leading-[1.5] placeholder-white/30"
                />
                <button type="button" onClick={toggleVoiceInput} title={isRecording ? 'Stop' : 'Voice input'}
                  className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 transition-all ${isRecording ? 'pulseRec' : 'bg-transparent text-white/45 hover:bg-white/[0.08] hover:text-[#dc2626]'}`}>
                  {isRecording ? <Square className="w-5 h-5 fill-current" /> : <Mic className="w-5 h-5" />}
                </button>
                {inputVal.trim() && (
                  <button type="submit" className="w-10 h-10 rounded-full bg-gradient-to-br from-[#dc2626] to-[#991b1b] text-white hover:scale-[1.08] transition-all flex items-center justify-center flex-shrink-0 shadow-[0_2px_12px_var(--color-primary-glow)]">
                    <Send className="w-5 h-5" />
                  </button>
                )}
              </form>
            </motion.div>
          )}
        </div>
      </div>
    </main>
  );
}
