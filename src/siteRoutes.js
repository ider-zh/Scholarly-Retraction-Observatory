export function siteRoot(pathname = typeof window === 'undefined' ? '/' : window.location.pathname) {
  return pathname.replace(/(?:reports\/v[12]|slides\/v2|presentation-v2)(?:\/index\.html|\/)?$/, '').replace(/index\.html$/, '').replace(/\/?$/, '/');
}

export function siteHref(path = '') {
  return `${siteRoot()}${path}`;
}

export function canonicalReportHash(hash) {
  const short = hash.replace(/^#\/snapshot(?=\/|\?|$)/, '#');
  const [path, query = ''] = short.split('?');
  const params = new URLSearchParams(query);
  if (params.get('sources') === 'rw,oa') params.delete('sources');
  const suffix = params.toString();
  if ((!path || ['#', '#/', '#/overview'].includes(path)) && !suffix) return '';
  return `${path || '#/overview'}${suffix ? `?${suffix}` : ''}`;
}

export function publicationRedirect({pathname, search = '', hash = ''}) {
  const root = siteRoot(pathname);
  if (/\/presentation-v2(?:\/index\.html|\/)?$/.test(pathname)) return `${root}slides/v2/${search}${hash}`;
  if (/^#\/snapshot(?:\/|\?|$)/.test(hash)) return `${root}reports/v2/${search}${canonicalReportHash(hash)}`;
  if (/^#\/report-v1(?:\?|$)/.test(hash)) return `${root}reports/v1/${search}${hash.replace(/^#\/report-v1/, '#/').replace(/^#\/$/, '')}`;
  return null;
}
