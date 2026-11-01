import type { BudgetBreakdown, BudgetItem, EventState, ScenarioDelta, ScenarioPreviewResponse } from '../types';

export interface ScenarioInputs { budget: string; guests: string; date: string }
export type ScenarioInputErrors = Partial<Record<keyof ScenarioInputs | 'form', string>>;
export function validateScenarioInputs(state: EventState, fields: ScenarioInputs): { delta: ScenarioDelta; errors: ScenarioInputErrors } {
  const budgetText = fields.budget.trim();
  const guestText = fields.guests.trim();
  const budget = budgetText ? Number(budgetText) : 0;
  const guests = guestText ? Number(guestText) : 0;
  const errors: ScenarioInputErrors = {};
  if ((budgetText && !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(budgetText)) || !Number.isFinite(budget) || Math.abs(budget) > Number.MAX_SAFE_INTEGER || Math.round((state.config.total_budget + budget) * 100) / 100 <= 0) errors.budget = 'Use a signed amount that leaves a total budget greater than ₹0.';
  if ((guestText && !/^[+-]?\d+$/.test(guestText)) || !Number.isSafeInteger(guests) || !Number.isSafeInteger(state.config.guest_count + guests) || state.config.guest_count + guests < 1) errors.guests = 'Use a whole number that leaves at least one guest.';
  if (fields.date && (!/^\d{4}-\d{2}-\d{2}$/.test(fields.date) || !Number.isFinite(Date.parse(`${fields.date}T12:00:00Z`)) || new Date(`${fields.date}T12:00:00Z`).toISOString().slice(0, 10) !== fields.date)) errors.date = 'Choose a valid date for this scenario.';
  const delta: ScenarioDelta = { budget_change: Math.round(budget * 100) / 100, guest_count_delta: guests, ...(fields.date && fields.date !== state.config.event_date ? { new_date: fields.date } : {}) };
  if (!Object.keys(errors).length && !delta.budget_change && !delta.guest_count_delta && !delta.new_date) errors.form = 'Try a budget, guest count, or date change to explore a new possibility.';
  return { delta, errors };
}
const categoryKey = (category: string) => category.normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim().toLowerCase();
export function scenarioBudgetRows(current: BudgetBreakdown, scenario: BudgetBreakdown) {
  const before = new Map(current.items.map(item => [categoryKey(item.category), item]));
  const after = new Map(scenario.items.map(item => [categoryKey(item.category), item]));
  return [...new Set([...before.keys(), ...after.keys()])].map(key => {
    const original = before.get(key); const proposed = after.get(key);
    const effective = (item?: BudgetItem) => item ? item.verified ?? item.estimated : 0;
    return { key, category: proposed?.category || original!.category, current: original, scenario: proposed, costChange: Math.round((effective(proposed) - effective(original)) * 100) / 100, changed: JSON.stringify(original) !== JSON.stringify(proposed) };
  });
}
export function scenarioAffectedTasks(preview: ScenarioPreviewResponse) {
  const current = preview.committed_state.tasks.tasks;
  const changed = preview.updated_tasks.tasks.filter(task => {
    const original = current.find(item => item.id === task.id);
    return !original || original.due_date !== task.due_date || original.status !== task.status;
  }).map(task => task.id);
  const seen = new Set<string>();
  return [...preview.affected_tasks, ...changed].map(reference => {
    const original = current.find(task => task.id === reference || task.title.toLowerCase() === reference.toLowerCase());
    const proposed = preview.updated_tasks.tasks.find(task => task.id === (original?.id || reference) || task.title.toLowerCase() === reference.toLowerCase());
    return { key: original?.id || proposed?.id || reference, title: proposed?.title || original?.title || reference, current: original, scenario: proposed };
  }).filter(task => { if (seen.has(task.key)) return false; seen.add(task.key); return true; });
}
