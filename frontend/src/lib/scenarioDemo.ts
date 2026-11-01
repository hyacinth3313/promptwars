import { recalculatePreviewBudget } from './budget';
import { shiftDemoTimeline } from './timeline';
import type { EventState, ScenarioDelta, ScenarioPreviewResponse } from '../types';

export function previewDemoScenario(state: EventState, delta: ScenarioDelta): ScenarioPreviewResponse {
  const current = structuredClone(state);
  const config = { ...current.config, total_budget: Math.round((current.config.total_budget + delta.budget_change) * 100) / 100, guest_count: current.config.guest_count + delta.guest_count_delta, event_date: delta.new_date || current.config.event_date };
  const ratio = config.guest_count / current.config.guest_count;
  const budget = structuredClone(current.budget);
  budget.total_budget = config.total_budget;
  budget.items.forEach(item => {
    item.allocated = Math.round(item.allocated / current.budget.total_budget * config.total_budget * 100) / 100;
    if (['catering', 'logistics'].includes(item.category.toLowerCase()) && item.verified === null) item.estimated = Math.round(item.estimated * ratio * 100) / 100;
  });
  const timeline = delta.new_date ? shiftDemoTimeline(current, { new_date: delta.new_date, late_task_ids: [] }) : null;
  return {
    scenario_id: `scenario_${crypto.randomUUID().replaceAll('-', '')}`, base_updated_at: current.updated_at, expires_at: new Date(Date.now() + 86400000).toISOString(),
    committed_state: current, updated_config: config, updated_budget: recalculatePreviewBudget(budget), updated_tasks: timeline?.updated_tasks || structuredClone(current.tasks),
    scenario_summary: 'A sample look at a different kind of celebration. Your committed plan stays in place until you choose to commit.',
    financial_impact: 'This local example scales unverified catering and logistics estimates with the guest count. Other estimates stay fixed, and allocations follow the new budget. It is illustrative rather than an AI prediction.',
    affected_tasks: delta.guest_count_delta || delta.new_date ? current.tasks.tasks.filter(task => task.status !== 'completed').map(task => task.id) : [],
    recommendations: ['Confirm revised quotes and guest capacity with your vendors.', ...(delta.new_date ? ['Share the new event date and reconfirm availability.'] : [])], critical_risks: timeline?.critical_risks || [],
  };
}
export function commitDemoScenario(preview: ScenarioPreviewResponse): EventState {
  return { ...structuredClone(preview.committed_state), config: structuredClone(preview.updated_config), budget: structuredClone(preview.updated_budget), tasks: structuredClone(preview.updated_tasks), tradeoff_options: [], last_committed_scenario_id: preview.scenario_id, updated_at: new Date().toISOString() };
}
