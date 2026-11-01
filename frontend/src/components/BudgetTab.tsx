import { useFeedback } from './Feedback';
import { useRef, useState } from 'react';
import { BadgeCheck, Check, CircleAlert, Flower2, LoaderCircle, RefreshCw, Sparkles, TrendingDown } from 'lucide-react';
import { Button, Card } from './ui';
import { apiError, plannerApi } from '../lib/api';
import { categoryLabel, categoryProgress, costIncreasePreview, effectiveCost, optionKey, recalculatePreviewBudget } from '../lib/budget';
import { applyDemoTradeoff, demoTradeoffs, overBudgetDemo } from '../lib/budgetDemo';
import { demoState } from '../lib/demo';
import { cn, money } from '../lib/utils';
import type { BudgetItem, EventState, TradeoffOption } from '../types';

interface Props { state: EventState; onStateChange: (state: EventState) => void }
const categoryColors: Record<string, string> = { venue: '#d7c7e7', catering: '#bfdac9', decor: '#efcbbb', photography: '#c4dae7', logistics: '#eac6d3' };

function CategoryCard({ item, currency }: { item: BudgetItem; currency: string }) {
  const { category } = item;
  const progress = categoryProgress(item);
  const verified = item.verified !== null;
  const color = categoryColors[item.category.toLowerCase()] || '#d7c7e7';
  return <article className="budget-category">
    <div className="budget-category-heading"><h3 className="flex items-center gap-3 font-display text-base font-bold"><span className="h-3 w-3 shrink-0 rounded-full shadow-button" style={{ backgroundColor: color }}/>{category.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</h3><span className={cn('rounded-full px-3 py-1 text-[10px]', progress.excess > 0 ? 'bg-peach text-[#8e6252]' : verified ? 'bg-mint text-[#527760]' : 'bg-cream text-muted')}>{progress.excess > 0 ? 'Above allocation' : verified ? 'Cost confirmed' : 'Planning estimate'}</span></div>
    <dl className="my-6 grid grid-cols-3 gap-3"><div><dt className="text-[10px] text-muted">Allocated</dt><dd className="mt-2 break-words text-sm font-semibold sm:text-base">{money(item.allocated, currency)}</dd></div><div><dt className="text-[10px] text-muted">Estimated</dt><dd className="mt-2 break-words text-sm text-muted sm:text-base">{money(item.estimated, currency)}</dd></div><div><dt className="flex items-center gap-1 text-[10px] text-[#527760]">Verified <BadgeCheck size={12}/></dt><dd className={cn('mt-2 break-words text-sm sm:text-base', verified ? 'font-semibold text-[#527760]' : 'text-xs text-muted')}>{verified ? money(item.verified!, currency) : 'Not confirmed'}</dd></div></dl>
    <div className="budget-progress" role="progressbar" aria-label={`${categoryLabel(item.category)} allocation used`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress.width)} aria-valuetext={item.allocated === 0 ? `${money(effectiveCost(item), currency)} projected; no allocation` : `${Math.round(progress.percentage)} percent of allocation; ${verified ? 'verified cost' : 'estimated cost'}`}><span style={{ width: `${progress.width}%`, backgroundColor: progress.excess > 0 ? '#e7b5a4' : color }}/></div>
    <div className="mt-2 flex flex-wrap justify-between gap-2 text-[10px] text-muted"><span>{item.allocated > 0 ? `${Math.round(progress.percentage)}% of allocation` : 'No allocation yet'}</span><span>{progress.excess > 0 ? `${money(progress.excess, currency)} above allocation` : `${money(Math.max(0, item.allocated - effectiveCost(item)), currency)} within allocation`}</span></div>
    <p className="mt-5 border-t border-charcoal/5 pt-4 text-xs leading-6 text-muted"><span className="mr-1 font-medium text-charcoal">Notes:</span>{item.notes || 'A little space for the details as your plan takes shape.'}</p>
  </article>;
}

