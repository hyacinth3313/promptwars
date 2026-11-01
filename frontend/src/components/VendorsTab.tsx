import { useFeedback } from './Feedback';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import axios from 'axios';
import { ArrowDown, Check, CircleAlert, ClipboardPaste, FileText, GitCompareArrows, HeartHandshake, LoaderCircle, RefreshCw, Sparkles } from 'lucide-react';
import { Button, Card } from './ui';
import VendorCard, { type VendorQuestionsState } from './VendorCard';
import VendorComparison from './VendorComparison';
import { apiError, plannerApi } from '../lib/api';
import { parseVendorQuestions, vendorCategories, vendorQuestionsPrompt, vendorSignature, type VendorCategory } from '../lib/vendors';
import { sampleVendorQuotes } from '../lib/vendorDemo';
import { cn } from '../lib/utils';
import type { EventState, VendorQuote } from '../types';

interface Props { state: EventState; onStateChange: (state: EventState) => void }
export default function VendorsTab({ state, onStateChange }: Props) {
  const id = state.config.session_id;
  const isDemo = id === 'demo';
  const [text, setText] = useState('');
  const [category, setCategory] = useState<VendorCategory>('catering');
  const [view, setView] = useState<'quotes' | 'compare'>('quotes');
  const [busy, setBusy] = useState<'analyze' | 'refresh' | null>(null);
  const busyRef = useRef(false);
  const [error, setError] = useState('');
  const [textError, setTextError] = useState('');
  const [notice, setNotice] = useState('');
  useFeedback(error, notice);
  const [needsRefresh, setNeedsRefresh] = useState(false);
  const [questions, setQuestions] = useState<Record<string, VendorQuestionsState>>({});
  const questionRequests = useRef(new Set<string>());
  const textarea = useRef<HTMLTextAreaElement>(null);
  const resultHeading = useRef<HTMLHeadingElement>(null);
  const errorSummary = useRef<HTMLDivElement>(null);
  useEffect(() => { if (error) errorSummary.current?.focus(); }, [error]);

  function finish() { busyRef.current = false; setBusy(null); }
  async function refresh() {
    if (busyRef.current) return;
    busyRef.current = true; setBusy('refresh'); setError(''); setNotice('');
    try { onStateChange(await plannerApi.getSession(id)); setNeedsRefresh(false); setNotice('Your saved vendor quotes are up to date.'); }
    catch (err) { setError(apiError(err)); } finally { finish(); }
  }
  function loadSample(index: number) {
    setText(sampleVendorQuotes[index].text); setCategory('catering'); setTextError(''); setError(''); setNotice('');
    textarea.current?.focus();
  }
  async function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busyRef.current || needsRefresh) return;
    if (text.trim().length < 10) { setTextError('Paste a little more of the quote — at least 10 characters — so we can find the details.'); textarea.current?.focus(); return; }
    busyRef.current = true; setBusy('analyze'); setError(''); setNotice(''); setTextError('');
    let saved = false;
    try {
      let quote: VendorQuote;
      if (isDemo) {
        const sample = sampleVendorQuotes.find(sample => sample.text.trim() === text.trim() && sample.quote.category === category);
        if (!sample) { setError('This sample event uses the two example quotes below. Load a sample to explore, or start a real event to analyze your own quote.'); return; }
        quote = structuredClone(sample.quote);
        if (state.vendors.some(vendor => vendorSignature(vendor) === vendorSignature(quote))) { setNotice('That sample quote is already in your vendor list. Try the other sample to compare.'); setView('quotes'); return; }
      } else quote = await plannerApi.analyzeVendor(id, { quote_text: text.trim(), category });
      // /analyze-vendor already persists the result. Do not POST or PATCH it again.
      saved = true; onStateChange({ ...state, vendors: [...state.vendors, quote] });
      setText(''); setView('quotes'); setNotice(`A little clarity, ready for you. ${quote.vendor_name} has been added to your quotes.`);
      if (!isDemo) onStateChange(await plannerApi.getSession(id));
      resultHeading.current?.focus();
    } catch (err) {
      if (saved) { setNeedsRefresh(true); setError('Your analyzed quote was saved, but we couldn’t refresh the full list. Refresh saved quotes before analyzing another.'); }
      else if (axios.isAxiosError(err) && err.response) setError(apiError(err));
      else {
        // A connection can fail after the server saves a quote. Check the saved list
        // before offering a retry so the same quote is not silently appended twice.
        try {
          const latest = await plannerApi.getSession(id); onStateChange(latest);
          if (latest.vendors.length > state.vendors.length) { setView('quotes'); setNotice('A newly saved quote is in your vendor list. Your pasted text is kept here while you review the latest cards before analyzing again.'); }
          else setError(apiError(err));
        } catch { setNeedsRefresh(true); setError('We couldn’t confirm whether the quote was saved. Your pasted text is still here. Refresh saved quotes before trying again.'); }
      }
    } finally { finish(); }
  }
  async function askQuestions(vendor: VendorQuote, key: string) {
    if (questionRequests.current.has(key)) return;
    questionRequests.current.add(key);
    setQuestions(previous => ({ ...previous, [key]: { loading: true, error: '', questions: previous[key]?.questions || [] } }));
    try {
      let list: string[];
      if (isDemo) {
        list = sampleVendorQuotes.find(sample => vendorSignature(sample.quote) === vendorSignature(vendor))?.questions || ['What is the final tax-inclusive amount?', 'What service hours and extras are included?', 'What are the payment and cancellation terms?'];
      } else {
        const reply = await plannerApi.chat(id, { message: vendorQuestionsPrompt(vendor) });
        list = parseVendorQuestions(reply.reply);
      }
      if (!list.length) {
        setQuestions(previous => ({ ...previous, [key]: { loading: false, questions: previous[key]?.questions || [], error: 'The planner didn’t return a clear question list this time. Try again in a moment.' } }));
      } else setQuestions(previous => ({ ...previous, [key]: { loading: false, questions: list, error: '' } }));
    } catch (err) { setQuestions(previous => ({ ...previous, [key]: { loading: false, questions: previous[key]?.questions || [], error: apiError(err) } })); }
    finally { questionRequests.current.delete(key); }
  }

  return <section aria-labelledby="vendors-title" className="space-y-7">
    <div><p className="eyebrow">GOOD PEOPLE. CLEARER POSSIBILITIES.</p><h2 id="vendors-title" className="mt-2 font-display text-[28px] font-semibold tracking-[-1px]">From messy quotes to lovely clarity.</h2><p className="mt-2 max-w-2xl text-sm leading-7 text-muted">Paste the email, the fine print, the little details. We’ll bring the important pieces together, so you can find the people who fit your celebration.</p></div>
    <Card className="overflow-hidden"><div className="grid lg:grid-cols-[1.65fr_1fr]"><form noValidate onSubmit={analyze} className="p-6 sm:p-8" aria-busy={busy === 'analyze'}><div className="mb-6 flex items-start gap-3"><span className="icon-tile !h-11 !w-11 shrink-0 bg-lavender"><ClipboardPaste size={21}/></span><div><h3 className="font-display text-xl font-bold">A little help with the fine print.</h3><p className="mt-2 text-xs leading-6 text-muted">Vendor emails, itemized quotes, and informal messages all belong here.</p></div></div>
      <label htmlFor="vendor-category">Service category<select id="vendor-category" value={category} onChange={event => setCategory(event.target.value as VendorCategory)} disabled={!!busy || needsRefresh} className="mb-5">{vendorCategories.map(category => <option key={category.value} value={category.value}>{category.label}</option>)}</select></label>
      <label htmlFor="vendor-quote-text">Paste your vendor quote<textarea ref={textarea} id="vendor-quote-text" name="quote_text" rows={9} required minLength={10} value={text} onChange={event => { setText(event.target.value); setTextError(''); }} disabled={!!busy || needsRefresh} className="vendor-quote-input" placeholder={'Hi! Sharing a quote for your celebration…\nDinner for 150 guests, setup, service staff…\nAdvance payment, taxes, extra hours…\n\nPaste everything. We’ll help make sense of it.'} aria-invalid={!!textError} aria-describedby={textError ? 'vendor-quote-error' : 'vendor-quote-help'}/></label>
      {textError && <p id="vendor-quote-error" role="alert" className="mt-2 text-xs leading-6 text-[#986552]">{textError}</p>}<div id="vendor-quote-help" className="mt-3 flex flex-wrap justify-between gap-2 text-[10px] text-muted"><span>No need to tidy it up first.</span><span>{text.length.toLocaleString('en-IN')} characters</span></div>
      {isDemo && <div className="mt-5 rounded-2xl bg-powder/50 p-4"><p className="text-[11px] leading-6 text-muted">Sample mode uses fixed examples so you can explore without a backend. Try both for a comparison.</p><div className="mt-2 flex flex-wrap gap-2">{sampleVendorQuotes.map((sample, index) => <button key={index} type="button" disabled={!!busy} onClick={() => loadSample(index)} className="rounded-xl bg-white/80 px-3 py-2 text-[10px] shadow-button hover:-translate-y-0.5 disabled:opacity-50">Sample {index + 1}: {sample.quote.vendor_name}</button>)}</div></div>}
      {busy === 'analyze' && <div role="status" className="mt-5 flex items-start gap-3 rounded-2xl bg-lavender/50 p-4"><LoaderCircle size={18} className="mt-1 shrink-0 animate-spin text-lilac"/><div><p className="text-sm font-medium">A little clarity is on its way…</p><p className="mt-1 text-xs leading-6 text-muted">Finding the figures, the inclusions, and the details tucked between the lines.</p></div></div>}
      <div className="mt-6 flex flex-wrap items-center justify-between gap-4"><p className="text-[10px] leading-5 text-muted">Your analyzed quote will join your vendor list below.</p><Button type="submit" disabled={!!busy || needsRefresh} className="w-full justify-center sm:w-auto">{busy === 'analyze' ? <><LoaderCircle size={16} className="animate-spin"/>Analyzing Quote…</> : <><Sparkles size={16}/>Analyze Quote</>}</Button></div>
    </form><aside className="flex flex-col justify-center bg-[#edf1eb] p-7 sm:p-9"><span className="icon-tile bg-mint"><HeartHandshake size={25}/></span><p className="eyebrow mt-7">THE RIGHT PEOPLE, IN THE DETAILS</p><h3 className="mt-3 font-display text-2xl font-semibold leading-9 tracking-[-.5px]">A clearer quote.<br/>A calmer conversation.</h3><ul className="mt-6 space-y-4">{['See the full picture, piece by piece.', 'Spot fees that deserve a second look.', 'Compare inclusions and payment terms.', 'Know just what to ask next.'].map(item => <li key={item} className="flex items-start gap-2 text-xs leading-6 text-muted"><Check size={14} className="mt-1 shrink-0 text-[#7da18a]"/>{item}</li>)}</ul><p className="mt-7 rounded-2xl bg-white/55 p-4 text-[11px] leading-6 text-muted">Analysis organizes the quote for your review. It doesn’t confirm a booking or mark the contract as verified.</p></aside></div></Card>
    {error && needsRefresh && <div ref={errorSummary} tabIndex={-1} role="alert" className="flex items-start gap-3 rounded-2xl bg-peach p-5 text-sm leading-6"><CircleAlert size={19} className="mt-1 shrink-0 text-[#986552]"/><div><p>{error}</p>{needsRefresh && <Button disabled={!!busy} onClick={refresh} variant="secondary" className="mt-3 text-xs"><RefreshCw size={14} className={busy === 'refresh' ? 'animate-spin' : ''}/>{busy === 'refresh' ? 'Refreshing saved quotes…' : 'Refresh saved quotes'}</Button>}</div></div>}
    {busy === 'refresh' && <p role="status" className="flex items-center gap-2 text-xs text-lilac"><LoaderCircle size={14} className="animate-spin"/>Gathering your saved quotes…</p>}
    <div className="flex flex-wrap items-end justify-between gap-5"><div><h3 ref={resultHeading} tabIndex={-1} className="font-display text-2xl font-semibold tracking-[-.7px]">Your people, coming into focus<span className="text-lilac">.</span></h3><p className="mt-2 text-xs text-muted">{state.vendors.length} analyzed {state.vendors.length === 1 ? 'quote' : 'quotes'} · {state.vendors.reduce((sum, vendor) => sum + vendor.hidden_fees.length, 0)} fees flagged for a closer look</p></div>{state.vendors.length >= 2 && <div className="flex gap-1 rounded-2xl bg-[#eeebe7] p-1.5" role="group" aria-label="Vendor view"><button aria-pressed={view === 'quotes'} onClick={() => setView('quotes')} className={cn('flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs', view === 'quotes' && 'bg-white shadow-button')}><FileText size={14}/>Quote details</button><button aria-pressed={view === 'compare'} onClick={() => setView('compare')} className={cn('flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs', view === 'compare' && 'bg-white shadow-button')}><GitCompareArrows size={14}/>Compare quotes</button></div>}</div>
    {state.vendors.length === 0 ? <Card className="flex flex-col items-center px-6 py-14 text-center"><span className="icon-tile bg-powder"><FileText size={24}/></span><h3 className="mt-6 font-display text-xl font-semibold">The first quote is a lovely place to start.</h3><p className="mt-3 max-w-md text-sm leading-7 text-muted">Paste a vendor message above to see the details here. Add a second quote to explore a side-by-side comparison.</p><button onClick={() => textarea.current?.focus()} className="mt-5 flex items-center gap-2 rounded-lg p-2 text-xs text-lilac">Start with a quote <ArrowDown size={14} className="rotate-180"/></button></Card> : view === 'compare' && state.vendors.length >= 2 ? <VendorComparison vendors={state.vendors}/> : <><div className="grid items-start gap-6 lg:grid-cols-2">{state.vendors.map((vendor, index) => {
      const key = `${index}:${vendorSignature(vendor)}`;
      return <VendorCard key={key} vendor={vendor} index={index} guestCount={state.config.guest_count} isDemo={isDemo} questions={questions[key]} onQuestions={() => askQuestions(vendor, key)}/>;
    })}</div>{state.vendors.length === 1 && <p className="text-center text-xs leading-6 text-muted">Add one more quote to see prices, fees, and inclusions side by side.</p>}</>}
  </section>;
}
