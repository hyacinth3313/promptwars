import type { EventState } from '../types';
export const demoState: EventState = {
  config: { session_id: 'demo', event_type: 'wedding', event_date: '2027-02-14', location: 'Bengaluru, Karnataka', total_budget: 1500000, guest_count: 150, currency: 'INR', priorities: { venue: .3, catering: .4, decor: .15, photography: .1, logistics: .05 } },
  budget: { total_budget: 1500000, remaining: 125000, overage: 0, is_over_budget: false, items: [{ category: 'Venue', allocated: 450000, estimated: 425000, verified: null, notes: 'A garden venue with room to celebrate.' }, { category: 'Catering', allocated: 600000, estimated: 560000, verified: null, notes: 'A seasonal menu for 150 guests.' }, { category: 'Decor', allocated: 225000, estimated: 200000, verified: null, notes: 'Soft florals and warm lights.' }, { category: 'Photography', allocated: 150000, estimated: 135000, verified: null, notes: 'The moments you’ll come back to.' }, { category: 'Logistics', allocated: 75000, estimated: 55000, verified: null, notes: 'Smooth arrivals and happy goodbyes.' }] },
  tasks: { last_updated: '2026-10-31T00:00:00Z', tasks: [
    { id: 'venue', title: 'Find your perfect venue', description: 'Shortlist garden venues and arrange a visit.', milestone: '3_months', due_date: '2026-11-14', depends_on: [], status: 'completed', estimated_cost: 425000 },
    { id: 'catering', title: 'Plan a menu to remember', description: 'Meet caterers and book a tasting.', milestone: '3_months', due_date: '2026-11-20', depends_on: ['venue'], status: 'in_progress', estimated_cost: 560000 },
    { id: 'invites', title: 'Send a little happy mail', description: 'Finalize the guest list and invitations.', milestone: '1_month', due_date: '2027-01-14', depends_on: ['venue'], status: 'pending', estimated_cost: null },
    { id: 'details', title: 'Bring the finishing touches together', description: 'Confirm flowers, seating, and your day-of plan.', milestone: '1_week', due_date: '2027-02-07', depends_on: ['catering', 'invites'], status: 'pending', estimated_cost: 200000 },
  ] }, vendors: [], tradeoff_options: [], applied_tradeoffs: [], created_at: '2026-10-31T00:00:00Z', updated_at: '2026-10-31T00:00:00Z',
};
