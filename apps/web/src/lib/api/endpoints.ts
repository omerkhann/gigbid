// One function per API call, so pages never build URLs by hand.
import { api, unwrap, type ApprovalIn, type Schemas } from "./client";

export const endpoints = {
  me: () => unwrap(api.GET("/auth/me")),
  login: (email: string, password: string) => unwrap(api.POST("/auth/login", { body: { email, password } })),
  register: (body: Schemas["RegisterIn"]) => unwrap(api.POST("/auth/register", { body })),
  logout: () => unwrap(api.POST("/auth/logout")),

  inbox: (status?: string) =>
    unwrap(api.GET("/jobs/inbox", { params: { query: { status: status || undefined, sort: "fit" } } })),
  job: (jobId: string) => unwrap(api.GET("/jobs/{job_id}", { params: { path: { job_id: jobId } } })),
  analyze: (jobId: string) => unwrap(api.POST("/jobs/{job_id}/analyze", { params: { path: { job_id: jobId } } })),
  scout: () => unwrap(api.POST("/scout/run")),

  approvals: () => unwrap(api.GET("/approvals")),
  decide: (threadId: string, body: ApprovalIn) =>
    unwrap(api.POST("/approvals/{thread_id}", { params: { path: { thread_id: threadId } }, body })),
  regenerate: (threadId: string, body: Schemas["RegenerateIn"]) =>
    unwrap(api.POST("/approvals/{thread_id}/regenerate", { params: { path: { thread_id: threadId } }, body })),

  runs: () => unwrap(api.GET("/runs")),
  run: (threadId: string) => unwrap(api.GET("/runs/{thread_id}", { params: { path: { thread_id: threadId } } })),

  pipeline: () => unwrap(api.GET("/pipeline")),
  threads: () => unwrap(api.GET("/messages")),
  thread: (id: string) => unwrap(api.GET("/messages/{conversation_id}", { params: { path: { conversation_id: id } } })),
  draftReply: (id: string) =>
    unwrap(api.POST("/messages/{conversation_id}/draft", { params: { path: { conversation_id: id } } })),

  analytics: () => unwrap(api.GET("/analytics")),
  settings: () => unwrap(api.GET("/settings")),
  saveSettings: (body: Schemas["SettingsIn"]) => unwrap(api.PUT("/settings", { body })),
  searches: () => unwrap(api.GET("/settings/searches")),
  addSearch: (body: Schemas["SavedSearchIn"]) => unwrap(api.POST("/settings/searches", { body })),
  deleteSearch: (id: string) =>
    unwrap(api.DELETE("/settings/searches/{search_id}", { params: { path: { search_id: id } } })),
  memory: () => unwrap(api.GET("/memory")),
  forget: (namespace: string, key: string) =>
    unwrap(api.DELETE("/memory/{namespace}/{key}", { params: { path: { namespace, key } } })),
  marketplaceHealth: () => unwrap(api.GET("/health/marketplace")),
};
