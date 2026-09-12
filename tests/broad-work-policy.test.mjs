import test from 'node:test';
import assert from 'node:assert/strict';
import {BROAD_WORK_POLICY, isBroadChart} from '../src/report/workPolicy.js';
import {chartMethod, populationName, variantName} from '../src/report/reader.js';
import {overviewNarrative, screeningNote} from '../src/report/overview.js';

test('Broad screening text follows the policy and retains uncertainty', () => {
  const chart = {chart_id: 'screening', slice_id: 'A0-screening', population_key: 'A0', status: 'ready', scope: {work_policy: BROAD_WORK_POLICY, work_types: ['all']}, rows: [{id: 'retained_A1', numerator: 8, denominator: 10, value: 80, unit: 'percent'}]};
  assert(isBroadChart(chart));
  assert.match(overviewNarrative(chart).finding, /宽口径保留 8 条/);
  assert.match(overviewNarrative(chart).boundary, /身份不确定/);
  assert.match(chartMethod(chart)[0], /不限 OpenAlex 文献类型/);
  assert.match(screeningNote(chart, {id: 'excluded_known_notice'}), /另一篇原文/);
  const candidate = {...chart, population_key: 'A1'};
  assert.match(populationName(candidate), /宽口径/);
  assert.match(variantName(candidate), /宽口径/);
  assert(!isBroadChart({...chart, scope: {work_types: ['all']}}));
});
