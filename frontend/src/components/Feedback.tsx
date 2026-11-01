import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { Check, HeartHandshake, X } from 'lucide-react';
import { cn } from '../lib/utils';

type Toast = { id: number; message: string; kind: 'success' | 'error' };
const FeedbackContext = createContext<(message: string, kind: Toast['kind']) => void>(() => {});

function ToastCard({ toast, dismiss }: { toast: Toast; dismiss: (id: number) => void }) {
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    // Errors stay available until dismissed. Pause success dismissal for reading or keyboard use.
    if (toast.kind === 'error' || paused) return;
    const timer = window.setTimeout(() => dismiss(toast.id), 8000);
    return () => window.clearTimeout(timer);
  }, [toast, paused, dismiss]);
  return <div role={toast.kind === 'error' ? 'alert' : 'status'} aria-atomic="true" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)} onFocus={() => setPaused(true)} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setPaused(false); }} className={cn('pointer-events-auto max-h-[40dvh] overflow-y-auto flex items-start gap-3 rounded-2xl border border-white p-4 shadow-clay', toast.kind === 'error' ? 'bg-[#fae9df]' : 'bg-[#e5f0e8]')}>
    {toast.kind === 'error' ? <HeartHandshake size={20} className="mt-1 shrink-0 text-[#986552]"/> : <Check size={20} className="mt-1 shrink-0 text-[#527760]"/>}
    <p className="min-w-0 flex-1 text-sm leading-6">{toast.message}</p><button type="button" onClick={() => dismiss(toast.id)} aria-label="Dismiss notification" className="-mr-2 -mt-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-xl hover:bg-white/60"><X size={16}/></button>
  </div>;
}

export function FeedbackProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const sequence = useRef(0);
  const dismiss = useCallback((id: number) => setToasts(current => current.filter(toast => toast.id !== id)), []);
  const notify = useCallback((message: string, kind: Toast['kind']) => {
    const next = { id: ++sequence.current, message, kind };
    setToasts(current => [...current.filter(toast => toast.message !== message).slice(-1), next]);
  }, []);
  return <FeedbackContext.Provider value={notify}>{children}<aside aria-label="Planner notifications" className="toast-stack pointer-events-none fixed z-50 flex w-[calc(100%-2rem)] max-w-md flex-col gap-3">{toasts.map(toast => <ToastCard key={toast.id} toast={toast} dismiss={dismiss}/>)}</aside></FeedbackContext.Provider>;
}

export function useFeedback(error = '', notice = '') {
  const notify = useContext(FeedbackContext);
  useEffect(() => { if (error) notify(error, 'error'); }, [error, notify]);
  useEffect(() => { if (notice) notify(notice, 'success'); }, [notice, notify]);
}

export function PlannerSkeleton() {
  return <section role="status" aria-label="Gathering your event details" className="space-y-8"><p className="flex items-center gap-3 text-sm text-muted"><span className="h-3 w-3 animate-pulse rounded-full bg-lilac"/>Gathering your event details…</p><div aria-hidden="true" className="space-y-8"><div className="space-y-4"><div className="skeleton h-4 w-40"/><div className="skeleton h-10 w-4/5"/><div className="skeleton h-4 w-1/2"/></div><div className="skeleton h-16 w-full"/><div className="grid gap-5 md:grid-cols-3">{[0, 1, 2].map(item => <div key={item} className="rounded-3xl bg-white/70 p-7 shadow-clay"><div className="skeleton h-4 w-2/3"/><div className="skeleton my-6 h-9 w-1/2"/><div className="skeleton h-3 w-3/4"/></div>)}</div><div className="skeleton h-52 w-full"/></div></section>;
}
