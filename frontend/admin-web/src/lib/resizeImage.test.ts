import { describe, expect, it } from 'vitest';

import { fitWithin } from './resizeImage';

describe('fitWithin', () => {
  it('leaves small images alone', () => {
    expect(fitWithin(800, 600)).toEqual({ width: 800, height: 600 });
  });
  it('scales a landscape phone photo to 1024 wide', () => {
    expect(fitWithin(4000, 3000)).toEqual({ width: 1024, height: 768 });
  });
  it('scales a portrait photo to 1024 tall', () => {
    expect(fitWithin(3000, 4000)).toEqual({ width: 768, height: 1024 });
  });
});
