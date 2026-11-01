export const priorityCategories = [
  { key: 'catering', label: 'Catering', color: '#c9dfd0', hint: 'Good food, happy people' },
  { key: 'venue', label: 'Venue', color: '#d9c9e9', hint: 'A place that feels just right' },
  { key: 'decor', label: 'Décor', color: '#efcdbd', hint: 'The little details and atmosphere' },
  { key: 'photography', label: 'Photography', color: '#c5dce9', hint: 'Memories worth keeping' },
  { key: 'logistics', label: 'Logistics', color: '#eac9d7', hint: 'Everything running smoothly' },
] as const;
export type PriorityKey = typeof priorityCategories[number]['key'];
export type PriorityWeights = Record<PriorityKey, number>;
export const defaultPriorities: PriorityWeights = { catering: 40, venue: 30, decor: 15, photography: 10, logistics: 5 };

/** Keep the chosen percentage; apportion the remainder in whole points. */
export function rebalancePriorities(weights: PriorityWeights, selected: PriorityKey, requested: number): PriorityWeights {
  const value = Math.max(0, Math.min(100, Math.round(requested)));
  const others = priorityCategories.map(category => category.key).filter(key => key !== selected);
  const remaining = 100 - value;
  const previousTotal = others.reduce((sum, key) => sum + weights[key], 0);
  const shares = others.map(key => {
    const exact = previousTotal === 0 ? remaining / others.length : weights[key] / previousTotal * remaining;
    return { key, points: Math.floor(exact), fraction: exact - Math.floor(exact) };
  });
  let unassigned = remaining - shares.reduce((sum, share) => sum + share.points, 0);
  [...shares].sort((a, b) => b.fraction - a.fraction).forEach(share => { if (unassigned > 0) { share.points++; unassigned--; } });
  const result = { ...weights, [selected]: value };
  shares.forEach(share => { result[share.key] = share.points; });
  return result;
}
export function prioritiesAreValid(weights: PriorityWeights): boolean {
  const values = priorityCategories.map(({ key }) => weights[key]);
  return values.every(value => Number.isFinite(value) && value >= 0 && value <= 100) && Math.abs(values.reduce((sum, value) => sum + value, 0) - 100) < 0.01;
}
