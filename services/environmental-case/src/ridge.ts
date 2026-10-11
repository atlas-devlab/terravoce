export interface RidgeModel {
  alpha: number; mean: number[]; scale: number[]; coefficients: number[]; residualIntercept: number;
}
/** Centered ridge: ||y - Xw||² + alpha ||w||²; all scaling uses training rows only. */
export function fitRidge(x: number[][], y: number[], alpha: number): RidgeModel {
  const n = x.length, p = x[0]?.length ?? 0;
  if (!n || !p || n !== y.length || !Number.isFinite(alpha) || alpha <= 0 ||
      x.some((r) => r.length !== p || r.some((v) => !Number.isFinite(v))) || y.some((v) => !Number.isFinite(v))) {
    throw new Error("Invalid ridge training inputs");
  }
  const mean = Array.from({ length: p }, (_, j) => x.reduce((s, r) => s + r[j]!, 0) / n);
  const scale = mean.map((m, j) => Math.sqrt(x.reduce((s, r) => s + (r[j]! - m) ** 2, 0) / n) || 1);
  const residualIntercept = y.reduce((s, v) => s + v, 0) / n;
  const standardized = x.map((r) => r.map((v, j) => (v - mean[j]!) / scale[j]!));
  const a = Array.from({ length: p }, (_, j) => Array.from({ length: p }, (_, k) =>
    standardized.reduce((s, r) => s + r[j]! * r[k]!, 0) + (j === k ? alpha : 0)));
  const b = Array.from({ length: p }, (_, j) => standardized.reduce((s, r, i) => s + r[j]! * (y[i]! - residualIntercept), 0));
  // Small dense system with partial pivoting; positive ridge penalty avoids singular correlated features.
  for (let j = 0; j < p; j++) {
    let pivot = j;
    for (let k = j + 1; k < p; k++) if (Math.abs(a[k]![j]!) > Math.abs(a[pivot]![j]!)) pivot = k;
    [a[j], a[pivot]] = [a[pivot]!, a[j]!]; [b[j], b[pivot]] = [b[pivot]!, b[j]!];
    const diagonal = a[j]![j]!;
    if (!Number.isFinite(diagonal) || Math.abs(diagonal) < 1e-12) throw new Error("Unstable ridge solve");
    for (let k = j + 1; k < p; k++) {
      const factor = a[k]![j]! / diagonal;
      for (let l = j; l < p; l++) a[k]![l] = a[k]![l]! - factor * a[j]![l]!;
      b[k] = b[k]! - factor * b[j]!;
    }
  }
  const coefficients = Array<number>(p).fill(0);
  for (let j = p - 1; j >= 0; j--) {
    const remaining = coefficients.reduce((s, w, k) => k > j ? s + a[j]![k]! * w : s, 0);
    coefficients[j] = (b[j]! - remaining) / a[j]![j]!;
  }
  if (coefficients.some((v) => !Number.isFinite(v))) throw new Error("Nonfinite ridge coefficients");
  return { alpha, mean, scale, coefficients, residualIntercept };
}
export function predictResidual(model: RidgeModel, features: number[]): number {
  if (features.length !== model.mean.length || features.some((v) => !Number.isFinite(v))) throw new Error("Invalid prediction features");
  return model.residualIntercept + features.reduce((s, v, j) => s + (v - model.mean[j]!) / model.scale[j]! * model.coefficients[j]!, 0);
}
