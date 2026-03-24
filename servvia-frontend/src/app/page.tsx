'use client';

import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, Plus, Mic, Send, ImagePlus, FileText, User, HeartPulse, ShieldCheck, ChevronRight, Volume2, Bot } from 'lucide-react';
import { AmbientBackground } from '@/components/AmbientBackground';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

type AppState = 'LOGIN' | 'ONBOARDING' | 'CHAT';

const formatPhaseLabel = (p?: string) => { 
  if (!p) return '';
  return p.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
};

export default function AppHome() {
  const router = useRouter();
  const [appState, setAppState] = useState<AppState>('LOGIN');
  const [email, setEmail] = useState('');
  const [profileForm, setProfileForm] = useState({ name: '', history: '' });
  const [messages, setMessages] = useState<any[]>([]);
  const [inputVal, setInputVal] = useState('');
  const [showAttachmentMenu, setShowAttachmentMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const skinFileInputRef = useRef<HTMLInputElement>(null);
  const labFileInputRef = useRef<HTMLInputElement>(null);

  const handleSpeech = (text: string) => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      if (window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel();
      } else {
        const utterance = new SpeechSynthesisUtterance(text.replace(/[*#_`]/g, ''));
        window.speechSynthesis.speak(utterance);
      }
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>, type: 'skin' | 'lab') => {
    const file = e.target.files?.[0];
    if (!file) return;
    setInputVal(`[Attached ${type === 'skin' ? 'Skin Photo' : 'Lab Report'}: ${file.name}] `);
    setShowAttachmentMenu(false);
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowAttachmentMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (appState === 'CHAT') scrollToBottom();
  }, [messages, appState]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;

    try {
      // Real API proxy call to Django
      const res = await fetch(`/api/proxy/profile/profile/check_profile/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email_id: email.trim() })
      });
      
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }

      if (data.exists && data.is_complete && data.profile) {
        setProfileForm({ 
          name: data.profile.first_name || email.split('@')[0], 
          history: data.profile.medical_conditions || '' 
        });
        setAppState('CHAT');
      } else {
        setAppState('ONBOARDING');
      }
    } catch (err: any) {
      console.error(err);
      alert(`ServVia Backend Error: ${err.message}. Please ensure your python Django server is running on localhost:9000!`);
    }
  };

  const handleOnboardingSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profileForm.name) return;

    try {
      const res = await fetch(`/api/proxy/profile/profile/create_or_update_profile/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          email_id: email.trim(), 
          first_name: profileForm.name, 
          medical_conditions: profileForm.history,
          allergies: "",
          current_medications: ""
        })
      });
      const data = await res.json();
      if (data.success) {
        setAppState('CHAT');
      } else {
        alert("Error saving profile");
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    const msg = inputVal.trim();
    if (!msg) return;

    setMessages(prev => [...prev, { type: 'user', text: msg }]);
    setInputVal('');

    // Pre-insert an empty AI message to stream into
    setMessages(prev => [...prev, { type: 'ai', text: "", isStreaming: true, stage: "Connecting...", completedStages: [] }]);

    try {
      const response = await fetch(`/api/proxy/chat/stream/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email_id: email, query: msg }),
      });

      if (!response.ok || !response.body) throw new Error("Stream Failed");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.substring(7).trim();
          } else if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.substring(6));

              setMessages(prev => {
                if (prev.length === 0) return prev;
                const newMsgs = [...prev];
                const lastIdx = newMsgs.length - 1;
                const lastMsg = { ...newMsgs[lastIdx] };
                if (lastMsg.type !== 'ai') return prev;

                if (currentEvent === "stage") {
                  if (data.id !== "streaming") {
                    if (lastMsg.stage && lastMsg.stage !== "Connecting...") {
                      if (!lastMsg.completedStages) lastMsg.completedStages = [];
                      if (!lastMsg.completedStages.includes(lastMsg.stage)) {
                        lastMsg.completedStages.push(lastMsg.stage);
                      }
                    }
                    lastMsg.stage = data.label;
                  }
                } else if (currentEvent === "token") {
                  lastMsg.stage = null;
                  lastMsg.text += (data.text || "");
                } else if (currentEvent === "emergency") {
                  lastMsg.stage = null;
                  lastMsg.text = data.response || "";
                  if (data.pipeline) lastMsg.pipelineData = data;
                } else if (currentEvent === "done") {
                  lastMsg.isStreaming = false;
                  lastMsg.pipelineData = data; // the backend sends full metadata on 'done'
                }
                
                newMsgs[lastIdx] = lastMsg;
                return newMsgs;
              });
            } catch (err) {}
          }
        }
      }
      
      // Mark done on close
      setMessages(prev => {
        const msgs = [...prev];
        msgs[msgs.length - 1].isStreaming = false;
        return msgs;
      });

    } catch (err) {
      console.error(err);
      setMessages(prev => {
        const msgs = [...prev];
        msgs[msgs.length - 1].text = "Connection lost to ServVia Agent.";
        msgs[msgs.length - 1].isStreaming = false;
        msgs[msgs.length - 1].stage = null;
        return msgs;
      });
    }
  };

  return (
    <main className="w-full h-screen overflow-hidden relative text-white selection:bg-primary/30 font-sans">
      <AmbientBackground isVisible={appState === 'LOGIN' || appState === 'ONBOARDING'} />

      {/* ── CENTRALIZED LAYOUT CONTAINER matching the legacy index.html ── */}
      <div className="max-w-[1200px] mx-auto h-screen flex flex-col relative z-10">
        
        {/* ── PERSISTENT HEADER ── */}
        <header className="flex items-center justify-between px-8 py-5 border-b border-[var(--color-border)] bg-[#050505]/85 backdrop-blur-xl">
          <div className="flex flex-col sm:flex-row sm:items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-primary to-primary-dark flex items-center justify-center shadow-[0_0_16px_var(--color-primary-glow)]">
              <HeartPulse className="text-white w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-primary">ServVia</h1>
              <p className="text-[0.7rem] text-muted tracking-[0.2em] uppercase">AI Healthcare Intelligence</p>
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div className={`flex flex-col items-end gap-1 ${appState !== 'LOGIN' ? 'flex' : 'hidden md:flex'}`}>
              <span className="font-semibold text-base capitalize">{profileForm.name || (appState === 'LOGIN' ? 'Guest user' : 'User')}</span>
            </div>
            {appState !== 'LOGIN' && (
              <button 
                onClick={() => setAppState('ONBOARDING')}
                className="hidden md:flex items-center gap-2 px-4 py-2 rounded-xl bg-primary/10 border border-[var(--color-border)] text-[var(--color-primary)] text-sm font-medium hover:bg-white/5 transition-all"
              >
                <User className="w-4 h-4" /> Edit Profile
              </button>
            )}
            <div className="flex items-center gap-2 text-sm text-gray-300">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse shadow-[0_0_8px_#22c55e]"></div>
              Online
            </div>
          </div>
        </header>

        {/* ── MAIN CHAT/STATE WRAPPER ── */}
        <div className="flex-1 flex flex-col overflow-hidden px-8 py-6">
          
          <div id="chat" className="flex-1 overflow-y-auto overflow-x-hidden p-8 bg-transparent border border-[var(--color-border)] transition-all rounded-[20px] relative mb-5 scrollbar-thin scrollbar-thumb-primary/20 scrollbar-track-transparent">
            
            <AnimatePresence mode="wait">
              {/* === LOGIN SCREEN === */}
              {appState === 'LOGIN' && (
                <motion.div 
                  key="login-screen"
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0 }}
                  className="min-h-[400px] flex flex-col items-center justify-center text-center h-full"
                >
                  <div className="w-full max-w-md relative mx-auto p-[2px] rounded-3xl group shadow-[0_0_40px_rgba(220,38,38,0.15)]">
                    {/* The Spinning Conic Gradient Masked Container */}
                    <div className="absolute inset-0 overflow-hidden rounded-3xl pointer-events-none">
                      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[250%] h-[250%] animate-[spin_8s_linear_infinite] bg-[conic-gradient(from_0deg,transparent_0_300deg,var(--color-primary)_360deg)] opacity-90" />
                    </div>
                    
                    {/* Inner Card */}
                    <div className="relative w-full h-full bg-[#080808]/95 backdrop-blur-2xl p-10 rounded-[calc(1.5rem-2px)] z-10 flex flex-col items-center text-left">
                      <div className="text-4xl mb-6 text-primary drop-shadow-[0_0_15px_var(--color-primary-glow)]">
                        <HeartPulse className="w-12 h-12" />
                      </div>
                      
                      <h2 className="text-3xl font-extrabold mb-2 bg-clip-text text-transparent bg-gradient-to-br from-white to-primary w-full text-center">Welcome to ServVia</h2>
                      <p className="text-muted mb-8 text-[1.1rem] w-full text-center">Your Personalized AI Health Companion</p>
                      
                      <form onSubmit={handleLogin} className="w-full space-y-5">
                        <div className="w-full">
                          <input 
                            type="email" 
                            required
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="Enter your email address"
                            className="w-full bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[14px] px-5 py-4 text-white text-base placeholder-white/25 outline-none focus:bg-white/5 focus:border-primary focus:ring-[3px] focus:ring-primary/10 transition-all font-sans"
                          />
                        </div>
                        <button 
                          type="submit"
                          className="w-full py-4 bg-gradient-to-br from-primary to-primary-dark rounded-[14px] font-bold hover:shadow-[0_8px_30px_rgba(220,38,38,0.45)] hover:-translate-y-[2px] transition-all flex items-center justify-center text-base"
                        >
                          Continue
                        </button>
                      </form>
                    </div>
                  </div>
                </motion.div>
              )}

              {/* === ONBOARDING SCREEN === */}
              {appState === 'ONBOARDING' && (
                <motion.div 
                  key="onboarding-screen"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="min-h-[400px] flex flex-col items-center justify-center text-center h-full"
                >
                  <div className="text-4xl mb-6 text-primary animate-[pulse_3s_ease-in-out_infinite]">
                    <Activity className="w-16 h-16 inline-block" />
                  </div>
                  <h2 className="text-3xl font-extrabold mb-3 bg-clip-text text-transparent bg-gradient-to-br from-white to-primary">Tell Us About Yourself</h2>
                  <p className="text-[1.1rem] text-muted mb-10 max-w-md mx-auto">This helps us provide safe, personalized health recommendations.</p>
                  
                  <div className="w-full max-w-lg text-left">
                    <form onSubmit={handleOnboardingSubmit} className="space-y-6">
                      <div>
                        <label className="text-sm font-medium text-white/80 block mb-2">What's your name?</label>
                        <input 
                          required
                          type="text" 
                          value={profileForm.name}
                          onChange={(e) => setProfileForm({...profileForm, name: e.target.value})}
                          placeholder="Your first name"
                          className="w-full bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[14px] px-5 py-4 text-white placeholder-white/25 outline-none focus:border-primary transition-all font-sans"
                        />
                      </div>
                      <div>
                        <label className="text-sm font-medium text-white/80 block mb-2 flex items-center gap-2">
                          <Activity className="w-4 h-4 text-primary" /> Any existing medical conditions?
                        </label>
                        <textarea 
                          required
                          rows={3}
                          value={profileForm.history}
                          onChange={(e) => setProfileForm({...profileForm, history: e.target.value})}
                          placeholder="e.g., diabetes, hypertension (or leave blank)"
                          className="w-full bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[14px] px-5 py-4 text-white placeholder-white/25 outline-none focus:border-primary transition-all resize-y min-h-[100px] font-sans"
                        />
                        <p className="text-[0.75rem] text-muted mt-2">This helps us recommend safe remedies.</p>
                      </div>
                      <button 
                        type="submit"
                        className="w-full mt-4 py-4 bg-gradient-to-br from-primary to-primary-dark rounded-[14px] font-bold hover:shadow-[0_8px_30px_rgba(220,38,38,0.45)] hover:-translate-y-[2px] transition-all flex items-center justify-center gap-2"
                      >
                        <ShieldCheck className="w-5 h-5" /> Save Profile & Continue
                      </button>
                    </form>
                  </div>
                </motion.div>
              )}

              {/* === CHAT MESSAGES SCREEN === */}
              {appState === 'CHAT' && (
                <motion.div 
                  key="chat-messages"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="w-full h-full flex flex-col"
                >
                  {/* WELCOME STATE */}
                  {messages.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-10 my-auto">
                      <div className="text-5xl mb-6 text-primary drop-shadow-[0_0_15px_var(--color-primary-glow)]">
                        <HeartPulse className="w-16 h-16 inline-block" />
                      </div>
                      <h2 className="text-3xl font-bold mb-3 text-white">Welcome back, {profileForm.name || 'Razak'}!</h2>
                      <p className="text-muted text-lg mb-8">ServVia — Multi-Agent AI Verified Healthcare</p>
                      
                      {/* Agent Flow Indicator */}
                      <div className="flex flex-wrap items-center justify-center gap-3 text-xs font-semibold mb-12">
                        <span className="px-4 py-2 rounded-full bg-[#8b5cf6]/10 border border-[#8b5cf6]/25 text-[#a78bfa] flex items-center gap-2 tracking-wide">
                          <Activity className="w-3.5 h-3.5" /> Proposer
                        </span>
                        <span className="text-white/20">→</span>
                        <span className="px-4 py-2 rounded-full bg-[#3b82f6]/10 border border-[#3b82f6]/25 text-[#60a5fa] flex items-center gap-2 tracking-wide">
                          <Activity className="w-3.5 h-3.5" /> Critic
                        </span>
                        <span className="text-white/20">→</span>
                        <span className="px-4 py-2 rounded-full bg-[#22c55e]/10 border border-[#22c55e]/25 text-[#4ade80] flex items-center gap-2 tracking-wide shadow-[0_0_10px_rgba(34,197,94,0.15)]">
                          <ShieldCheck className="w-4 h-4" /> Verified
                        </span>
                      </div>

                      <p className="text-muted font-medium">How can I help you today?</p>
                    </div>
                  )}

                  {/* CHAT MESSAGES */}
                  <div className="flex flex-col gap-6 pb-4">
                    {messages.map((msg, idx) => (
                      <motion.div 
                        initial={{ opacity: 0, y: 16 }}
                        animate={{ opacity: 1, y: 0 }}
                        key={idx} 
                        className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'} clear-both block w-full`}
                      >
                        {msg.type === 'user' ? (
                          <div className="max-w-[82%] px-6 py-4 bg-gradient-to-br from-primary to-primary-dark text-white rounded-[20px] rounded-tr-[4px] shadow-[0_4px_16px_rgba(220,38,38,0.25)] leading-relaxed">
                            {msg.text}
                          </div>
                        ) : msg.isStreaming && !msg.text ? (
                          <div className="bg-[#0f1115] border border-white/5 rounded-[12px] p-5 flex flex-col min-w-[340px] shadow-[0_4px_20px_rgba(0,0,0,0.5)]">
                            {msg.completedStages && msg.completedStages.length > 0 && (
                              <div className="flex flex-col gap-3.5 mb-5 pb-5 border-b border-white/[0.05]">
                                {msg.completedStages.map((s: string, i: number) => (
                                  <div key={i} className="flex items-center gap-3 text-[0.85rem] text-[#059669] font-medium tracking-wide">
                                    <div className="w-5 h-5 rounded-full bg-[#059669]/10 border border-[#059669]/20 flex items-center justify-center">
                                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                                    </div>
                                    <span className="text-white/40">{s}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                            
                            <div className="flex items-center gap-3 text-[0.95rem] font-bold text-primary tracking-wide">
                              <Activity className="w-[1.2rem] h-[1.2rem] animate-pulse drop-shadow-[0_0_8px_var(--color-primary-glow)]" />
                              {msg.stage || 'Connecting...'}
                              <span className="flex gap-[0.15rem] ml-1 opacity-70 mt-1">
                                <motion.span animate={{ opacity: [0.2, 1, 0.2] }} transition={{ repeat: Infinity, duration: 1.4, delay: 0 }}>.</motion.span>
                                <motion.span animate={{ opacity: [0.2, 1, 0.2] }} transition={{ repeat: Infinity, duration: 1.4, delay: 0.2 }}>.</motion.span>
                                <motion.span animate={{ opacity: [0.2, 1, 0.2] }} transition={{ repeat: Infinity, duration: 1.4, delay: 0.4 }}>.</motion.span>
                              </span>
                            </div>
                          </div>
                        ) : (
                          <div className="max-w-[85%] bg-white/[0.025] border border-[var(--color-border)] text-white rounded-[20px] rounded-tl-[4px] leading-[1.8] flex flex-col group overflow-hidden shadow-lg p-0">
                            {/* MARKDOWN ENGINE - Always visible if not in streaming trail mode */}
                            <div className="p-6">
                              <div className="prose prose-invert max-w-none text-[0.95rem]">
                                  <ReactMarkdown 
                                    remarkPlugins={[remarkGfm]}
                                    components={{
                                      h1: ({node, ...props}) => <h1 className="text-2xl font-bold mt-6 mb-4 text-white" {...props}/>,
                                      h2: ({node, ...props}) => <h2 className="text-xl font-bold mt-6 mb-3 text-primary border-b border-white/10 pb-2 flex items-center gap-2" {...props}/>,
                                      h3: ({node, ...props}) => {
                                        // Specific UI override for standard medical action cards
                                        const childrenArr = React.Children.toArray(props.children);
                                        const text = childrenArr.join('').toLowerCase();
                                        if (text.includes('when to see a doctor')) {
                                          return <div className="bg-[#0f1115] border-l-[3px] border-teal-500 rounded-[8px] p-4 my-5"><h3 className="text-lg font-bold text-white shadow-none" {...props}/></div>
                                        }
                                        return <h3 className="text-lg font-bold mt-5 mb-2 text-white border-l-[3px] border-primary pl-4 bg-primary/5 py-3 rounded-r-lg" {...props}/>
                                      },
                                      p: ({node, ...props}) => <p className="text-white/90 leading-relaxed mb-4" {...props}/>,
                                      ul: ({node, ...props}) => <ul className="list-disc leading-relaxed text-white/90 pl-6 mb-4 space-y-2 marker:text-primary" {...props}/>,
                                      ol: ({node, ...props}) => <ol className="list-decimal leading-relaxed text-white/90 pl-6 mb-4 space-y-2 marker:text-primary" {...props}/>,
                                      li: ({node, ...props}) => <li className="" {...props}/>,
                                      strong: ({node, ...props}) => <strong className="font-bold text-[#dc2626]" {...props}/>,
                                      a: ({node, ...props}) => <a className="text-blue-400 hover:text-blue-300 underline underline-offset-2" target="_blank" rel="noopener noreferrer" {...props}/>,
                                      blockquote: ({node, ...props}) => <blockquote className="border-l-[3px] border-primary/50 pl-4 py-1 italic bg-white/5 rounded-r-lg text-white/70" {...props}/>,
                                      code: ({node, ...props}) => <code className="bg-black/40 text-primary-light px-1.5 py-0.5 rounded text-sm font-mono border border-white/5" {...props}/>,
                                    }}
                                  >
                                    {msg.text?.replace(/<br\s*\/?>/gi, '\n\n')}
                                  </ReactMarkdown>
                                </div>

                                {/* PIPELINE METADATA CARDS */}
                                {msg.pipelineData && (
                                  <div className="mt-8 flex flex-col gap-4">
                                    {/* Emergency / Safety Block Banners */}
                                    {msg.pipelineData.pipeline === 'emergency_intercept' && (
                                      <div className="p-4 rounded-[12px] flex items-center gap-3 font-semibold border shadow-[0_0_15px_rgba(239,68,68,0.15)] bg-red-500/10 border-red-500/30 text-[#fca5a5]">
                                        <ShieldCheck className="w-5 h-5"/> Emergency Protocol Triggered
                                      </div>
                                    )}
                                    {msg.pipelineData.pipeline === 'safety_blocked' && (
                                      <div className="p-4 rounded-[12px] flex items-center gap-3 font-semibold border shadow-lg bg-[#1a1a1a]/80 border-white/10 text-[#a3a3a3]">
                                        <Activity className="w-5 h-5"/> Safety Engine Blocked Action
                                      </div>
                                    )}

                                    {/* Biological Context Card */}
                                    {msg.pipelineData.bio_state && (
                                      <div className="flex flex-col md:flex-row items-center gap-4 p-5 rounded-[16px] bg-[#1a1a24]/50 border border-indigo-500/20 relative overflow-hidden backdrop-blur-md">
                                        <div className="absolute top-0 right-0 w-40 h-40 bg-indigo-500/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3 pointer-events-none"></div>
                                        <div className="w-12 h-12 rounded-[14px] bg-indigo-500/10 text-indigo-400 flex items-center justify-center flex-shrink-0 shadow-[0_0_15px_rgba(99,102,241,0.15)] border border-indigo-500/20">
                                          <Activity className="w-6 h-6" />
                                        </div>
                                        <div className="flex flex-col gap-2 w-full">
                                          <div className="text-[0.8rem] font-bold text-indigo-300 uppercase tracking-[0.15em] opacity-90">Biological Context</div>
                                          <div className="flex flex-wrap gap-2 text-xs font-semibold">
                                            <span className="px-3 py-1.5 rounded-lg bg-black/40 border border-white/5 text-white/80 shadow-inner">{formatPhaseLabel(msg.pipelineData.bio_state.circadian_phase)}</span>
                                            <span className="px-3 py-1.5 rounded-lg bg-black/40 border border-white/5 text-white/80 shadow-inner">{formatPhaseLabel(msg.pipelineData.bio_state.seasonal_influence)}</span>
                                            <span className="px-3 py-1.5 rounded-lg bg-black/40 border border-white/5 text-white/80 shadow-inner">Sleep: {formatPhaseLabel(msg.pipelineData.bio_state.sleep_pressure)}</span>
                                            {msg.pipelineData.bio_state.is_misaligned && (
                                              <span className="px-3 py-1.5 rounded-lg bg-red-500/15 border border-red-500/25 text-[#fca5a5] font-bold tracking-wide animate-pulse shadow-[0_0_10px_rgba(239,68,68,0.15)]">Misaligned Phase</span>
                                            )}
                                          </div>
                                        </div>
                                      </div>
                                    )}

                                    {/* Safety Block Card */}
                                    {msg.pipelineData.safety && !msg.pipelineData.safety.is_safe && (
                                      <div className="flex flex-col gap-3 p-5 rounded-[16px] bg-red-950/30 border border-red-500/25 relative overflow-hidden backdrop-blur-md">
                                        <div className="flex items-center gap-2 font-extrabold text-[#fca5a5] border-b border-red-500/20 pb-3 text-sm tracking-wide uppercase">
                                          <ShieldCheck className="w-4 h-4" /> Safety Details
                                        </div>
                                        <div className="flex flex-col gap-2 text-[0.95rem] tracking-wide mt-1">
                                          {msg.pipelineData.safety.blocked_herb && (
                                            <div className="flex items-start gap-2"><span className="text-white/50 w-24 flex-shrink-0">Blocked:</span> <span className="text-white font-medium">{msg.pipelineData.safety.blocked_herb}</span></div>
                                          )}
                                          {msg.pipelineData.safety.washout_days_remaining ? (
                                            <div className="flex items-start gap-2"><span className="text-white/50 w-24 flex-shrink-0">Washout:</span> <span className="text-[#fca5a5] font-bold">{msg.pipelineData.safety.washout_days_remaining} day(s)</span></div>
                                          ): null}
                                          {msg.pipelineData.safety.contraindications && msg.pipelineData.safety.contraindications.length > 0 && (
                                            <div className="flex items-start gap-2"><span className="text-white/50 w-24 flex-shrink-0">Interactions:</span> <span className="text-white/90 leading-relaxed font-medium">{msg.pipelineData.safety.contraindications.join(', ')}</span></div>
                                          )}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>

                            {/* TTS ACTIONS BAR */}
                            {!msg.isStreaming && msg.text && (
                              <div className="bg-black/20 px-6 py-3 border-t border-white/5 flex justify-end gap-2 group-hover:opacity-100 opacity-60 transition-opacity">
                                <button 
                                  onClick={() => handleSpeech(msg.text)}
                                  title="Listen" 
                                  className="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 hover:shadow-[0_0_15px_rgba(255,255,255,0.1)] text-white/50 hover:text-white transition-all flex items-center justify-center border border-transparent hover:border-white/10"
                                >
                                  <Volume2 className="w-[1.1rem] h-[1.1rem]" />
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

          {/* ── STICKY INPUT BAR CONTAINER ── */}
          {appState === 'CHAT' && (
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="w-full relative px-8 flex justify-center mb-6"
            >
              <div className="w-full relative">
                
                {/* ATTACHMENT MENU POPUP */}
                <AnimatePresence>
                  {showAttachmentMenu && (
                    <motion.div 
                      ref={menuRef}
                      initial={{ opacity: 0, scale: 0.95, y: 10 }}
                      animate={{ opacity: 1, scale: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.95, y: 10 }}
                      className="absolute bottom-full left-0 mb-3 bg-[#0a0a0a]/95 backdrop-blur-xl border border-[var(--color-border)] rounded-[16px] p-2 min-w-[200px] shadow-[0_12px_40px_rgba(0,0,0,0.6)] flex flex-col gap-1 z-40"
                    >
                      <div className="px-4 py-2 text-[0.7rem] text-white/35 uppercase tracking-widest font-semibold border-b border-primary/15 mb-1">
                        Analysis Tools
                      </div>
                      
                      <input type="file" ref={labFileInputRef} className="hidden" onChange={(e) => handleFileSelect(e, 'lab')} multiple accept=".pdf,.png,.jpg,.jpeg" />
                      <button 
                        onClick={() => labFileInputRef.current?.click()}
                        className="flex items-center gap-3 px-4 py-3 rounded-xl bg-transparent hover:bg-primary/10 text-white/80 hover:text-white transition-all text-left group border border-transparent hover:border-primary/20"
                      >
                        <FileText className="w-5 h-5 text-primary" />
                        <span className="text-[0.9rem] font-medium">Lab Report</span>
                      </button>
                      
                      <input type="file" ref={skinFileInputRef} className="hidden" onChange={(e) => handleFileSelect(e, 'skin')} accept="image/*" />
                      <button 
                        onClick={() => skinFileInputRef.current?.click()}
                        className="flex items-center gap-3 px-4 py-3 rounded-xl bg-transparent hover:bg-primary/10 text-white/80 hover:text-white transition-all text-left group border border-transparent hover:border-primary/20"
                      >
                        <ImagePlus className="w-5 h-5 text-primary" />
                        <span className="text-[0.9rem] font-medium">Skin Photo</span>
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* ACTUAL INPUT FORM */}
                <form 
                  onSubmit={handleSendMessage}
                  className="flex items-center gap-2.5 w-full bg-white/[0.025] border border-white/10 rounded-[28px] pl-3 pr-4 py-[0.4rem] shadow-lg focus-within:border-primary/35 focus-within:bg-white/[0.04] focus-within:shadow-[0_0_30px_rgba(220,38,38,0.06)] transition-all relative z-30"
                >
                  <button 
                    type="button" 
                    onClick={() => setShowAttachmentMenu(!showAttachmentMenu)}
                    title="Add attachments"
                    className="w-10 h-10 rounded-full bg-transparent border-none text-white/45 hover:bg-white/5 hover:text-primary transition-all flex items-center justify-center flex-shrink-0"
                  >
                    <Plus className={`w-[1.1rem] h-[1.1rem] transition-transform duration-300 ${showAttachmentMenu ? 'rotate-45 text-primary' : ''}`} />
                  </button>
                  
                  <input 
                    type="text" 
                    value={inputVal}
                    onChange={(e) => setInputVal(e.target.value)}
                    placeholder="Ask about symptoms, remedies, or health concerns..."
                    className="flex-1 bg-transparent py-3 text-[1rem] outline-none text-white placeholder-white/30 font-sans"
                  />
                  
                  {inputVal.trim() ? (
                    <button type="submit" className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-primary-dark text-white hover:-translate-y-px hover:shadow-[0_2px_12px_var(--color-primary-glow)] hover:scale-105 transition-all flex items-center justify-center flex-shrink-0 shadow-[0_2px_12px_var(--color-primary-glow)]">
                      <Send className="w-[1.1rem] h-[1.1rem] -ml-0.5" />
                    </button>
                  ) : (
                    <button type="button" title="Voice input" className="w-10 h-10 rounded-full bg-transparent border-none text-white/45 hover:bg-white/5 hover:text-primary transition-all flex items-center justify-center flex-shrink-0">
                      <Mic className="w-[1.1rem] h-[1.1rem]" />
                    </button>
                  )}
                </form>

              </div>
            </motion.div>
          )}

        </div>
      </div>
    </main>
  );
}
