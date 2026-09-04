import { expect, it } from "vitest";
import { parseDiscoveryInputDocument } from "./discoveryInput";

const validDocument = {
  schemaVersion: "1.0",
  kind: "discovery-input",
  taskId: "informational-task-id",
  candidate: {
    path: "/home/alice/work",
    workspace: "peer",
    agent: "Alice",
    bridgeId: "bridge-1",
  },
};

it("parses a strict discovery input document", () => {
  const result = parseDiscoveryInputDocument(JSON.stringify(validDocument));

  expect(result).toEqual({ ok: true, document: validDocument });
});

it.each([
  ["extra document field", { ...validDocument, extra: true }],
  ["extra candidate field", { ...validDocument, candidate: { ...validDocument.candidate, extra: true } }],
  ["unsafe path", { ...validDocument, candidate: { ...validDocument.candidate, path: "/tmp/work" } }],
  ["home root path", { ...validDocument, candidate: { ...validDocument.candidate, path: "/home/" } }],
])("rejects %s", (_label, document) => {
  const result = parseDiscoveryInputDocument(JSON.stringify(document));

  expect(result.ok).toBe(false);
});
