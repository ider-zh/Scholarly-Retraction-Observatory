import test from 'node:test';
import assert from 'node:assert/strict';
import {siteRoot, publicationRedirect, canonicalReportHash} from '../src/siteRoutes.js';
import {parseReportRoute} from '../src/report/routes.js';
import {REPORT_PAGES} from '../src/report/sections.js';

test('publication roots support domain and project-directory deployments', () => {
  for (const base of ['/', '/Scholarly-Retraction-Observatory/']) {
    for (const suffix of ['', 'index.html', 'reports/v1/', 'reports/v2/index.html', 'slides/v2/', 'presentation-v2/index.html']) assert.equal(siteRoot(base + suffix), base);
    assert.equal(publicationRedirect({pathname: base, hash: '#/report-v1'}), `${base}reports/v1/`);
    assert.equal(publicationRedirect({pathname: `${base}presentation-v2/index.html`, search: '?preview=1', hash: '#/13'}), `${base}slides/v2/?preview=1#/13`);
  }
});

test('legacy deep links retain filters and invalid parameter validation', () => {
  const hash = '#/snapshot/concepts/topic/discipline?sources=oa&population=A1&node=C123&metric=proportion';
  const short = canonicalReportHash(hash);
  assert.equal(short, '#/concepts/topic/discipline?sources=oa&population=A1&node=C123&metric=proportion');
  assert.deepEqual(parseReportRoute(hash, REPORT_PAGES), parseReportRoute(short, REPORT_PAGES));
  assert.equal(publicationRedirect({pathname: '/project/', hash}), `/project/reports/v2/${short}`);
  assert.equal(canonicalReportHash('#/snapshot/overview?sources=rw%2Coa'), '');
  assert.deepEqual(parseReportRoute('', REPORT_PAGES).sources, ['rw', 'oa']);
  assert(parseReportRoute('#/time?sources=invalid', REPORT_PAGES).error);
  assert(parseReportRoute('#/time?unknown=true', REPORT_PAGES).error);
  assert.equal(canonicalReportHash('#/time?sources=rw&slice=T1%2FB-retracted'), '#/time?sources=rw&slice=T1%2FB-retracted');
});