export default function BudgetTab({ state, onStateChange }: Props) {
  const id = state.config.session_id;
  const isDemo = id === 'demo';
  const [busy, setBusy] = useState<'recalculate' | 'generate' | 'apply' | 'refresh' | 'simulate' | null>(null);
  const busyRef = useRef(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  useFeedback(error, notice);
  const [guidance, setGuidance] = useState('');
  const [needsRefresh, setNeedsRefresh] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const { budget } = state;
  const currency = state.config.currency;
  const totalAllocated = budget.items.reduce((sum, item) => sum + item.allocated, 0);
  const totalEstimated = budget.items.reduce((sum, item) => sum + item.estimated, 0);
  const estimatesOverBudget = Math.round(totalEstimated * 100) > Math.round(budget.total_budget * 100);
  const simulation = costIncreasePreview(budget);
  const applied = new Set(state.applied_tradeoffs.map(optionKey));
  // A package changes the basis for its alternatives. Ask for fresh recommendations
  // after any option from the current batch has been applied, even after a reload.
  const batchAlreadyApplied = state.tradeoff_options.some(option => applied.has(optionKey(option)));
  const options = budget.is_over_budget && !batchAlreadyApplied ? state.tradeoff_options : [];
  const activeSelection = selected && options.some(option => optionKey(option) === selected) ? selected : options.length ? optionKey(options.find(option => option.recommended) || options[0]) : null;
  function begin(action: NonNullable<typeof busy>) {
    if (busyRef.current) return false;
    busyRef.current = true; setBusy(action); setError(''); setNotice(''); return true;
  }
  function finish() { busyRef.current = false; setBusy(null); }
  async function recalculate() {
    if (!begin('recalculate')) return;
    try {
      if (isDemo) {
        const next = { ...state, budget: recalculatePreviewBudget(budget) };
        next.tradeoff_options = next.budget.is_over_budget ? demoTradeoffs(next) : [];
        onStateChange(next);
      } else {
        const result = await plannerApi.recalculateBudget(id);
        onStateChange({ ...state, budget: result.budget, tradeoff_options: result.tradeoffs?.options || [] });
        setGuidance(result.tradeoffs?.guidance_notes || '');
      }
      setSelected(null); setNotice('Your budget is up to date.');
    } catch (err) { setError(apiError(err)); } finally { finish(); }
  }
  async function simulateIncrease() {
    if (budget.is_over_budget || needsRefresh || !simulation || !begin('simulate')) return;
    let saved = false;
    try {
      const current = isDemo ? state : await plannerApi.getSession(id);
      const preview = costIncreasePreview(current.budget);
      if (!preview) {
        onStateChange(current);
        setNotice('Your latest budget has changed. Review it before simulating a cost increase.');
        return;
      }
      let updated: EventState;
      if (isDemo) {
        updated = { ...current, budget: preview.budget, tradeoff_options: [] };
        updated.tradeoff_options = updated.budget.is_over_budget ? demoTradeoffs(updated) : [];
      } else {
        updated = await plannerApi.updateBudgetItems(id, preview.budget.items);
        saved = true;
        onStateChange(updated);
        const result = await plannerApi.recalculateBudget(id);
        updated = { ...updated, budget: result.budget, tradeoff_options: result.tradeoffs?.options || [] };
        setGuidance(result.tradeoffs?.guidance_notes || '');
      }
      onStateChange(updated); setSelected(null);
      setNotice(`${categoryLabel(preview.category)} estimate increased by ${money(preview.increase, currency)}. ${updated.budget.is_over_budget ? 'Your budget is now over its limit. Review the trade-off options below.' : 'Your plan is still within budget. Trade-offs will appear when projected costs exceed your total budget.'}`);
      if (!isDemo) onStateChange(await plannerApi.getSession(id));
    } catch (err) {
      try {
        if (!isDemo) onStateChange(await plannerApi.getSession(id));
        setError(saved ? 'The cost increase was saved, but we couldn’t finish refreshing your options. Use Recalculate budget to continue without adding another increase.' : `${apiError(err)} Your latest budget has been loaded; review the estimate before trying again.`);
      } catch {
        setNeedsRefresh(true);
        setError('We couldn’t confirm whether the increase was saved. Refresh your saved plan before trying again.');
      }
    } finally { finish(); }
  }
  async function generate() {
    if (!begin('generate')) return;
    try {
      if (isDemo) { onStateChange({ ...state, tradeoff_options: demoTradeoffs(state) }); setGuidance('Illustrative options for this sample event. Real suggestions use your event details.'); }
      else {
        const result = await plannerApi.generateTradeoffs(id);
        onStateChange({ ...state, tradeoff_options: result.options }); setGuidance(result.guidance_notes);
        if (!result.options.length) { setNotice('No adjustments were returned this time. Try generating your options again.'); return; }
      }
      setSelected(null); setNotice('Your options are ready. Choose the adjustment that feels right for your event.');
    } catch (err) { setError(apiError(err)); } finally { finish(); }
  }
  async function refresh() {
    if (!begin('refresh')) return;
    try { onStateChange(await plannerApi.getSession(id)); setNeedsRefresh(false); setNotice('Your saved plan is up to date.'); }
    catch (err) { setError(apiError(err)); } finally { finish(); }
  }
  async function apply(option: TradeoffOption) {
    if (needsRefresh || applied.has(optionKey(option)) || !begin('apply')) return;
    let saved = false;
    try {
      const updated = isDemo ? applyDemoTradeoff(state, option) : await plannerApi.applyTradeoff(id, { option });
      saved = true; onStateChange(updated); setSelected(null); setGuidance('');
      setNotice('Adjustment applied. Your budget and planning tasks have been updated.');
      if (!isDemo) onStateChange(await plannerApi.getSession(id));
    } catch (err) {
      if (saved) { setError('Your adjustment was saved, but we couldn’t refresh the latest plan. Refresh your saved plan below.'); setNeedsRefresh(true); }
      else {
        // Reconcile a lost response before allowing a non-idempotent apply request to be retried.
        try {
          const latest = await plannerApi.getSession(id);
          onStateChange(latest);
          if (latest.applied_tradeoffs.some(item => optionKey(item) === optionKey(option))) setNotice('Adjustment applied. Your saved plan is now up to date.');
          else setError(apiError(err));
        } catch { setNeedsRefresh(true); setError('We couldn’t confirm whether the adjustment was saved. Refresh your saved plan before applying another option.'); }
      }
    } finally { finish(); }
  }

  return <section aria-labelledby="budget-title" className="space-y-7">
    <Card className="overflow-hidden border border-white bg-[#f7f3f9]">
      <h3 id="budget-summary-title" className="sr-only">Budget summary</h3>
      <div role="region" aria-labelledby="budget-summary-title" tabIndex={0} className="overflow-x-auto rounded-3xl">
        <dl className="grid min-w-[620px] grid-cols-4 gap-2 p-3 sm:min-w-0 sm:gap-3 sm:p-4">
          {[
            { label: 'Total Budget', amount: budget.total_budget, color: 'bg-lavender/60' },
            { label: 'Total Allocated', amount: totalAllocated, color: 'bg-powder/60' },
            { label: 'Total Estimated', amount: totalEstimated, color: estimatesOverBudget ? 'bg-pink/70' : 'bg-peach/50' },
            { label: 'Remaining', amount: budget.remaining, color: 'bg-mint/70' },
          ].map(({ label, amount, color }) => <div key={label} className={cn('min-w-0 rounded-2xl px-4 py-5 shadow-button', color)}>
            <dt className="text-[11px] font-medium text-muted">{label}</dt>
            <dd className="mt-3 break-words font-display text-xl font-semibold tracking-[-.5px] lg:text-2xl">{money(amount, currency)}</dd>
          </div>)}
        </dl>
      </div>
      {estimatesOverBudget && <p role="status" className="mx-4 mb-4 flex items-start gap-2 rounded-xl bg-[#fae5e6] px-4 py-3 text-xs leading-6 text-[#a04852]"><CircleAlert size={16} className="mt-1 shrink-0"/><span><strong>Over Budget</strong> · Total estimates exceed your budget by {money(totalEstimated - budget.total_budget, currency)}.</span></p>}
      <p className="px-5 pb-4 text-[10px] leading-5 text-muted">Remaining reflects projected spending, using confirmed costs where available. <span className="sm:hidden">Swipe to see all four totals.</span></p>
    </Card>
    <div className="flex flex-wrap items-end justify-between gap-5"><div><p className="eyebrow">GOOD PLANS HAVE BREATHING ROOM</p><h2 id="budget-title" className="mt-2 font-display text-[28px] font-semibold tracking-[-1px]">A thoughtful place for every rupee.</h2><p className="mt-2 text-sm leading-6 text-muted">A clear picture of your spending, with room for what matters.</p></div><Button variant="secondary" disabled={!!busy || needsRefresh} onClick={recalculate} className="text-xs"><RefreshCw size={15} className={busy === 'recalculate' ? 'animate-spin' : ''}/>{busy === 'recalculate' ? 'Refreshing your numbers…' : 'Recalculate budget'}</Button></div>
    {!budget.is_over_budget && <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-peach/30 px-4 py-3"><Button type="button" variant="secondary" onClick={simulateIncrease} disabled={!!busy || needsRefresh || !simulation} className="bg-peach/70 px-4 py-2.5 text-xs" aria-describedby="cost-increase-help">{busy === 'simulate' ? <LoaderCircle size={15} className="animate-spin"/> : <TrendingDown size={15} className="rotate-180"/>}{busy === 'simulate' ? 'Updating costs & finding options…' : 'Simulate Cost Increase'}</Button><p id="cost-increase-help" className="min-w-0 flex-1 text-[11px] leading-6 text-muted">{simulation ? `Adds ${money(simulation.increase, currency)} to ${categoryLabel(simulation.category)} in ${isDemo ? 'this sample' : 'your saved plan'}. Covers the remaining surplus, then adds ₹20,000 to reveal trade-off options.` : 'Add an unconfirmed category estimate to try a cost increase. Verified costs stay unchanged.'}</p></div>}
    {isDemo && <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-lilac/10 bg-lavender/30 px-4 py-3 text-xs text-muted"><Sparkles size={15}/><span>Explore the sample budget, including a little room to rebalance.</span><button disabled={!!busy} onClick={() => { onStateChange(overBudgetDemo()); setSelected(null); setNotice('Sample over-budget scenario loaded.'); setError(''); setGuidance(''); }} className="rounded-lg px-2 py-1 font-semibold text-lilac underline underline-offset-4">Preview over-budget example</button><button disabled={!!busy} onClick={() => { onStateChange(structuredClone(demoState)); setSelected(null); setNotice('Sample budget reset.'); setError(''); setGuidance(''); }} className="rounded-lg px-2 py-1 text-charcoal underline underline-offset-4">Reset sample</button></div>}
    {error && needsRefresh && <div role="alert" className="flex items-start gap-3 rounded-2xl bg-peach p-5 text-sm leading-6"><CircleAlert size={20} className="mt-0.5 shrink-0 text-[#986b59]"/><div><p>{error}</p>{needsRefresh && <Button onClick={refresh} disabled={!!busy} variant="secondary" className="mt-3 text-xs"><RefreshCw size={14} className={busy === 'refresh' ? 'animate-spin' : ''}/>{busy === 'refresh' ? 'Refreshing…' : 'Refresh saved plan'}</Button>}</div></div>}
    {budget.is_over_budget && <Card className="flex flex-wrap items-center justify-between gap-6 border border-[#eed5c8] bg-[#fcf0e8] p-7"><div className="flex items-start gap-4"><span className="icon-tile !h-11 !w-11 shrink-0 bg-peach"><CircleAlert size={20}/></span><div className="max-w-xl"><h3 className="font-display text-lg font-bold">A little over. Plenty of possibilities.</h3><p className="mt-2 text-sm leading-6 text-[#8c7266]">Your projected costs are {money(budget.overage, currency)} above your budget. Explore a few thoughtful adjustments and choose what works for your celebration.</p></div></div><Button disabled={!!busy || needsRefresh} onClick={generate} className="bg-white/80 text-xs">{busy === 'generate' ? <LoaderCircle size={16} className="animate-spin"/> : <Sparkles size={16}/>} {busy === 'generate' ? 'Finding a little breathing room…' : 'Generate Trade-off Options'}</Button></Card>}
    <Card className="p-5 sm:p-7"><div className="mb-6 flex flex-wrap items-end justify-between gap-4"><div><h3 className="font-display text-xl font-bold tracking-[-.5px]">The details, beautifully balanced.</h3><p className="mt-2 max-w-xl text-xs leading-6 text-muted">Progress compares each category’s projected cost with its allocation. Confirmed costs take priority over estimates.</p></div><span className="flex items-center gap-1.5 text-[11px] text-[#527760]"><BadgeCheck size={14}/> Verified = confirmed cost</span></div>{budget.items.length ? <div className="grid gap-5 md:grid-cols-2">{budget.items.map((item, index) => <CategoryCard key={`${item.category}-${index}`} item={item} currency={currency}/>)}</div> : <div className="rounded-2xl bg-cream px-5 py-10 text-center text-sm leading-7 text-muted"><Flower2 size={28} className="mx-auto mb-4 text-lilac"/><h4 className="font-display text-lg font-semibold text-charcoal">Room for every little detail.</h4><p className="mx-auto mt-3 max-w-md text-xs leading-6">No category allocations yet. As your plan takes shape, this is where estimates, confirmed costs, and spending notes will come together.</p></div>}</Card>
    {budget.is_over_budget && options.length > 0 && <section aria-labelledby="tradeoffs-title"><div className="mb-6"><p className="eyebrow">SMALL ADJUSTMENTS. MORE POSSIBILITY.</p><h3 id="tradeoffs-title" className="mt-2 font-display text-2xl font-semibold tracking-[-.7px]">Find the balance that feels like you.</h3><p className="mt-3 text-sm leading-6 text-muted">Choose one option to review and apply. Savings are estimates; verified contracts stay confirmed.</p>{guidance && <p className="mt-2 text-xs leading-6 text-muted">{guidance}</p>}</div><fieldset disabled={!!busy || needsRefresh} className="grid min-w-0 gap-5 lg:grid-cols-2"><legend className="sr-only">Choose a budget trade-off option</legend>{options.map(option => {
      const key = optionKey(option); const chosen = activeSelection === key;
      return <Card key={key} className={cn('flex flex-col border-2 p-6 transition-colors', chosen ? 'border-[#c8b5da] bg-[#f4eef8]' : 'border-transparent')}>
        <label className="flex cursor-pointer items-start gap-3 text-sm"><input className="!mt-1 !h-4 !w-4 shrink-0 accent-[#8a719d]" type="radio" name="budget-tradeoff" checked={chosen} onChange={() => setSelected(key)}/><span><span className="block font-display text-base font-bold leading-6">{option.title}</span>{option.recommended && <span className="mt-2 inline-flex items-center gap-1 rounded-full bg-mint px-2.5 py-1 text-[10px] text-[#527760]"><Sparkles size={11}/> Thoughtful pick</span>}</span></label>
        <p className="mt-4 text-sm leading-6 text-muted">{option.description}</p><div className="my-5 rounded-2xl bg-white/80 px-4 py-4 shadow-button"><p className="text-[10px] text-muted">Potential savings · INR</p><p className="mt-1 font-display text-2xl font-bold text-[#527760]">{money(option.total_savings_inr, 'INR')}</p></div>
        <ul className="space-y-4">{option.tradeoffs.map((change, index) => <li key={index} className="rounded-xl bg-white/50 p-4"><div className="flex flex-wrap items-center justify-between gap-2 text-[10px]"><span className="font-semibold text-lilac">{categoryLabel(change.category)}</span><span className="text-[#527760]">Save {money(change.savings_inr, 'INR')}</span></div><p className="mt-2 text-sm font-medium leading-6">{change.action}</p><p className="mt-2 text-xs leading-6 text-muted">{change.impact_description}</p></li>)}</ul>
        {option.impact_on_other_categories && <p className="mb-5 mt-4 text-xs leading-6 text-muted"><span className="font-medium text-charcoal">Also worth considering: </span>{option.impact_on_other_categories}</p>}
        <Button disabled={!chosen || !!busy || needsRefresh} onClick={() => apply(option)} className="mt-auto w-full justify-center bg-white/80 text-xs">{busy === 'apply' && chosen ? <><LoaderCircle size={16} className="animate-spin"/> Applying your adjustment…</> : <>Apply this option <Check size={16}/></>}</Button>
      </Card>;
    })}</fieldset></section>}
    {budget.is_over_budget && state.tradeoff_options.length > 0 && options.length === 0 && <p className="rounded-2xl bg-lavender/40 p-5 text-sm leading-6 text-muted">Your previous adjustments are recorded below. Generate fresh options to explore the remaining overage.</p>}
    {state.applied_tradeoffs.length > 0 && <Card className="p-7"><h3 className="font-display text-lg font-bold">Thoughtful changes, kept in view.</h3><p className="mt-2 text-xs leading-6 text-muted">Applied adjustments are recorded here. Your current totals above reflect the saved budget.</p><ul className="mt-5 space-y-3">{state.applied_tradeoffs.map((option, index) => <li key={`${optionKey(option)}-${index}`} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-mint/40 px-4 py-4"><span className="flex items-center gap-2 text-sm"><Check size={15} className="shrink-0 text-[#527760]"/>{option.title}</span><span className="text-xs text-[#527760]">Target savings {money(option.total_savings_inr, 'INR')}</span></li>)}</ul></Card>}
  </section>;
}
