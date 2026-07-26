export interface User {
  id: string;
  email: string;
  role: 'admin' | 'editor' | 'student';
  display_name: string | null;
  grade: string | null;
  school: string | null;
  is_active: boolean;
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user?: User;
}

export interface Question {
  id: string;
  section: string;
  type: string;
  skill: string | null;
  difficulty: string | null;
  status: string;
  current_version?: {
    id: string;
    stem: string;
    passage: string | null;
    options: { label: string; text: string }[] | null;
    correct_answer: string;
    explanation: string | null;
  };
}

export interface ExamModule {
  id: string;
  section: string;
  module_no: number;
  form: string;
  time_limit_min: number;
  question_count: number;
  selection_rules: SelectionRule[];
}

export interface SelectionRule {
  id: string;
  skill: string | null;
  difficulty: string | null;
  count: number;
}

export interface Exam {
  id: string;
  title: string;
  description: string | null;
  status: string;
  modules: ExamModule[];
  created_at: string;
}

export interface AttemptState {
  id: string;
  state: string;
  section: string;
  module_no: number;
  form: string;
  remaining_ms: number;
  questions: AttemptQuestion[];
  question_palette: { answered: number; unanswered: number; total: number };
}

export interface AttemptQuestion {
  aq_id: string;
  type: string;
  stem: string;
  options: { label: string; text: string }[] | null;
  your_answer: string | null;
  marked: boolean;
}

export interface ModuleSubmitResult {
  m1_score: number;
  total: number;
  threshold: number;
  chosen_form: string;
  next_state: string;
}

export interface AnalysisResult {
  attempt_id: string;
  scaled: { rw: number; math: number; total: number };
  raw: { rw: number; math: number };
  routing: Record<string, { m1_score: number; threshold: number; chosen_form: string }>;
  domain_breakdown: Record<string, unknown>;
  weak_skills: Record<string, number>;
}

export interface Plan {
  plan_id: string;
  title: string;
  tasks: PlanTask[];
}

export interface PlanTask {
  id: string;
  skill: string;
  target_count: number;
  completed_count: number;
  priority: number;
  status: string;
}
