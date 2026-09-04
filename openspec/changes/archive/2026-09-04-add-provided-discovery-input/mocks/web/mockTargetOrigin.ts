export type MockTargetOrigin = "provided" | "live" | "fallback-live";

export const MOCK_TARGET_ORIGIN_PARAM = "__mockTargetOrigin";

export function readMockTargetOrigin(value: string | null): MockTargetOrigin | null {
  if (value === "provided" || value === "live" || value === "fallback-live") return value;
  return null;
}

export function targetOriginLabel(origin: MockTargetOrigin): string {
  if (origin === "provided") return "Provided target";
  if (origin === "fallback-live") return "Provided target · fell back to discovery";
  return "Discovered live";
}
