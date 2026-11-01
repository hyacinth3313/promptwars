import { useFeedback } from './Feedback';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import axios from 'axios';
import { ArrowRight, Check, CircleAlert, GitCompareArrows, LoaderCircle, RefreshCw, RotateCcw, Sparkles, WandSparkles } from 'lucide-react';
import { Button, Card } from './ui';
import ScenarioComparison from './ScenarioComparison';
import { apiError, plannerApi } from '../lib/api';
import { commitDemoScenario, previewDemoScenario } from '../lib/scenarioDemo';
import { validateScenarioInputs, type ScenarioInputErrors, type ScenarioInputs } from '../lib/scenarios';
import { formatTaskDate } from '../lib/timeline';
import { money as formatMoney } from '../lib/utils';
import type { EventState, ScenarioPreviewResponse } from '../types';

interface Props { state: EventState; onStateChange: (state: EventState) => void }
const emptyFields: ScenarioInputs = { budget: '', guests: '', date: '' };
const money = (value: number, currency: string) => formatMoney(value, currency, 2);
export default function WhatIfTab({ state, onStateChange }: Props) {
  const id = state.config.session_id;
  const isDemo = id === 'demo';
  const [fields, setFields] = useState<ScenarioInputs>({ ...emptyFields });
  const [fieldErrors, setFieldErrors] = useState<ScenarioInputErrors>({});
  const [preview, setPreview] = useState<ScenarioPreviewResponse | null>(null);
  const [reviewedInputs, setReviewedInputs] = useState('');
  const [requiresRerun, setRequiresRerun] = useState(false);
  const [busy, setBusy] = useState<'run' | 'commit' | 'refresh' | null>(null);
  const busyRef = useRef(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  useFeedback(error, notice);
  const [needsRefresh, setNeedsRefresh] = useState(false);
  const errorSummary = useRef<HTMLDivElement>(null);
  const form = useRef<HTMLFormElement>(null);
  const previewHeading = useRef<HTMLHeadingElement>(null);
  const dirty = !!preview && reviewedInputs !== JSON.stringify(fields);
  const stale = !!preview && (requiresRerun || state.updated_at !== preview.base_updated_at);
  useEffect(() => { if (error) errorSummary.current?.focus(); }, [error]);

  function begin(action: NonNullable<typeof busy>) {
    if (busyRef.current) return false;
    busyRef.current = true; setBusy(action); setError(''); setNotice(''); return true;
  }
  function finish() { busyRef.current = false; setBusy(null); }
  function update(key: keyof ScenarioInputs, value: string) {
    setFields(previous => ({ ...previous, [key]: value }));
    setFieldErrors(previous => ({ ...previous, [key]: undefined, form: undefined }));
  }
  function acceptCommitted(saved: EventState) {
    onStateChange(saved); setPreview(null); setFields({ ...emptyFields }); setFieldErrors({}); setRequiresRerun(false); setNeedsRefresh(false);
    setNotice('Your new scenario is now the committed plan. Budget, guest count, and timeline are ready across your planner.');
  }
  async function refresh() {
    if (!begin('refresh')) return;
    try {
      const saved = await plannerApi.getSession(id);
      if (preview && saved.last_committed_scenario_id === preview.scenario_id) acceptCommitted(saved);
      else { onStateChange(saved); setNeedsRefresh(false); setNotice('Your saved plan is up to date.'); }
    } catch (err) { setError(apiError(err)); } finally { finish(); }
  }
  async function run(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (needsRefresh || busyRef.current) return;
    const validated = validateScenarioInputs(state, fields);
    setFieldErrors(validated.errors);
    if (Object.keys(validated.errors).length) {
      const first = Object.keys(validated.errors)[0];
      if (first !== 'form') form.current?.querySelector<HTMLElement>(`[name="${first}"]`)?.focus();
      return;
    }
    if (!begin('run')) return;
    let received = false;
    try {
      const result = isDemo ? previewDemoScenario(state, validated.delta) : await plannerApi.whatIf(id, { delta: validated.delta });
      received = true;
      setPreview(result); setReviewedInputs(JSON.stringify(fields)); setRequiresRerun(false);
      // Only the committed baseline is shared with other tabs. The proposed values
      // stay isolated here until /commit-scenario succeeds.
      onStateChange(result.committed_state);
      setNotice('Your scenario is ready. Take a little look at what could change.');
      if (!isDemo) onStateChange(await plannerApi.getSession(id));
      previewHeading.current?.focus();
    } catch (err) {
      if (received) { setNeedsRefresh(true); setError('Your preview is ready, but we couldn’t check the latest saved plan. Refresh the saved plan before committing.'); }
      else setError(apiError(err));
    } finally { finish(); }
  }
  function discard() {
    if (busyRef.current) return;
    setPreview(null); setFields({ ...emptyFields }); setFieldErrors({}); setRequiresRerun(false); if (!needsRefresh) setError(''); setNotice('Back to your committed plan. A fresh possibility is always here when you’re ready.');
  }
  async function commit() {
    if (!preview || dirty || stale || needsRefresh || busyRef.current) return;
    if (Date.now() >= Date.parse(preview.expires_at)) { setRequiresRerun(true); setError('This preview has expired. Run the scenario again to review a fresh plan.'); return; }
    if (!begin('commit')) return;
    let saved = false;
    try {
      const result = isDemo ? commitDemoScenario(preview) : await plannerApi.commitScenario(id, { scenario_id: preview.scenario_id });
      saved = true; acceptCommitted(result);
      if (!isDemo) onStateChange(await plannerApi.getSession(id));
    } catch (err) {
      if (saved) { setNeedsRefresh(true); setError('Your scenario was committed, but we couldn’t refresh the latest saved plan. Refresh it below before exploring another scenario.'); }
      else {
        if (axios.isAxiosError(err) && [404, 409, 410].includes(err.response?.status || 0)) setRequiresRerun(true);
        try {
          const latest = await plannerApi.getSession(id);
          if (latest.last_committed_scenario_id === preview.scenario_id) acceptCommitted(latest);
          else { onStateChange(latest); setError(apiError(err)); }
        } catch { setNeedsRefresh(true); setError('We couldn’t confirm whether the scenario was committed. Refresh the saved plan before trying again.'); }
      }
    } finally { finish(); }
  }
  const fieldError = (key: keyof ScenarioInputs) => fieldErrors[key] && <span id={`scenario-error-${key}`} className="mt-2 block text-xs leading-5 text-[#986552]">{fieldErrors[key]}</span>;

  return <section aria-labelledby="what-if-title" className="space-y-7">
    <div><p className="eyebrow">A LITTLE “WHAT IF”. A WHOLE NEW POSSIBILITY.</p><h2 id="what-if-title" className="mt-2 font-display text-[28px] font-semibold tracking-[-1px]">Room to dream. A plan to come back to.</h2><p className="mt-2 max-w-2xl text-sm leading-7 text-muted">A few more guests? A cozier budget? Explore the ripple effect, see the details together, and choose what feels right.</p></div>
    {isDemo && <p className="flex items-start gap-2 rounded-2xl bg-lavender/35 px-5 py-4 text-xs leading-6 text-muted"><Sparkles size={15} className="mt-1 shrink-0"/>This sample uses a simple local estimate, rather than AI. Committing here only updates the temporary sample event.</p>}
    <Card className="overflow-hidden"><div className="border-b border-white bg-lavender/35 px-6 py-5 sm:px-8"><h3 className="flex items-center gap-2 font-display text-lg font-bold"><WandSparkles size={20} className="text-lilac"/>Let’s try a little something different.</h3><p className="mt-2 text-xs leading-6 text-muted">Current: {money(state.budget.total_budget, state.config.currency)} · {state.config.guest_count} guests · {formatTaskDate(state.config.event_date)}</p></div>
      <form ref={form} onSubmit={run} noValidate className="p-6 sm:p-8" aria-busy={busy === 'run'}><fieldset disabled={!!busy || needsRefresh} className="grid min-w-0 gap-5 md:grid-cols-3"><label htmlFor="scenario-budget">Budget Change<span className="currency-input"><span aria-hidden="true">₹</span><input id="scenario-budget" name="budget" type="text" inputMode="text" value={fields.budget} onChange={event => update('budget', event.target.value)} placeholder="e.g. -100000" aria-invalid={!!fieldErrors.budget} aria-describedby={fieldErrors.budget ? 'scenario-error-budget' : 'scenario-budget-help'}/></span><span id="scenario-budget-help" className="mt-2 block text-[10px] font-normal leading-5 text-muted">Add or subtract from your total budget.</span>{fieldError('budget')}</label><label htmlFor="scenario-guests">Guest Count Delta<input id="scenario-guests" name="guests" type="text" inputMode="text" value={fields.guests} onChange={event => update('guests', event.target.value)} placeholder="e.g. +40 or -25" aria-invalid={!!fieldErrors.guests} aria-describedby={fieldErrors.guests ? 'scenario-error-guests' : 'scenario-guests-help'}/><span id="scenario-guests-help" className="mt-2 block text-[10px] font-normal leading-5 text-muted">More people, or a more intimate gathering.</span>{fieldError('guests')}</label><label htmlFor="scenario-date">Date Change <span className="font-normal text-muted">· optional</span><input id="scenario-date" name="date" type="date" value={fields.date} onChange={event => update('date', event.target.value)} aria-invalid={!!fieldErrors.date} aria-describedby={fieldErrors.date ? 'scenario-error-date' : 'scenario-date-help'}/><span id="scenario-date-help" className="mt-2 block text-[10px] font-normal leading-5 text-muted">Leave blank to keep your current date.</span>{fieldError('date')}</label></fieldset>
        {fieldErrors.form && <p role="alert" className="mt-4 rounded-xl bg-peach/60 p-3 text-xs leading-6">{fieldErrors.form}</p>}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-4"><p className="max-w-sm text-[11px] leading-6 text-muted">A preview gives you a little perspective.<br/>Choose “Commit This Scenario” when it feels right.</p><Button type="submit" disabled={!!busy || needsRefresh} className="w-full justify-center px-8 py-4 md:w-auto">{busy === 'run' ? <><LoaderCircle size={18} className="animate-spin"/>Exploring your possibilities…</> : <><Sparkles size={18}/>Run Scenario <ArrowRight size={16}/></>}</Button></div>
      </form>
    </Card>
    {error && needsRefresh && <div ref={errorSummary} tabIndex={-1} role="alert" className="flex items-start gap-3 rounded-2xl bg-peach p-5 text-sm leading-6"><CircleAlert size={19} className="mt-1 shrink-0 text-[#986552]"/><div><p>{error}</p>{needsRefresh && <Button disabled={!!busy} onClick={refresh} variant="secondary" className="mt-3 text-xs"><RefreshCw size={14} className={busy === 'refresh' ? 'animate-spin' : ''}/>Refresh saved plan</Button>}</div></div>}
    {busy && <div role="status" className="flex items-center gap-3 rounded-3xl bg-lavender/40 p-6 text-sm text-lilac"><span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white/60 shadow-button"><LoaderCircle size={22} className="animate-spin"/></span><div><p className="font-medium">{busy === 'run' ? 'A little magic, coming together…' : busy === 'commit' ? 'Making room for your new plan…' : 'Gathering your saved plan…'}</p><p className="mt-1 text-xs leading-6 text-muted">{busy === 'run' ? 'Considering your budget, your people, and the little steps in between.' : 'We’ll bring the latest details together across your planner.'}</p></div></div>}
    {preview ? <>
      <div><h3 ref={previewHeading} tabIndex={-1} className="flex items-center gap-2 font-display text-2xl font-semibold tracking-[-.5px]"><GitCompareArrows size={22} className="text-lilac"/>Two possibilities. One clear picture.</h3><p className="mt-2 text-xs leading-6 text-muted">Compare the saved baseline with the exact scenario you would be accepting.</p></div>
      {(dirty || stale) && <p role="status" className="rounded-2xl bg-peach/65 px-5 py-4 text-sm leading-6 text-[#8c6554]">{stale ? 'Your saved plan has changed, or this preview needs to be renewed. Run Scenario again before committing.' : 'Your inputs have changed. Run Scenario again to review the new values before committing.'}</p>}
      <ScenarioComparison preview={preview} stale={stale}/>
      <Card className="border border-white bg-[#f8f5f0] p-5 sm:p-6"><div className="flex flex-wrap items-center justify-between gap-5"><div><h3 className="font-display text-base font-bold">Does this feel like your next chapter?</h3><p className="mt-2 text-xs leading-6 text-muted">Commit the previewed budget, guest count, and event date as your saved plan.</p></div><div className="flex w-full flex-wrap gap-3 sm:w-auto"><Button type="button" variant="secondary" disabled={!!busy} onClick={discard} className="flex-1 justify-center text-xs sm:flex-none"><RotateCcw size={14}/>Discard Scenario</Button><Button type="button" disabled={!!busy || dirty || stale || needsRefresh} onClick={commit} className="flex-1 justify-center bg-mint text-xs sm:flex-none">{busy === 'commit' ? <LoaderCircle size={15} className="animate-spin"/> : <Check size={15}/>}Commit This Scenario</Button></div></div></Card>
    </> : <Card className="flex flex-col items-center bg-[#f1ebf5] px-6 py-14 text-center"><span className="icon-tile !h-16 !w-16 bg-white/75"><WandSparkles size={28} className="text-lilac"/></span><p className="eyebrow mt-7">THERE’S ROOM FOR A NEW IDEA</p><h3 className="mt-3 font-display text-2xl font-semibold tracking-[-.5px]">What if it could feel a little different?</h3><p className="mt-4 max-w-lg text-sm leading-7 text-muted">Try a smaller budget, welcome a few more people, or explore a new date. Your comparison will appear here, with the details that deserve a closer look.</p><div className="mt-7 flex flex-wrap justify-center gap-3"><button disabled={!!busy || needsRefresh} onClick={() => { setFields({ ...emptyFields, budget: '-100000' }); setFieldErrors({}); form.current?.querySelector<HTMLElement>('[name="budget"]')?.focus(); }} className="rounded-full bg-white/75 px-4 py-2.5 text-xs shadow-button">Try a cozier budget</button><button disabled={!!busy || needsRefresh} onClick={() => { setFields({ ...emptyFields, guests: '+40' }); setFieldErrors({}); form.current?.querySelector<HTMLElement>('[name="guests"]')?.focus(); }} className="rounded-full bg-white/75 px-4 py-2.5 text-xs shadow-button">A few more lovely people</button></div></Card>}
  </section>;
}
