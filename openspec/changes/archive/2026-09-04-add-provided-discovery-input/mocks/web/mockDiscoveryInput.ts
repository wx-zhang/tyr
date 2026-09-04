export type MockDiscoveryInputDocument = {
  schemaVersion: "1.0";
  kind: "discovery-input";
  taskId: string;
  candidate: {
    path: string;
    workspace: string;
    agent: string;
    bridgeId: string;
  };
};

export type MockDiscoveryInputState = {
  document: MockDiscoveryInputDocument;
  fallbackToDiscovery: boolean;
};

export type MockDiscoveryInputParseResult =
  | { ok: true; document: MockDiscoveryInputDocument }
  | { ok: false; error: string };

export const MOCK_DISCOVERY_INPUT_STATE_KEY = "__mockDiscoveryInput";

const DOCUMENT_FIELDS = ["schemaVersion", "kind", "taskId", "candidate"];
const CANDIDATE_FIELDS = ["path", "workspace", "agent", "bridgeId"];

function nonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function exactFields(object: Record<string, unknown>, allowed: string[]): string | null {
  for (const field of allowed) {
    if (!(field in object)) return `Missing field "${field}".`;
  }
  for (const field of Object.keys(object)) {
    if (!allowed.includes(field)) return `Unexpected field "${field}".`;
  }
  return null;
}

export function parseDiscoveryInputDocument(text: string): MockDiscoveryInputParseResult {
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
  const candidateFieldsError = exactFields(candidateRecord, CANDIDATE_FIELDS);
  if (candidateFieldsError) return { ok: false, error: `candidate: ${candidateFieldsError}` };
  for (const field of CANDIDATE_FIELDS) {
    if (!nonEmptyString(candidateRecord[field])) {
      return { ok: false, error: `candidate.${field} must be a non-empty string.` };
    }
  }
  const path = candidateRecord.path as string;
  if (!path.startsWith("/home/")) {
    return {
      ok: false,
      error: "candidate.path must be an absolute path under /home.",
    };
  }
  if (path.split("/").includes("..")) {
    return {
      ok: false,
      error: "candidate.path must not contain parent traversal.",
    };
  }
  return {
    ok: true,
    document: {
      schemaVersion: "1.0",
      kind: "discovery-input",
      taskId: document.taskId,
      candidate: {
        path,
        workspace: candidateRecord.workspace as string,
        agent: candidateRecord.agent as string,
        bridgeId: candidateRecord.bridgeId as string,
      },
    },
  };
}

export async function readDiscoveryInputFile(file: File): Promise<MockDiscoveryInputParseResult> {
  let text: string;
  try {
    text = await file.text();
  } catch {
    return { ok: false, error: "The selected file could not be read." };
  }
  return parseDiscoveryInputDocument(text);
}

export function mockDiscoveryInputStateFromRouterState(
  state: unknown,
): MockDiscoveryInputState | null {
  if (typeof state !== "object" || state === null) return null;
  const candidate = (state as Record<string, unknown>)[MOCK_DISCOVERY_INPUT_STATE_KEY];
  if (typeof candidate !== "object" || candidate === null) return null;
  const record = candidate as Record<string, unknown>;
  if (typeof record.document !== "object" || record.document === null) return null;
  return {
    document: record.document as MockDiscoveryInputDocument,
    fallbackToDiscovery: record.fallbackToDiscovery === true,
  };
}
