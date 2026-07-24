export type BaseRecord = {
  id: string;
  workspace_id: string;
  created_at: string;
  updated_at: string;
};

export type Insight = BaseRecord & {
  title: string;
  category: string;
  severity: string;
  summary: string;
  evidence: string[];
};

export type Recommendation = BaseRecord & {
  title: string;
  priority: string;
  action: string;
  reason: string;
  expected_impact: string;
  owner_agent: string;
  confidence: number;
  status: string;
  founder_note: string;
};

export type IntelligenceRun = BaseRecord & {
  executive_summary: string;
  health_score: number;
  forecast: string;
  insights: Insight[];
  recommendations: Recommendation[];
};

export type Briefing = BaseRecord & {
  greeting: string;
  business_snapshot: string[];
  top_signal: string;
  top_risk: string;
  recommendation: string;
  actions_completed: string[];
  actions_awaiting_approval: string[];
};

export type AgentRun = BaseRecord & {
  agent: string;
  action: string;
  result: string;
  metadata: Record<string, unknown>;
  estimated_minutes_saved: number;
};

export type Dashboard = {
  health_score: number | null;
  latest_intelligence: IntelligenceRun | null;
  latest_briefing: Briefing | null;
  counts: Record<string, number>;
  recent_activity: AgentRun[];
};

export type Source = BaseRecord & {
  source_type: string;
  name: string;
  status: string;
  data: Record<string, unknown>;
};

export type KnowledgeNode = BaseRecord & {
  node_type: string;
  label: string;
  properties: { label?: string; value?: unknown; unit?: string };
  confidence: number;
};

export type KnowledgeGraph = {
  sources: Source[];
  nodes: KnowledgeNode[];
  edges: Array<BaseRecord & {
    from_node_id: string;
    to_node_id: string;
    relation: string;
  }>;
};

export type Campaign = BaseRecord & {
  recommendation_id: string;
  name: string;
  channel: string;
  audience: string;
  goal: string;
  status: string;
  assets_created: number;
  executions: number;
};

export type GrowthAsset = BaseRecord & {
  campaign_id: string;
  asset_type: string;
  title: string;
  content: string;
  call_to_action: string;
  grounding_facts: string[];
  status: string;
};

export type Approval = BaseRecord & {
  action_type: string;
  entity_type: string;
  entity_id: string;
  title: string;
  content: string;
  reason: string;
  status: string;
  revision: number;
  execution_status: string;
  execution_provider?: string;
  provider_message_id?: string;
};

export type SupportTicket = BaseRecord & {
  customer_name: string;
  customer_email: string;
  subject: string;
  message: string;
  priority: string;
  status: string;
  draft_status: string;
  escalation_reason?: string;
  channel?: string;
  customer_phone?: string;
  latest_message?: string;
  external_conversation_id?: string;
};

export type GitHubConnectionStatus = {
  connected: boolean;
  account_connected?: boolean;
  repository_connected: boolean;
  status: string;
  connection_type?: string | null;
  github_login?: string | null;
  github_name?: string | null;
  github_avatar_url?: string | null;
  selected_repository?: string | null;
  selected_branch?: string | null;
  repository_private?: boolean | null;
  repository_html_url?: string | null;
  repository_description?: string | null;
  last_synced_at?: string | null;
  product_id?: string | null;
};

export type OnboardingStatus = {
  complete: boolean;
  current_step: string;
  github: GitHubConnectionStatus;
};

export type GitHubRepository = {
  id: number;
  full_name: string;
  name: string;
  description: string | null;
  private: boolean;
  default_branch: string;
  language: string | null;
  updated_at: string;
  html_url: string;
  owner_avatar_url: string | null;
};

export type Integration = {
  key: "github" | "firestore" | "stripe" | "posthog" | "gmail" | "whatsapp";
  name: string;
  status: string;
  mode: string;
  description: string;
  available: boolean;
  details: Record<string, unknown>;
};


