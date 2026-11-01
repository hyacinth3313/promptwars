import type { BudgetBreakdown, BudgetItem, TradeoffOption } from '../types';

export const effectiveCost = (item: BudgetItem) => item.verified ?? item.estimated;
export function categoryProgress(item: BudgetItem) {
  const cost = effectiveCost(item);
  const percentage = item.allocated > 0 ? cost / item.allocated * 100 : cost > 0 ? 100 : 0;
  return { percentage, width: Math.max(0, Math.min(100, percentage)), excess: Math.max(0, cost - item.allocated) };
}
export function recalculatePreviewBudget(budget: BudgetBreakdown): BudgetBreakdown {
  const projected = budget.items.reduce((sum, item) => sum + effectiveCost(item), 0);
  const difference = Math.round((budget.total_budget - projected) * 100) / 100;
  return { ...budget, remaining: Math.max(0, difference), overage: Math.max(0, -difference), is_over_budget: difference < 0 };
}
export function optionKey(option: TradeoffOption) {
  return JSON.stringify([option.title, option.total_savings_inr, option.tradeoffs.map(item => [item.category, item.action, item.savings_inr])]);
}
export function categoryLabel(category: string) {
  const normalized = category.trim().toLowerCase();
  return normalized === 'decor' ? 'Décor' : normalized.charAt(0).toUpperCase() + normalized.slice(1);
}
