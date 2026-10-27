// Petites aides de rédaction française.

/** count(1, "union") → « 1 union » ; count(3, "union") → « 3 unions » ; pluriel irrégulier en 3e argument. */
export function count(n: number, singular: string, plural = `${singular}s`) {
  return `${n.toLocaleString("fr-FR")} ${n > 1 ? plural : singular}`;
}
