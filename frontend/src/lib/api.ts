import axios from 'axios';
import type { AnalyzeVendorRequest, ApplyTradeoffRequest, ChatMessageRequest, ChatResponse, CommitScenarioRequest, CreateSessionResponse, EventConfig, EventState, RecalculateBudgetResponse, ScenarioPreviewResponse, TaskStatus, TaskStatusUpdateResponse, TimelineShiftRequest, TimelineShiftResponse, TradeoffResponse, VendorQuote, WhatIfRequest } from '../types';
export const api = axios.create({ baseURL: import.meta.env?.VITE_API_URL || 'https://gather-genai.onrender.com/api', timeout: 90000, headers: { 'Content-Type': 'application/json' } });
const path = (id: string) => `/sessions/${encodeURIComponent(id)}`;
export const plannerApi = {
  createSession: async () => (await api.post<CreateSessionResponse>('/sessions')).data,
  getSession: async (id: string, signal?: AbortSignal) => (await api.get<EventState>(path(id), { signal })).data,
  initialize: async (config: EventConfig) => (await api.post<EventState>(`${path(config.session_id)}/intake`, config)).data,
  updateTask: async (id: string, taskId: string, status: TaskStatus) => (await api.post<TaskStatusUpdateResponse>(`${path(id)}/tasks/${encodeURIComponent(taskId)}/status`, { status })).data,
  recalculateBudget: async (id: string) => (await api.post<RecalculateBudgetResponse>(`${path(id)}/recalculate-budget`)).data,
  updateBudgetItems: async (id: string, items: EventState['budget']['items']) => (await api.patch<EventState>(path(id), { budget: { items }, tradeoff_options: [] })).data,
  generateTradeoffs: async (id: string) => (await api.post<TradeoffResponse>(`${path(id)}/tradeoffs`, undefined, { params: { force_refresh: true } })).data,
  applyTradeoff: async (id: string, request: ApplyTradeoffRequest) => (await api.post<EventState>(`${path(id)}/apply-tradeoff`, request)).data,
  shiftTimeline: async (id: string, request: TimelineShiftRequest) => (await api.post<TimelineShiftResponse>(`${path(id)}/shift-timeline`, request)).data,
  analyzeVendor: async (id: string, request: AnalyzeVendorRequest) => (await api.post<VendorQuote>(`${path(id)}/analyze-vendor`, request, { params: { add_to_state: true } })).data,
  chat: async (id: string, request: ChatMessageRequest) => (await api.post<ChatResponse>(`${path(id)}/chat`, request)).data,
  whatIf: async (id: string, request: WhatIfRequest) => (await api.post<ScenarioPreviewResponse>(`${path(id)}/what-if`, request)).data,
  commitScenario: async (id: string, request: CommitScenarioRequest) => (await api.post<EventState>(`${path(id)}/commit-scenario`, request)).data,
};
export function apiError(error: unknown) {
  if (axios.isAxiosError(error)) {
    if (error.code === 'ECONNABORTED') return 'Planning is taking a little longer. Please try again.';
    if (!error.response) return 'We couldn’t connect to your planner. Check your connection and try again in a moment.';
    // Never show provider errors, stack traces, or raw validation payloads in the UI.
    switch (error.response.status) {
      case 400: case 422: return 'A little detail needs another look. Check your entries and try again.';
      case 401: case 403: return 'We couldn’t open this plan with your current access. Please return home and try again.';
      case 404: return 'We couldn’t find that saved plan or preview. Refresh your plan, or start a new celebration from home.';
      case 409: return 'Your saved plan has changed. Refresh it and review your changes before trying again.';
      case 410: return 'This preview has expired. Run a fresh scenario to explore your latest plan.';
      case 429: return 'Your planning companion needs a brief pause. Please try again in a little while.';
      case 502: case 503: case 504: return 'Your planning companion is taking a little break. Please try again shortly.';
    }
  }
  return 'Something went wrong. Please try again.';
}
