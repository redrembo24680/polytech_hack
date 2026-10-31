/** "380671234501" -> "+380 67 123 45 01"; falls back to "+digits". */
export function formatPhone(digits: string): string {
  const m = /^380(\d{2})(\d{3})(\d{2})(\d{2})$/.exec(digits);
  return m ? `+380 ${m[1]} ${m[2]} ${m[3]} ${m[4]}` : digits ? `+${digits}` : "";
}