export type WhatsAppConversation = BaseRecord & {
  customer_phone: string;
  customer_name: string;
  last_message: string;
  last_message_type: string;
  last_message_at: string;
  last_inbound_at: string;
  unread_count: number;
  message_count: number;
  ticket_id: string;
  status: string;
};

export type WhatsAppMessage = BaseRecord & {
  external_message_id: string;
  conversation_id: string;
  direction: "inbound" | "outbound";
  customer_phone: string;
  customer_name: string;
  message_type: string;
  body: string;
  provider_timestamp: string;
  delivery_status: string;
};


export type WhatsAppEmbeddedConfig = {
  enabled: boolean;
  app_id: string;
  config_id: string;
  graph_version: string;
  feature_type: string;
  missing_configuration: string[];
  webhook_callback_url: string;
};

export type WhatsAppEmbeddedSession = {
  waba_id: string;
  phone_number_id: string;
  business_id?: string;
  flow_type?: string;
};

export type OperationReadiness = {
  ready: boolean;
  missing_required: string[];
  connected_sources: string[];
  data_gaps: string[];
};

export type OperationRun = BaseRecord & {
  trigger: string;
  status: string;
  message: string;
  connected_sources: string[];
  business_review_id?: string;
  recommendation_id?: string;
  action_plan_id?: string;
  error?: string;
};

export type OperationStep = BaseRecord & {
  operation_run_id?: string;
  action_plan_id?: string;
  key: string;
  label: string;
  position: number;
  status: string;
  result: string;
};

export type EvidenceBundle = BaseRecord & {
  operation_run_id: string;
  key: string;
  source_key: string;
  source_name: string;
  source_object_id?: string;
  fact: string;
  value: unknown;
  unit: string;
  display_value: string;
  confidence: number;
  retrieved_at?: string;
};

export type ReviewFinding = BaseRecord & {
  business_review_id: string;
  operation_run_id: string;
  title: string;
  category: string;
  severity: string;
  summary: string;
  why_it_matters: string;
  evidence_ids: string[];
};

export type BusinessReview = BaseRecord & {
  operation_run_id: string;
  opening_message: string;
  executive_summary: string;
  review_scope: string[];
  data_gaps: string[];
  status: string;
  connected_sources: string[];
  evidence_count: number;
  recommendation_id?: string;
};

export type OperatingRecommendation = Recommendation & {
  business_review_id: string;
  operation_run_id: string;
  objective: string;
  risk_level: string;
  owner_workflow: string;
  suggested_channel: string;
  audience: string;
  success_metric: string;
  time_horizon: string;
  alternatives: string[];
  evidence_ids: string[];
};

export type ActionDeliverable = {
  type: string;
  id: string;
  title: string;
  status: string;
};

export type ActionPlan = BaseRecord & {
  recommendation_id: string;
  business_review_id: string;
  operation_run_id: string;
  title: string;
  objective: string;
  audience: string;
  channel: string;
  success_metric: string;
  time_horizon: string;
  status: string;
  deliverables: ActionDeliverable[];
  approval_ids: string[];
  executed_approval_ids?: string[];
  execution_provider?: string;
};

export type OutcomeCheck = BaseRecord & {
  action_plan_id: string;
  recommendation_id: string;
  status: string;
  success_metric: string;
  time_horizon: string;
  latest_result?: string;
  baseline?: Record<string, unknown>;
  observed?: Record<string, unknown>;
};

export type CommandCenter = {
  readiness: OperationReadiness;
  operation_run: OperationRun | null;
  operation_steps: OperationStep[];
  review: BusinessReview | null;
  findings: ReviewFinding[];
  recommendation: OperatingRecommendation | null;
  evidence: EvidenceBundle[];
  action_plan: ActionPlan | null;
  action_steps: OperationStep[];
  approvals: Approval[];
  outcome: OutcomeCheck | null;
};
