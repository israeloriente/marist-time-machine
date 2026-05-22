// Shared people/turma constants and helpers, so the year/class option lists
// and the collaborator range label don't drift across views.

export const CLASS_LETTERS = ["A", "B", "C", "D", "E", "F"] as const;

// Graduation years for student pickers: a window from 10 years ahead back ~100.
export function graduationYears(now = new Date().getFullYear()): number[] {
  return Array.from({ length: 111 }, (_, i) => now + 10 - i);
}

// Collaborator (teacher/staff) years span decades — wider, no future bias.
export function collabYears(now = new Date().getFullYear()): number[] {
  return Array.from({ length: 81 }, (_, i) => now - i);
}

// "2005–2012", "2005–atual", "?–2012", or null when neither bound is set.
export function formatCollabRange(
  entry: number | null | undefined,
  exit: number | null | undefined,
): string | null {
  if (entry == null && exit == null) return null;
  return `${entry ?? "?"}–${exit ?? "atual"}`;
}
