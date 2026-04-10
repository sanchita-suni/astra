export type ScaffoldTemplate = "python-ml" | "nextjs-fullstack" | "fastapi-react" | "generic-python";

export interface ScaffoldedFile {
  path: string;
  bytes: number;
}

export interface ScaffoldResult {
  opportunity_id: string;
  template: ScaffoldTemplate;
  repo_name: string;
  repo_url: string | null;
  brief_markdown: string;
  files: ScaffoldedFile[];
  created_at: string;
  dry_run: boolean;
  brief_source: "llm" | "fallback";
}
