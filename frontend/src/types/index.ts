export type EventType = 'wedding' | 'birthday' | 'corporate' | 'community' | 'other';
export type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'late';
export interface EventConfig { session_id: string; event_type: EventType; event_date: string; location: string; total_budget: number; guest_count: number; priorities: Record<string, number>; currency: string }
export interface BudgetItem { category: string; allocated: number; estimated: number; verified: number | null; notes: string }
export interface BudgetBreakdown { total_budget: number; items: BudgetItem[]; remaining: number; overage: number; is_over_budget: boolean }
export interface TaskItem { id: string; title: string; description: string; milestone: '3_months' | '1_month' | '1_week' | 'day_of'; due_date: string; depends_on: string[]; status: TaskStatus; estimated_cost: number | null }
export interface TaskList { tasks: TaskItem[]; last_updated: string }
export interface VendorQuote { vendor_name: string; category: string; total_quoted: number; line_items: Record<string, unknown>[]; hidden_fees: string[]; inclusions: string[]; exclusions: string[]; payment_schedule: string; capacity: number | null; notes: string; is_verified: boolean }
export interface TradeoffItem { category: string; action: string; savings_inr: number; impact_description: string }
export interface TradeoffOption { title: string; description: string; total_savings_inr: number; tradeoffs: TradeoffItem[]; impact_on_other_categories: string; recommended: boolean }
export interface EventState { config: EventConfig; budget: BudgetBreakdown; tasks: TaskList; vendors: VendorQuote[]; tradeoff_options: TradeoffOption[]; applied_tradeoffs: TradeoffOption[]; created_at: string; updated_at: string; last_committed_scenario_id?: string | null }
export interface CreateSessionResponse { session_id: string; message: string }
export interface TaskStatusUpdateResponse { task: TaskItem; downstream_affected_task_ids: string[]; timeline_shifted: boolean; message: string; tasks: TaskList }
export interface IntakePlanResponse { budget: BudgetBreakdown; tasks: TaskList }
export interface TradeoffResponse { overage_amount: number; options: TradeoffOption[]; guidance_notes: string }
export interface ApplyTradeoffRequest { option_index?: number | null; option?: TradeoffOption | null; custom_notes?: string | null }
export interface RecalculateBudgetResponse { budget: BudgetBreakdown; is_over_budget: boolean; overage: number; tradeoffs: TradeoffResponse | null; message: string }
export interface TimelineShiftRequest { new_date?: string | null; late_task_ids?: string[] }
export interface TimelineShiftResponse { reasoning: string; critical_risks: string[]; updated_tasks: TaskList }
export interface TaskProgressStats { total: number; completed: number; in_progress: number; pending: number; late: number; completion_percentage: number }
export interface GroupedTasksResponse { session_id: string; stats: TaskProgressStats; milestones: Record<string, TaskItem[]>; last_updated: string }
export interface ScenarioDelta { budget_change: number; guest_count_delta: number; new_date?: string }
export interface WhatIfRequest { delta: ScenarioDelta }
export interface WhatIfResponse { scenario_summary: string; financial_impact: string; updated_budget: BudgetBreakdown; affected_tasks: string[]; recommendations: string[] }
export interface ScenarioPreviewResponse extends WhatIfResponse { scenario_id: string; base_updated_at: string; expires_at: string; committed_state: EventState; updated_config: EventConfig; updated_tasks: TaskList; critical_risks: string[] }
export interface CommitScenarioRequest { scenario_id: string }
export interface AnalyzeVendorRequest { quote_text: string; category?: string | null }
export interface ChatMessageRequest { message: string }
export interface ChatResponse { reply: string; session_id: string; suggested_actions: string[] }
