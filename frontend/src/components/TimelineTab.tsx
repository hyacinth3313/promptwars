import { useFeedback } from './Feedback';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { CalendarDays, Check, CheckCheck, CircleAlert, Clock3, Flag, GitBranch, ListChecks, LoaderCircle, Play, RefreshCw, RotateCcw, Sparkles } from 'lucide-react';
import { Button, Card } from './ui';
import { apiError, plannerApi } from '../lib/api';
import { formatTaskDate, groupTimelineTasks, shiftDemoTimeline, taskStatuses, timelineShiftRequest, timelineStats, updateDemoTask, validEventDate } from '../lib/timeline';
import { cn } from '../lib/utils';
import type { EventState, TaskItem, TaskStatus, TimelineShiftResponse } from '../types';

interface Props { state: EventState; onStateChange: (state: EventState) => void }
interface TaskCardProps { task: TaskItem; tasksById: Map<string, TaskItem>; disabled: boolean; updating: boolean; onStatusChange: (task: TaskItem, status: TaskStatus) => void }

function TaskCard({ task, tasksById, disabled, updating, onStatusChange }: TaskCardProps) {
  const [expanded, setExpanded] = useState(false);
  const status = taskStatuses[task.status];
  return <Card className={cn('flex min-w-0 flex-col p-6', task.status === 'completed' && 'bg-[#fafdf9]', task.status === 'late' && 'border border-[#efd6c8]')}>
    <div className="flex items-start justify-between gap-4"><h4 className="min-w-0 break-words font-display text-base font-bold leading-7">{task.title}</h4><span className={cn('inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1.5 text-[10px] font-medium', status.color)}>{task.status === 'completed' && <Check size={11}/>} {status.label}</span></div>
    <p className={cn('mt-3 whitespace-pre-line text-xs leading-6 text-muted', !expanded && 'line-clamp-2')}>{task.description}</p>{task.description.length > 140 && <button type="button" onClick={() => setExpanded(value => !value)} aria-expanded={expanded} className="mt-1 self-start rounded-lg px-1 py-1 text-[11px] text-lilac underline underline-offset-4">{expanded ? 'A little less detail' : 'Read the details'}</button>}
    <div className="mt-5 flex items-center gap-2 text-xs text-charcoal/80"><CalendarDays size={14} className="text-lilac"/><span>Due <time dateTime={task.due_date}>{formatTaskDate(task.due_date)}</time></span></div>
    <div className="mb-6 mt-4"><p className="mb-2 flex items-center gap-1.5 text-[10px] font-medium text-muted"><GitBranch size={12}/> {task.depends_on.length ? 'Depends on' : 'No prerequisites'}</p>{task.depends_on.length > 0 && <ul className="flex flex-wrap gap-2">{task.depends_on.map(id => {
      const dependency = tasksById.get(id);
      return <li key={id} className={cn('inline-flex max-w-full items-center gap-1.5 rounded-xl px-2.5 py-1.5 text-[10px] leading-5', dependency?.status === 'completed' ? 'bg-mint/70 text-[#527760]' : 'bg-cream text-muted')}>
        {dependency?.status === 'completed' ? <Check size={11} className="shrink-0"/> : <Clock3 size={11} className="shrink-0"/>}<span className="break-words">{dependency?.title || `Unavailable task (${id})`}{dependency ? ` · ${taskStatuses[dependency.status].label}` : ''}</span>
      </li>;
    })}</ul>}</div>
    <div role="group" className="mt-auto flex flex-wrap gap-2 border-t border-charcoal/5 pt-4" aria-label={`Change status for ${task.title}`}>
      {task.status === 'completed' ? <Button type="button" variant="secondary" disabled={disabled} onClick={() => onStatusChange(task, 'pending')} className="px-3 py-2.5 text-[11px]"><RotateCcw size={13}/> Reopen task</Button> : <>
        <Button type="button" disabled={disabled} onClick={() => onStatusChange(task, 'completed')} className="bg-mint px-3 py-2.5 text-[11px]"><Check size={13}/> Mark Complete</Button>
        {task.status !== 'in_progress' && <Button type="button" disabled={disabled} onClick={() => onStatusChange(task, 'in_progress')} className="px-3 py-2.5 text-[11px]"><Play size={12}/> Start task</Button>}
        {task.status !== 'late' && <Button type="button" disabled={disabled} onClick={() => onStatusChange(task, 'late')} className="bg-peach px-3 py-2.5 text-[11px]"><Flag size={12}/> Mark Late</Button>}
        {task.status !== 'pending' && <button type="button" disabled={disabled} onClick={() => onStatusChange(task, 'pending')} className="rounded-xl px-3 py-2 text-[11px] text-muted hover:bg-cream disabled:opacity-60">Set Pending</button>}
      </>}
    </div>{updating && <p role="status" className="mt-3 flex items-center gap-2 text-xs text-lilac"><LoaderCircle size={13} className="animate-spin"/> Saving this little step…</p>}
  </Card>;
}

