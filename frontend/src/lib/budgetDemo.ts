import { demoState } from './demo';
import { recalculatePreviewBudget } from './budget';
import type { EventState, TradeoffOption } from '../types';

/** Illustrative local actions for the explicitly labeled sample session only. */
export function overBudgetDemo(): EventState {
  const state = structuredClone(demoState);
  state.budget.items[1].estimated += 250000;
  state.budget.items[1].notes = 'Sample quote: a larger menu puts this category above its allocation.';
  state.budget.items[0].verified = 425000;
  state.budget = recalculatePreviewBudget(state.budget);
  return state;
}
export function demoTradeoffs(state: EventState): TradeoffOption[] {
  const savings = state.budget.overage;
  return [
    { title: 'A thoughtful menu, just as memorable', description: 'Keep the guest list and simplify the menu with seasonal ingredients.', total_savings_inr: savings, recommended: true, impact_on_other_categories: 'Venue, photography, and guest count stay the same.', tradeoffs: [{ category: 'catering', action: 'Choose a seasonal menu with fewer live stations', savings_inr: savings, impact_description: 'A smaller selection of dishes with the same number of servings. Confirm a revised quote with your caterer.' }] },
    { title: 'Small touches, lovely savings', description: 'Share the adjustment between food and flowers.', total_savings_inr: savings, recommended: false, impact_on_other_categories: 'Allow time to agree new menu and floral selections with both vendors.', tradeoffs: [{ category: 'catering', action: 'Simplify the welcome drinks and dessert selection', savings_inr: savings * .6, impact_description: 'Fewer choices, with the full meal retained.' }, { category: 'decor', action: 'Use local seasonal flowers and reuse ceremony arrangements', savings_inr: savings * .4, impact_description: 'A simpler floral palette with a little extra setup coordination.' }] },
  ];
}
export function applyDemoTradeoff(state: EventState, option: TradeoffOption): EventState {
  const next = structuredClone(state);
  option.tradeoffs.forEach((change, index) => {
    const item = next.budget.items.find(item => item.category.toLowerCase() === change.category.toLowerCase());
    if (item) { item.estimated = Math.max(0, item.estimated - change.savings_inr); item.notes = `${item.notes} Trade-off: ${change.action}.`; }
    next.tasks.tasks.push({ id: `demo-tradeoff-${next.applied_tradeoffs.length}-${index}`, title: change.action, description: change.impact_description, milestone: '1_month', due_date: next.config.event_date, depends_on: [], status: 'pending', estimated_cost: 0 });
  });
  next.budget = recalculatePreviewBudget(next.budget);
  next.applied_tradeoffs.push(option);
  next.updated_at = new Date().toISOString();
  next.tasks.last_updated = next.updated_at;
  return next;
}
