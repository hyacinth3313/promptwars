import type { EventState, TaskItem, TaskProgressStats, TaskStatus, TaskStatusUpdateResponse, TimelineShiftRequest, TimelineShiftResponse } from '../types';

export const milestones = [
  { key: '3_months', label: '3 Months Out', subtitle: 'Lay the lovely foundations.', color: 'bg-lavender' },
  { key: '1_month', label: '1 Month Out', subtitle: 'Bring the big pieces together.', color: 'bg-powder' },
  { key: '1_week', label: '1 Week Out', subtitle: 'Make space for the finishing touches.', color: 'bg-peach' },
  { key: 'day_of', label: 'Day Of', subtitle: 'Be here for the moments you planned for.', color: 'bg-mint' },
] as const;
export const taskStatuses: Record<TaskStatus, { label: string; color: string }> = {
  pending: { label: 'Pending', color: 'bg-[#efeae3] text-[#796f63]' },
  in_progress: { label: 'In Progress', color: 'bg-lavender text-[#795f8a]' },
  completed: { label: 'Completed', color: 'bg-mint text-[#527760]' },
  late: { label: 'Late', color: 'bg-peach text-[#986552]' },
};
export function groupTimelineTasks(tasks: TaskItem[]) {
  return milestones.map(milestone => ({ ...milestone, tasks: tasks.filter(task => task.milestone === milestone.key).sort((a, b) => a.due_date.localeCompare(b.due_date) || a.title.localeCompare(b.title)) }));
}
export function timelineStats(tasks: TaskItem[]): TaskProgressStats {
  const completed = tasks.filter(task => task.status === 'completed').length;
  return { total: tasks.length, completed, in_progress: tasks.filter(task => task.status === 'in_progress').length, pending: tasks.filter(task => task.status === 'pending').length, late: tasks.filter(task => task.status === 'late').length, completion_percentage: tasks.length ? Math.round(completed / tasks.length * 1000) / 10 : 0 };
}
export function formatTaskDate(date: string) {
  return new Date(`${date}T12:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}
export function validEventDate(date: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(date) && Number.isFinite(Date.parse(`${date}T12:00:00Z`)) && new Date(`${date}T12:00:00Z`).toISOString().slice(0, 10) === date;
}
export function timelineShiftRequest(currentDate: string, requestedDate?: string): TimelineShiftRequest {
  // The status endpoint already cascades delays. Sending these IDs again would
  // push dependent tasks a second time; ask the shift endpoint to review the saved state.
  return { ...(requestedDate && requestedDate !== currentDate ? { new_date: requestedDate } : {}), late_task_ids: [] };
}

// Deterministic local interactions for the labeled demo; live planning uses the backend.
const dayMs = 86400000;
function addDays(date: string, days: number) { return new Date(Date.parse(`${date}T12:00:00Z`) + days * dayMs).toISOString().slice(0, 10); }
function milestoneAt(due: string, event: string): TaskItem['milestone'] {
  const days = (Date.parse(event) - Date.parse(due)) / dayMs;
  return days > 60 ? '3_months' : days > 14 ? '1_month' : days > 1 ? '1_week' : 'day_of';
}
function enforceDemoDependencies(tasks: TaskItem[], eventDate: string) {
  const byId = new Map(tasks.map(task => [task.id, task]));
  for (let pass = 0; pass < tasks.length; pass++) {
    let changed = false;
    for (const task of tasks) {
      if (task.status === 'completed') continue;
      for (const parentId of task.depends_on) {
        const parent = byId.get(parentId);
        if (!parent) continue;
        const required = [addDays(parent.due_date, 1), eventDate].sort()[0];
        if (task.due_date < required) { task.due_date = required; task.milestone = milestoneAt(required, eventDate); changed = true; }
      }
    }
    if (!changed) break;
  }
}
export function updateDemoTask(state: EventState, taskId: string, status: TaskStatus): TaskStatusUpdateResponse {
  const tasks = structuredClone(state.tasks);
  const task = tasks.tasks.find(item => item.id === taskId);
  if (!task) throw new Error('Task not found');
  const wasLate = task.status === 'late';
  task.status = status;
  const affected: string[] = [];
  if (status === 'late' && !wasLate) {
    const visited = new Set([taskId]);
    const queue = [taskId];
    while (queue.length) {
      const parent = queue.shift()!;
      for (const child of tasks.tasks) {
        if (!child.depends_on.includes(parent) || visited.has(child.id)) continue;
        visited.add(child.id); queue.push(child.id);
        if (child.status !== 'completed') {
          const due = [addDays(child.due_date, 5), state.config.event_date].sort()[0];
          if (due !== child.due_date) { child.due_date = due; affected.push(child.id); }
        }
      }
    }
    enforceDemoDependencies(tasks.tasks, state.config.event_date);
  }
  tasks.last_updated = new Date().toISOString();
  return { task, tasks, downstream_affected_task_ids: affected, timeline_shifted: affected.length > 0, message: 'Sample task updated.' };
}
export function shiftDemoTimeline(state: EventState, request: TimelineShiftRequest): TimelineShiftResponse {
  const target = request.new_date || state.config.event_date;
  const delta = (Date.parse(target) - Date.parse(state.config.event_date)) / dayMs;
  const tasks = structuredClone(state.tasks);
  for (const task of tasks.tasks) {
    if (task.status !== 'completed' && delta) task.due_date = [addDays(task.due_date, delta), target].sort()[0];
  }
  enforceDemoDependencies(tasks.tasks, target);
  tasks.last_updated = new Date().toISOString();
  const risks: string[] = [];
  if (delta) risks.push('Your event date has changed. Reconfirm vendor availability and share the updated schedule.');
  if (tasks.tasks.some(task => task.status === 'late')) risks.push('Some tasks are still marked late. Check their prerequisites and agree new deadlines with your team.');
  if (tasks.tasks.some(task => task.status !== 'completed' && task.milestone !== 'day_of' && (Date.parse(target) - Date.parse(task.due_date)) / dayMs <= 3)) risks.push('Some preparation tasks are close to event day. Give these a little extra attention.');
  return { updated_tasks: tasks, reasoning: 'Sample timeline realigned with dependencies in mind. Completed tasks keep their original dates.', critical_risks: risks };
}
