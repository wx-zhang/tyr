import type { DiscoveryInputDocument } from "../../api/client";

export type DiscoveryInputParseResult =
  | { ok: true; document: DiscoveryInputDocument }
  | { ok: false; error: string };

const DOCUMENT_FIELDS = ["schemaVersion", "kind", "taskId", "candidate"];
const CANDIDATE_FIELDS = ["path", "workspace", "agent", "bridgeId"];

function nonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function exactFields(
  object: Record<string, unknown>, allowed: string[], required: string[] = allowed,
): string | null {
  for (const field of required) {
    if (!(field in object)) return `Missing field "${field}".`;
  }
  for (const field of Object.keys(object)) {
    if (!allowed.includes(field)) return `Unexpected field "${field}".`;
  }
  return null;
}

export function parseDiscoveryInputDocument(text: string): DiscoveryInputParseResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return { ok: false, error: "The file does not contain valid JSON." };
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    return { ok: false, error: "The document must be a JSON object." };
  }
  const document = parsed as Record<string, unknown>;
  const documentFieldsError = exactFields(document, DOCUMENT_FIELDS);
  if (documentFieldsError) return { ok: false, error: documentFieldsError };
  if (document.schemaVersion !== "1.0") {
    return {
      ok: false,
      error: `Unsupported schemaVersion ${JSON.stringify(document.schemaVersion)}. Expected "1.0".`,
    };
  }
  if (document.kind !== "discovery-input") {
    return {
      ok: false,
      error: `Unexpected kind ${JSON.stringify(document.kind)}. Expected "discovery-input".`,
    };
  }
  if (!nonEmptyString(document.taskId)) {
    return { ok: false, error: "taskId must be a non-empty string." };
  }
  const candidate = document.candidate;
  if (typeof candidate !== "object" || candidate === null || Array.isArray(candidate)) {
    return { ok: false, error: "candidate must be a JSON object." };
  }
  const candidateRecord = candidate as Record<string, unknown>;
  const candidateFieldsError = exactFields(candidateRecord, CANDIDATE_FIELDS, ["workspace", "bridgeId"]);
  if (candidateFieldsError) return { ok: false, error: `candidate: ${candidateFieldsError}` };
  for (const field of CANDIDATE_FIELDS) {
    if ((field === "path" || field === "agent") && candidateRecord[field] == null) continue;
    if (!nonEmptyString(candidateRecord[field])) {
      return { ok: false, error: `candidate.${field} must be a non-empty string.` };
    }
  }
  return {
    ok: true,
    document: {
      schemaVersion: "1.0",
      kind: "discovery-input",
      taskId: document.taskId,
      candidate: {
        ...(candidateRecord.path != null ? { path: candidateRecord.path as string } : {}),
        workspace: candidateRecord.workspace as string,
        ...(candidateRecord.agent != null ? { agent: candidateRecord.agent as string } : {}),
        bridgeId: candidateRecord.bridgeId as string,
      },
    },
  };
}

export async function readDiscoveryInputFile(file: File): Promise<DiscoveryInputParseResult> {
  let text: string;
  try {
    text = await file.text();
  } catch {
    return { ok: false, error: "The selected file could not be read." };
  }
  return parseDiscoveryInputDocument(text);
}
