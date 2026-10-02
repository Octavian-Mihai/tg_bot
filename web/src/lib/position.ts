/** Fractional position for inserting at `index` in a column whose other cards have these (sorted) positions. */
export function positionAt(others: number[], index: number): number {
  const before = others[index - 1];
  const after = others[index];
  if (before === undefined && after === undefined) return 1;
  if (before === undefined) return after - 1;
  if (after === undefined) return before + 1;
  return (before + after) / 2;
}
