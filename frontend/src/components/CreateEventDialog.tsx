import { useEffect, useRef, useState, type CSSProperties, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Check, CircleAlert, Heart, LoaderCircle, RotateCcw, Sparkles, X } from 'lucide-react';
import { Button } from './ui';
import { apiError, plannerApi } from '../lib/api';
import { defaultPriorities, prioritiesAreValid, priorityCategories, rebalancePriorities } from '../lib/priorities';
import type { EventType } from '../types';

interface IntakeFields { type: EventType; date: string; location: string; budget: string; guests: string }
type FieldErrors = Partial<Record<keyof IntakeFields | 'priorities', string>>;
function localToday() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

export default function CreateEventDialog({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const errorSummary = useRef<HTMLDivElement>(null);
  const sessionId = useRef<string>();
  const submitting = useRef(false);
  const navigate = useNavigate();
  const [fields, setFields] = useState<IntakeFields>({ type: 'wedding', date: '', location: '', budget: '', guests: '' });
  const [priorities, setPriorities] = useState({ ...defaultPriorities });
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const total = Object.values(priorities).reduce((sum, value) => sum + value, 0);
  useEffect(() => {
    dialog.current?.showModal();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = previousOverflow; };
  }, []);
  useEffect(() => { if (error) errorSummary.current?.focus(); }, [error]);
  function update<K extends keyof IntakeFields>(key: K, value: IntakeFields[K]) {
    setFields(current => ({ ...current, [key]: value }));
    setFieldErrors(current => ({ ...current, [key]: undefined }));
    setError('');
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current) return;
    const errors: FieldErrors = {};
    if (!fields.date || !Number.isFinite(Date.parse(fields.date)) || fields.date < localToday()) errors.date = 'Choose today or a date in the future.';
    if (!fields.location.trim()) errors.location = 'Add a city or venue for your celebration.';
    if (!Number.isFinite(Number(fields.budget)) || Number(fields.budget) <= 0) errors.budget = 'Add a budget greater than ₹0.';
    if (!Number.isSafeInteger(Number(fields.guests)) || Number(fields.guests) < 1) errors.guests = 'Add at least one guest, using a whole number.';
    if (!prioritiesAreValid(priorities)) errors.priorities = 'Your priorities need to add up to 100%. Try resetting the sliders.';
    setFieldErrors(errors); setError('');
    if (Object.keys(errors).length) {
      dialog.current?.querySelector<HTMLElement>(`[name="${Object.keys(errors)[0]}"]`)?.focus();
      return;
    }
    submitting.current = true; setBusy(true);
    try {
      sessionId.current ??= (await plannerApi.createSession()).session_id;
      await plannerApi.initialize({
        session_id: sessionId.current, event_type: fields.type, event_date: fields.date,
        location: fields.location.trim(), total_budget: Number(fields.budget), guest_count: Number(fields.guests), currency: 'INR',
        priorities: Object.fromEntries(priorityCategories.map(({ key }) => [key, priorities[key] / 100])),
      });
      navigate(`/planner/${encodeURIComponent(sessionId.current)}`);
    } catch (err) { setError(apiError(err)); } finally { submitting.current = false; setBusy(false); }
  }
  const fieldError = (key: keyof IntakeFields) => fieldErrors[key] && <span id={`error-${key}`} className="mt-2 block text-xs leading-5 text-[#9b594d]">{fieldErrors[key]}</span>;

  return <dialog ref={dialog} onCancel={event => { if (submitting.current) event.preventDefault(); else onClose(); }} className="event-dialog intake-dialog rounded-3xl bg-cream text-charcoal" aria-labelledby="create-title" aria-describedby="create-description">
    <button disabled={busy} onClick={onClose} className="absolute right-5 top-5 z-10 rounded-full bg-white/70 p-2 text-muted transition hover:bg-lavender disabled:opacity-40" aria-label="Close event setup"><X size={20}/></button>
    <div className="intake-heading"><span className="icon-tile !h-12 !w-12 bg-lavender"><Sparkles size={23}/></span><div><p className="eyebrow">A LITTLE ABOUT YOUR BIG DAY</p><h2 id="create-title" className="mt-2 font-display text-[27px] font-bold leading-tight tracking-[-.8px] sm:text-[32px]">Let’s make it feel like you.</h2><p id="create-description" className="mt-3 text-sm leading-6 text-muted">A few thoughtful details. A plan full of possibilities.</p></div></div>
    <form noValidate onSubmit={submit} aria-busy={busy}>
      <fieldset disabled={busy} className="intake-columns">
        <section aria-labelledby="event-details-heading" className="intake-section">
          <div className="mb-6 flex items-center gap-3"><span className="intake-step bg-peach">01</span><div><h3 id="event-details-heading" className="font-display text-base font-bold">Set the scene</h3><p className="mt-1 text-xs text-muted">Every lovely detail starts somewhere.</p></div></div>
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <label className="sm:col-span-2" htmlFor="intake-type">Event type<select id="intake-type" name="type" value={fields.type} onChange={event => update('type', event.target.value as EventType)}><option value="wedding">Wedding</option><option value="birthday">Birthday</option><option value="corporate">Corporate</option><option value="community">Community</option><option value="other">Other</option></select></label>
            <label className="sm:col-span-2" htmlFor="intake-date">Event date<input id="intake-date" required type="date" name="date" min={localToday()} value={fields.date} onChange={event => update('date', event.target.value)} aria-invalid={!!fieldErrors.date} aria-describedby={fieldErrors.date ? 'error-date' : undefined}/>{fieldError('date')}</label>
            <label className="sm:col-span-2" htmlFor="intake-location">Location<input id="intake-location" required name="location" maxLength={200} value={fields.location} onChange={event => update('location', event.target.value)} placeholder="City or venue, e.g. Bengaluru" autoComplete="address-level2" aria-invalid={!!fieldErrors.location} aria-describedby={fieldErrors.location ? 'error-location' : undefined}/>{fieldError('location')}</label>
            <label htmlFor="intake-budget">Total budget<span className="currency-input"><span aria-hidden="true">₹</span><input id="intake-budget" aria-label="Total budget in Indian rupees" required type="number" inputMode="decimal" name="budget" min="0.01" step="any" value={fields.budget} onChange={event => update('budget', event.target.value)} placeholder="500000" aria-invalid={!!fieldErrors.budget} aria-describedby={fieldErrors.budget ? 'error-budget' : undefined}/></span>{fieldError('budget')}</label>
            <label htmlFor="intake-guests">Guest count<input id="intake-guests" required type="number" inputMode="numeric" name="guests" min="1" step="1" value={fields.guests} onChange={event => update('guests', event.target.value)} placeholder="150" aria-invalid={!!fieldErrors.guests} aria-describedby={fieldErrors.guests ? 'error-guests' : undefined}/>{fieldError('guests')}</label>
          </div><p className="mt-5 flex items-center gap-2 text-[11px] leading-5 text-muted"><Heart size={13} className="shrink-0 text-[#b18fa3]"/> No detail too small. No celebration too you.</p>
        </section>
        <section aria-labelledby="priorities-heading" className="intake-section priority-section">
          <div className="mb-5 flex items-center gap-3"><span className="intake-step bg-mint">02</span><div><h3 id="priorities-heading" className="font-display text-base font-bold">Make room for what matters</h3><p className="mt-1 text-xs text-muted">Tell us where you’d love to spend a little more.</p></div></div>
          <div className="mb-5 flex items-center justify-between gap-3"><span className="rounded-full bg-mint px-3 py-1.5 text-[11px] font-semibold text-[#4c715b]"><Check size={12} className="mr-1 inline"/>{total}% allocated</span><button type="button" onClick={() => setPriorities({ ...defaultPriorities })} className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] text-muted hover:text-charcoal"><RotateCcw size={12}/> Reset</button></div>
          <div className="space-y-5">{priorityCategories.map(({ key, label, color, hint }) => <div key={key} className="priority-row" style={{ '--slider-color': color, '--slider-progress': `${priorities[key]}%` } as CSSProperties}>
            <div className="flex items-center justify-between"><label htmlFor={`priority-${key}`} className="text-xs font-semibold">{label}</label><output htmlFor={`priority-${key}`} className="priority-value" aria-hidden="true">{priorities[key]}<span className="ml-0.5 text-[10px]">%</span></output></div>
            <input id={`priority-${key}`} name={key === 'catering' ? 'priorities' : `priority-${key}`} className="priority-slider" type="range" min="0" max="100" step="1" value={priorities[key]} aria-valuetext={`${priorities[key]} percent; other categories adjust automatically`} aria-describedby="priority-explanation" onChange={event => { setPriorities(current => rebalancePriorities(current, key, Number(event.target.value))); setFieldErrors(current => ({ ...current, priorities: undefined })); }}/>
            <p className="text-[10px] text-muted">{hint}</p>
          </div>)}</div>
          <p id="priority-explanation" className="mt-5 rounded-xl bg-white/75 p-3 text-[11px] leading-5 text-muted">Slide toward what you love. The other priorities gently rebalance to keep your total at 100%.</p>
          {fieldErrors.priorities && <p role="alert" className="mt-3 text-xs text-[#9b594d]">{fieldErrors.priorities}</p>}
        </section>
      </fieldset>
      <div className="intake-actions">
        {error && <div ref={errorSummary} tabIndex={-1} role="alert" className="mb-5 flex items-start gap-3 rounded-2xl bg-peach p-4 text-sm leading-6"><CircleAlert size={19} className="mt-0.5 shrink-0 text-[#9b7260]"/><div><p className="font-semibold">Your details are safe here. Let’s try again.</p><p className="mt-1 text-xs leading-5 text-muted">{error}</p></div></div>}
        <div className="flex flex-col items-center justify-between gap-4 sm:flex-row"><p className="max-w-[270px] text-center text-xs leading-5 text-muted sm:text-left">A thoughtful budget. A clear timeline.<br/>More space for the moments that matter.</p><Button disabled={busy} type="submit" className="w-full justify-center px-6 py-4 sm:w-auto">{busy ? <><LoaderCircle className="shrink-0 animate-spin" size={18}/><span role="status">Creating your personalized plan…</span></> : <>Create my event plan <ArrowRight size={18}/></>}</Button></div>
        {busy && <p className="mt-4 text-center text-xs text-lilac" role="status">We’re bringing your budget and timeline together. This may take a moment.</p>}
      </div>
    </form>
  </dialog>;
}
