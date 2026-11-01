import { useCallback, useEffect, useRef, useState } from 'react';
import { apiError, plannerApi } from '../lib/api';
import { demoState } from '../lib/demo';
import type { EventState, TaskItem } from '../types';
export function useEvent(sessionId: string) {
  const [state, setState] = useState<EventState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [pendingTask, setPendingTask] = useState<string | null>(null);
  const taskRequest = useRef(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError(''); setState(null);
    if (sessionId === 'demo') { setState(structuredClone(demoState)); setLoading(false); return; }
    plannerApi.getSession(sessionId, controller.signal).then(setState).catch(err => { if (!controller.signal.aborted) setError(apiError(err)); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [sessionId, retry]);
  const toggleTask = useCallback(async (task: TaskItem) => {
    if (taskRequest.current) return;
    taskRequest.current = true;
    const status = task.status === 'completed' ? 'pending' : 'completed';
    setPendingTask(task.id); setError('');
    try {
      if (sessionId === 'demo') setState(previous => previous && ({ ...previous, tasks: { ...previous.tasks, tasks: previous.tasks.tasks.map(item => item.id === task.id ? { ...item, status } : item) } }));
      else { const result = await plannerApi.updateTask(sessionId, task.id, status); setState(previous => previous?.config.session_id === sessionId ? ({ ...previous, tasks: result.tasks }) : previous); }
    } catch (err) { setError(apiError(err)); } finally { taskRequest.current = false; setPendingTask(null); }
  }, [sessionId]);
  const replaceState = useCallback((next: EventState) => {
    // Keep all planner tabs in sync after planning actions, including changed dates and tasks.
    if (next.config.session_id === sessionId) setState(current => current?.config.session_id === next.config.session_id ? next : current);
  }, [sessionId]);
  return { state, loading, error, toggleTask, pendingTask, replaceState, reload: () => setRetry(value => value + 1) };
}
