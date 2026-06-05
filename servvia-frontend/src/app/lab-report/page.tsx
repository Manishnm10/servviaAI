'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { UploadCloud, CheckCircle, AlertTriangle, FileText, ArrowRight, ShieldCheck, Activity } from 'lucide-react';

type FlowState = 'UPLOAD' | 'VERIFYING' | 'ANALYZING' | 'DASHBOARD';

export default function CoPilotPage() {
  const [flowState, setFlowState] = useState<FlowState>('UPLOAD');
  const [file, setFile] = useState<File | null>(null);
  const [identityData, setIdentityData] = useState<any>(null);
  const [reportId, setReportId] = useState<number | null>(null);
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState('');

  // 1. Upload Phase
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;
    setFile(selectedFile);
    setFlowState('VERIFYING');
    setErrorMsg('');

    try {
      const formData = new FormData();
      formData.append('report', selectedFile);
      formData.append('email_id', 'mr.razak.test@example.com'); // Mock auth email

      const res = await fetch('/api/proxy/lab-report/identify/', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer test_token' },
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to identify report');

      setIdentityData(data.identity);
      setReportId(data.pending_report_id);
    } catch (err: any) {
      setErrorMsg(err.message);
      setFlowState('UPLOAD');
    }
  };

  // 2. Confirm Phase
  const handleConfirm = async () => {
    setFlowState('ANALYZING');
    setErrorMsg('');

    try {
      const payload = {
        pending_report_id: reportId,
        create_profile: true,
        profile_label: identityData?.patient_name || 'My Health',
      };

      const res = await fetch('/api/proxy/lab-report/confirm/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer test_token',
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to run analysis');

      setDashboardData(data);
      setFlowState('DASHBOARD');
    } catch (err: any) {
      setErrorMsg(err.message);
      setFlowState('VERIFYING');
    }
  };

  return (
    <main className="min-h-screen text-foreground p-8 flex flex-col items-center">
      {/* Header */}
      <div className="w-full max-w-5xl mb-12 flex justify-between items-center pb-6 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary to-primary-dark flex items-center justify-center shadow-[0_0_16px_var(--color-primary-glow)]">
            <Activity className="text-white w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-primary">
              ServVia AI
            </h1>
            <p className="text-xs text-muted tracking-widest uppercase">Clinical Co-Pilot</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-green-500" />
          <span className="text-sm text-muted">HIPAA Compliant</span>
        </div>
      </div>

      <div className="w-full max-w-5xl relative min-h-[60vh] flex flex-col items-center justify-center">
        
        {/* Error Message */}
        {errorMsg && (
          <div className="absolute top-0 w-full max-w-md p-4 bg-red-900/30 border border-red-500/50 rounded-xl text-red-200 text-sm text-center mb-8">
            {errorMsg}
          </div>
        )}

        <AnimatePresence mode="wait">
          
          {/* UPLOAD STATE */}
          {flowState === 'UPLOAD' && (
            <motion.div
              key="upload"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="w-full max-w-2xl glass-panel p-12 text-center rounded-2xl flex flex-col items-center border-[var(--color-border)]"
            >
              <div className="w-20 h-20 bg-primary/10 rounded-full flex items-center justify-center mb-6">
                <UploadCloud className="w-10 h-10 text-primary" />
              </div>
              <h2 className="text-3xl font-bold mb-4">Upload Lab Report</h2>
              <p className="text-muted mb-8 max-w-md">
                Securely upload your clinical PDF. Our Neuro-Symbolic AI will extract identity and map temporal biomarkers.
              </p>
              
              <label className="cursor-pointer relative overflow-hidden group">
                <div className="absolute inset-0 bg-gradient-to-r from-primary to-primary-dark rounded-xl opacity-90 transition-opacity group-hover:opacity-100"></div>
                <div className="px-8 py-4 flex items-center gap-3 relative z-10 text-white font-semibold">
                  <FileText className="w-5 h-5" />
                  Select PDF Document
                </div>
                <input 
                  type="file" 
                  accept=".pdf,.png,.jpg" 
                  className="hidden" 
                  onChange={handleFileUpload} 
                />
              </label>
            </motion.div>
          )}

          {/* VERIFYING POPUP */}
          {flowState === 'VERIFYING' && (
            <motion.div
              key="verifying"
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 1.05, opacity: 0 }}
              className="w-full max-w-md glass-panel p-8 rounded-2xl relative overflow-hidden"
            >
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-primary via-primary-dark to-transparent"></div>
              
              {!identityData ? (
                <div className="flex flex-col items-center py-8">
                  <div className="w-10 h-10 border-4 border-primary/30 border-t-primary rounded-full animate-spin mb-6"></div>
                  <h3 className="text-xl font-semibold">Identity Fingerprinting...</h3>
                  <p className="text-sm text-muted mt-2">Extracting demographic data securely.</p>
                </div>
              ) : (
                <div className="flex flex-col items-center">
                  <div className="w-16 h-16 bg-primary/20 rounded-full flex items-center justify-center mb-6 text-primary shadow-[0_0_20px_var(--color-primary-glow)]">
                    <CheckCircle className="w-8 h-8" />
                  </div>
                  <h3 className="text-2xl font-bold mb-2">Profile Match Found</h3>
                  <p className="text-muted text-center mb-8 text-sm">
                    No existing profile found. Create a new patient profile for this identity?
                  </p>
                  
                  <div className="w-full bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-4 mb-8">
                    <div className="flex justify-between py-2 border-b border-white/5">
                      <span className="text-muted text-sm">Patient Name</span>
                      <span className="font-semibold">{identityData.patient_name || 'Unknown'}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-white/5">
                      <span className="text-muted text-sm">Age/Sex</span>
                      <span className="font-semibold">{identityData.age || '--'} / {identityData.sex || '--'}</span>
                    </div>
                    <div className="flex justify-between py-2">
                      <span className="text-muted text-sm">Patient ID</span>
                      <span className="font-semibold">{identityData.patient_id || identityData.srf_id || 'N/A'}</span>
                    </div>
                  </div>

                  <button 
                    onClick={handleConfirm}
                    className="w-full py-4 bg-gradient-to-r from-primary to-primary-dark rounded-xl font-bold flex items-center justify-center gap-2 hover:-translate-y-1 transition-transform shadow-[0_8px_30px_rgba(220,38,38,0.45)]"
                  >
                    Confirm & Analyze <ArrowRight className="w-5 h-5" />
                  </button>
                </div>
              )}
            </motion.div>
          )}

          {/* ANALYZING */}
          {flowState === 'ANALYZING' && (
            <motion.div
              key="analyzing"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center py-20"
            >
              <div className="relative w-32 h-32 mb-8">
                <div className="absolute inset-0 bg-primary/20 rounded-full animate-ping"></div>
                <div className="absolute inset-2 glass rounded-full flex items-center justify-center">
                  <Activity className="w-10 h-10 text-primary animate-pulse" />
                </div>
              </div>
              <h2 className="text-2xl font-bold mb-2">Co-Pilot Processing</h2>
              <p className="text-muted text-center max-w-sm">
                Running neuro-symbolic triage and comparing biomarkers against historical temporal state.
              </p>
            </motion.div>
          )}

          {/* DASHBOARD */}
          {flowState === 'DASHBOARD' && dashboardData && (
            <motion.div
              key="dashboard"
              initial={{ opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              className="w-full grid grid-cols-1 md:grid-cols-3 gap-6"
            >
              {/* Left Column: Triage & Action Plan */}
              <div className="md:col-span-1 flex flex-col gap-6">
                
                <div className="glass-panel p-6 rounded-2xl">
                  <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                    <AlertTriangle className="w-5 h-5 text-red-500" /> Triage Alerts
                  </h3>
                  
                  {dashboardData.triage?.red_flags?.length > 0 && (
                    <div className="mb-4">
                      <span className="text-xs font-bold text-red-400 uppercase tracking-wider mb-2 block">Red Flags (Review Required)</span>
                      {dashboardData.triage.red_flags.map((flag: any, i: number) => (
                        <div key={i} className="p-3 bg-red-950/40 border border-red-500/30 rounded-xl mb-2">
                          <p className="font-bold text-sm text-red-200">{flag.biomarker}</p>
                          <p className="text-xs text-red-300 mt-1">{flag.reason}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {dashboardData.triage?.yellow_flags?.length > 0 && (
                    <div>
                      <span className="text-xs font-bold text-amber-400 uppercase tracking-wider mb-2 block">Yellow Flags (Lifestyle)</span>
                      {dashboardData.triage.yellow_flags.map((flag: any, i: number) => (
                        <div key={i} className="p-3 bg-amber-950/20 border border-amber-500/20 rounded-xl mb-2 flex items-start">
                          <div className="w-2 h-2 rounded-full bg-amber-500 mt-1.5 mr-2 shrink-0"></div>
                          <div>
                            <p className="font-semibold text-sm text-amber-100">{flag.biomarker}</p>
                            <p className="text-xs text-amber-200/70 mt-0.5">{flag.reason}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="glass p-6 rounded-2xl">
                  <h3 className="text-lg font-bold mb-4">Action Plan</h3>
                  <div className="space-y-4">
                    <div>
                      <h4 className="text-sm font-semibold text-muted mb-2">Clinical Follow-ups</h4>
                      <ul className="text-sm space-y-2">
                        {dashboardData.action_plan?.clinical_followups?.map((item: string, i: number) => (
                          <li key={i} className="flex gap-2 text-gray-300"><span className="text-primary">•</span>{item}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="h-px bg-[var(--color-border)] w-full"></div>
                    <div>
                      <h4 className="text-sm font-semibold text-muted mb-2">Lifestyle & Nutrition</h4>
                      <ul className="text-sm space-y-2">
                        {dashboardData.action_plan?.lifestyle?.map((item: string, i: number) => (
                          <li key={i} className="flex gap-2 text-gray-300"><span className="text-primary">•</span>{item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>

              </div>

              {/* Right Column: System Groups */}
              <div className="md:col-span-2 flex flex-col gap-6">
                
                <div className="glass-panel p-6 rounded-2xl flex justify-between items-center bg-gradient-to-r from-[var(--color-surface)] to-primary/5">
                  <div>
                    <p className="text-sm text-muted">Test Type</p>
                    <p className="text-xl font-bold">{dashboardData.test_type}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-muted">Abnormal Biomarkers</p>
                    <p className="text-2xl font-bold text-red-500">{dashboardData.abnormal_count} <span className="text-lg text-muted">/ {dashboardData.normal_count + dashboardData.abnormal_count}</span></p>
                  </div>
                </div>

                {dashboardData.system_groups?.map((group: any, i: number) => (
                  <div key={i} className="glass p-6 rounded-2xl">
                    <h3 className="text-lg font-bold mb-4">{group.system}</h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm text-left">
                        <thead className="text-xs text-muted uppercase bg-white/5 border-b border-[var(--color-border)]">
                          <tr>
                            <th className="px-4 py-3 rounded-tl-lg">Biomarker</th>
                            <th className="px-4 py-3">Value</th>
                            <th className="px-4 py-3">Reference</th>
                            <th className="px-4 py-3 rounded-tr-lg">Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {group.biomarkers.map((bm: any, j: number) => (
                            <tr key={j} className="border-b border-white/5 last:border-0 hover:bg-white/5 transition-colors">
                              <td className="px-4 py-3 font-medium text-gray-200">{bm.name}</td>
                              <td className="px-4 py-3">{bm.value} <span className="text-muted text-xs">{bm.unit}</span></td>
                              <td className="px-4 py-3 text-muted text-xs">{bm.reference_range}</td>
                              <td className="px-4 py-3">
                                <span className={`px-2 py-1 rounded-md text-xs font-bold ${
                                  bm.status === 'high' ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 
                                  bm.status === 'low' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : 
                                  'bg-green-500/10 text-green-400 border border-green-500/20'
                                }`}>
                                  {bm.status.toUpperCase()}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}

              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </main>
  );
}
