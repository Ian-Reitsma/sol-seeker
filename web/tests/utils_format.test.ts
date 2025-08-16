// @ts-ignore - utils.js is plain JS
import { formatSol, formatSolChange, formatPercent } from '../public/js/utils.js';

describe('utils formatters', () => {
  test('formatSol shows SOL and USD', () => {
    expect(formatSol(2, 10)).toBe('2.00 SOL ($20.00)');
  });

  test('formatSolChange handles sign', () => {
    expect(formatSolChange(-1.5, 20)).toBe('-1.50 SOL ($30.00)');
    expect(formatSolChange(1.5, 20)).toBe('+1.50 SOL ($30.00)');
  });

  test('formatPercent adds sign', () => {
    expect(formatPercent(-0.25)).toBe('-0.25%');
    expect(formatPercent(0.5)).toBe('+0.50%');
  });
});