export default function TimelineTab({ state, onStateChange }: Props) {
  const id = state.config.session_id;
  const isDemo = id === 'demo';
  const [date, setDate] = useState(state.config.event_date);
  const [dateError, setDateError] = useState('');
  const [busy, setBusy] = useState<'status' | 'shift' | 'refresh' | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const busyRef = useRef(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  useFeedback(error, notice);
  const [needsRefresh, setNeedsRefresh] = useState(false);
  const [report, setReport] = useState<TimelineShiftResponse | null>(null);
  const dateInput = useRef<HTMLInputElement>(null);
  const stats = timelineStats(state.tasks.tasks);
  const groups = groupTimelineTasks(state.tasks.tasks);
  const tasksById = new Map(state.tasks.tasks.map(task => [task.id, task]));
  useEffect(() => { setDate(state.config.event_date); setDateError(''); }, [state.config.event_date]);

  function begin(action: NonNullable<typeof busy>) {
    if (busyRef.current) return false;
    busyRef.current = true; setBusy(action); setError(''); setNotice(''); return true;
  }
  function finish() { busyRef.current = false; setBusy(null); setPendingId(null); }
  async function refresh() {
    if (!begin('refresh')) return;
    try { onStateChange(await plannerApi.getSession(id)); setNeedsRefresh(false); setReport(null); setNotice('Your saved timeline is up to date.'); }
    catch (err) { setError(apiError(err)); } finally { finish(); }
  }
  async function changeStatus(task: TaskItem, status: TaskStatus) {
    if (needsRefresh || task.status === status || !begin('status')) return;
    setPendingId(task.id);
    let saved = false;
    try {
      const result = isDemo ? updateDemoTask(state, task.id, status) : await plannerApi.updateTask(id, task.id, status);
      saved = true;
      onStateChange({ ...state, tasks: result.tasks, updated_at: result.tasks.last_updated });
      setReport(null);
      const affected = result.downstream_affected_task_ids.length;
      setNotice(status === 'late' ? `Task marked Late. ${affected ? `${affected} dependent ${affected === 1 ? 'task was' : 'tasks were'} rescheduled.` : 'No downstream tasks needed to move.'} You can review the full timeline below.` : `“${task.title}” is now ${taskStatuses[status].label.toLowerCase()}.`);
      if (!isDemo) onStateChange(await plannerApi.getSession(id));
    } catch (err) {
      if (saved) { setNeedsRefresh(true); setError('Your task update was saved, but we couldn’t refresh the full plan. Refresh the saved timeline before making another change.'); }
      else {
        // A late status update cascades delays. Reconcile a lost response before retrying.
        try {
          const latest = await plannerApi.getSession(id); onStateChange(latest);
          if (latest.tasks.tasks.find(item => item.id === task.id)?.status === status) { setReport(null); setNotice(`Saved status confirmed: ${taskStatuses[status].label}. Your timeline is up to date.`); }
          else setError(apiError(err));
        } catch { setNeedsRefresh(true); setError('We couldn’t confirm whether this change was saved. Refresh the saved timeline before trying again.'); }
      }
    } finally { finish(); }
  }
  async function shift(requestedDate?: string) {
    if (needsRefresh) return;
    if (requestedDate !== undefined && !validEventDate(requestedDate)) { setDateError('Choose a valid event date so we can realign your plan.'); dateInput.current?.focus(); return; }
    if (!begin('shift')) return;
    const request = timelineShiftRequest(state.config.event_date, requestedDate);
    let saved = false;
    try {
      const result = isDemo ? shiftDemoTimeline(state, request) : await plannerApi.shiftTimeline(id, request);
      saved = true;
      onStateChange({ ...state, config: { ...state.config, event_date: request.new_date || state.config.event_date }, tasks: result.updated_tasks, updated_at: result.updated_tasks.last_updated });
      setReport(result);
      setNotice('Your timeline has been realigned. Completed tasks keep their dates; the latest tasks are shown below.');
      if (!isDemo) onStateChange(await plannerApi.getSession(id));
    } catch (err) {
      setNeedsRefresh(true);
      setError(saved ? 'Your timeline was saved, but we couldn’t refresh the full plan. Refresh the saved timeline below.' : `${apiError(err)} Refresh the saved timeline to confirm the latest dates before trying again.`);
    } finally { finish(); }
  }
  function submitDate(event: FormEvent<HTMLFormElement>) { event.preventDefault(); void shift(date); }

  return <section aria-labelledby="timeline-title" className="space-y-7">
    <div className="flex flex-wrap items-end justify-between gap-5"><div><p className="eyebrow">ONE LITTLE STEP. A LOVELY BIG DAY.</p><h2 id="timeline-title" className="mt-2 font-display text-[28px] font-semibold tracking-[-1px]">Your plans, finding their rhythm.</h2><p className="mt-2 text-sm leading-6 text-muted">A calm place for every task, every milestone, and every little change.</p></div><span className="flex items-center gap-2 rounded-full bg-lavender/70 px-4 py-2 text-xs text-lilac"><Clock3 size={14}/>{stats.in_progress} in progress</span></div>
    {isDemo && <p className="flex items-start gap-2 rounded-2xl bg-lavender/30 px-5 py-4 text-xs leading-6 text-muted"><Sparkles size={15} className="mt-1 shrink-0"/>This sample board supports status changes and date shifts locally. Try marking a task Late to see its dependent tasks move. Sample actions never change a real event.</p>}
    {error && needsRefresh && <div role="alert" className="flex items-start gap-3 rounded-2xl bg-peach p-5 text-sm leading-6"><CircleAlert size={19} className="mt-1 shrink-0 text-[#986552]"/><div><p>{error}</p>{needsRefresh && <Button disabled={!!busy} onClick={refresh} variant="secondary" className="mt-3 text-xs"><RefreshCw size={14} className={busy === 'refresh' ? 'animate-spin' : ''}/>Refresh saved timeline</Button>}</div></div>}
    {busy && <p role="status" className="flex items-center gap-2 text-xs text-lilac"><LoaderCircle size={14} className="animate-spin"/>{busy === 'shift' ? 'Giving your timeline a little breathing room…' : busy === 'refresh' ? 'Gathering your latest saved dates…' : 'Saving your task and checking its dependencies…'}</p>}
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">{[{ label: 'Total tasks', count: stats.total, color: 'bg-powder', icon: ListChecks }, { label: 'Completed', count: stats.completed, color: 'bg-mint', icon: CheckCheck }, { label: 'Pending', count: stats.pending, color: 'bg-[#f2ebe1]', icon: Clock3 }, { label: 'Late', count: stats.late, color: 'bg-peach', icon: Flag }].map(({ label, count, color, icon: Icon }) => <Card key={label} className={cn('p-5 sm:p-6', color)}><div className="flex items-center justify-between gap-3"><p className="text-xs text-charcoal/80">{label}</p><Icon size={17} strokeWidth={1.6}/></div><p className="mt-4 font-display text-3xl font-semibold">{count}</p></Card>)}</div>
    <Card className="p-6"><div className="mb-4 flex flex-wrap items-center justify-between gap-3"><p className="text-sm font-medium">A little closer with every step.</p><span className="text-xs text-[#527760]">{stats.completion_percentage}% complete · {stats.completed} of {stats.total} tasks</span></div><div className="timeline-progress" role="progressbar" aria-label="Planning tasks completed" aria-valuemin={0} aria-valuemax={100} aria-valuenow={stats.completion_percentage} aria-valuetext={`${stats.completed} of ${stats.total} tasks completed`}><span style={{ width: `${stats.completion_percentage}%` }}/></div></Card>
    <Card className="p-6 sm:p-7"><div className="flex items-start gap-4"><span className="icon-tile !h-11 !w-11 shrink-0 bg-lavender"><CalendarDays size={21}/></span><div><h3 className="font-display text-lg font-bold">A new date. A plan that moves with you.</h3><p className="mt-2 text-xs leading-6 text-muted">Move the event date and we’ll realign the unfinished tasks. Completed tasks keep their original dates.</p><p className="mt-2 text-[11px] text-lilac">Currently planned for {formatTaskDate(state.config.event_date)}</p></div></div>
      <form onSubmit={submitDate} noValidate className="mt-6 flex flex-col items-stretch gap-4 sm:flex-row sm:items-end"><label className="min-w-0 flex-1" htmlFor="timeline-event-date">New event date<input ref={dateInput} id="timeline-event-date" type="date" required value={date} onChange={event => { setDate(event.target.value); setDateError(''); }} disabled={!!busy || needsRefresh} aria-invalid={!!dateError} aria-describedby={dateError ? 'timeline-date-error' : undefined}/></label><Button type="submit" disabled={!!busy || needsRefresh || date === state.config.event_date} className="justify-center py-3.5 text-xs"><RefreshCw size={15} className={busy === 'shift' ? 'animate-spin' : ''}/>Update date & realign</Button></form>{dateError && <p id="timeline-date-error" role="alert" className="mt-3 text-xs text-[#986552]">{dateError}</p>}
    </Card>
    {stats.late > 0 && <Card className="flex flex-wrap items-center justify-between gap-5 border border-[#efd6c8] bg-[#fcf0e8] p-6"><div className="flex items-start gap-3"><Flag size={20} className="mt-1 shrink-0 text-[#986552]"/><div className="max-w-xl"><h3 className="font-display text-base font-bold">A little breathing room for the next steps.</h3><p className="mt-2 text-xs leading-6 text-[#8c7266]">{stats.late} {stats.late === 1 ? 'task is' : 'tasks are'} marked Late. Downstream dates update when you mark a task late. Recalculate to review the full schedule and any remaining risks.</p></div></div><Button disabled={!!busy || needsRefresh} onClick={() => shift()} className="bg-white/80 text-xs"><Sparkles size={15}/>Recalculate timeline</Button></Card>}
    {report && <Card className="border border-lilac/10 bg-[#f1ebf5] p-6"><h3 className="flex items-center gap-2 font-display text-base font-bold"><Sparkles size={17} className="text-lilac"/>A fresh look at your timeline</h3><p className="mt-3 whitespace-pre-line text-sm leading-7 text-muted">{report.reasoning}</p>{report.critical_risks.length > 0 ? <div className="mt-5"><h4 className="text-xs font-semibold">A few things to keep an eye on</h4><ul className="mt-3 space-y-2">{report.critical_risks.map((risk, index) => <li key={index} className="flex items-start gap-2 rounded-xl bg-white/65 px-4 py-3 text-xs leading-6"><CircleAlert size={14} className="mt-1 shrink-0 text-[#986552]"/>{risk}</li>)}</ul></div> : <p className="mt-4 flex items-center gap-2 text-xs text-[#527760]"><Check size={14}/>No critical risks were reported in this review.</p>}</Card>}
    <div className="timeline-board space-y-9">{groups.map((group, index) => {
      const complete = group.tasks.filter(task => task.status === 'completed').length;
      return <section key={group.key} aria-labelledby={`milestone-${group.key}`}><div className={cn('mb-5 flex flex-wrap items-center justify-between gap-4 rounded-2xl px-5 py-5 shadow-button', group.color)}><div className="flex items-center gap-4"><span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-white/60 text-xs font-semibold text-charcoal/70">0{index + 1}</span><div><h3 id={`milestone-${group.key}`} className="font-display text-lg font-bold">{group.label}</h3><p className="mt-1 text-[11px] text-charcoal/70">{group.subtitle}</p></div></div><span className="rounded-full bg-white/60 px-3 py-1.5 text-[10px]">{complete} of {group.tasks.length} complete</span></div>{group.tasks.length ? <div className="grid items-stretch gap-5 lg:grid-cols-2">{group.tasks.map(task => <TaskCard key={task.id} task={task} tasksById={tasksById} disabled={!!busy || needsRefresh} updating={pendingId === task.id} onStatusChange={changeStatus}/>)}</div> : <div className="rounded-3xl border border-dashed border-charcoal/10 bg-white/30 px-6 py-9 text-center text-xs leading-6 text-muted"><CalendarDays size={24} className="mx-auto mb-3 text-lilac"/><p className="font-medium text-charcoal">A little breathing room.</p><p className="mt-2">No tasks in this milestone yet. When there are steps to plan, they’ll have a home here.</p></div>}</section>;
    })}</div>
  </section>;
}
