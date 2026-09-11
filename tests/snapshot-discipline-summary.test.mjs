import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
import {resolveStudy} from '../src/report/discipline.js';

const data = JSON.parse(readFileSync('public/data/snapshot/fields.json')).discipline_explorer;

test('node summary distinguishes sample coverage from publication proportion and keeps missing distinct from zero', async () => {
  const server = await createServer({server: {middlewareMode: true}, appType: 'custom'});
  try {
    const {default: Summary} = await server.ssrLoadModule('/src/report/DisciplineSummary.jsx');
    const render = study => renderToStaticMarkup(React.createElement(Summary, {study, populationLabel: study.population, cutoff: data.oa_cutoff}));
    for (const [taxonomy, node, numerator, denominator, share, percent] of [
      ['topics', 'https://openalex.org/subfields/2746', '1,511', '4,172,308', '3.002%', '0.036215%'],
      ['concepts', 'https://openalex.org/C71924100', '20,722', '54,171,563', '41.171%', '0.038253%'],
    ]) for (const metric of ['count', 'share', 'rate']) {
      const study = resolveStudy(data, ['oa'], {taxonomy, node, metric});
      const html = render(study);
      assert(html.includes(`${numerator} ÷ 50,331 × 100%`));
      assert(html.includes(`${numerator} ÷ ${denominator} × 100%`));
      assert(html.includes(share)); assert(html.includes(percent));
      assert(html.includes(`data-metric="${metric}"`));
      assert(html.includes('以下三项固定并列展示'));
      if (taxonomy === 'concepts') assert(html.includes('包含低分/零分标签'));
    }
    const rw = render(resolveStudy(data, ['rw'], {taxonomy: 'subjects', metric: 'share'}));
    assert(rw.includes('RW 未提供同口径发表论文分母'));
    const study = resolveStudy(data, ['oa'], {taxonomy: 'topics'});
    const zero = {...study, node: {...study.node, counts: {A1: [0]}, denominator: [100]}};
    assert(render(zero).includes('<strong>0%</strong>'));
    assert(render({...zero, node: {...zero.node, denominator: [0]}}).includes('分母为零，比率未定义'));
    assert(render({...zero, node: {...zero.node, counts: {A1: [1]}, denominator: [1000000000]}}).includes('&lt;0.000001%'));
  } finally {
    await server.close();
  }
});
