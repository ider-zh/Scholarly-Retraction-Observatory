import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {geoNaturalEarth1, geoPath} from 'd3-geo';

const raw = await readFile(process.argv[2]);
const sha256 = createHash('sha256').update(raw).digest('hex');
assert.equal(sha256, '6866c877d39cba9c357620878839b336d569f8c662d3cfab4cb1dbe2d39c977f');
const world = JSON.parse(raw);
const projection = geoNaturalEarth1().fitExtent([[8, 8], [952, 482]], {type: 'Sphere'});
const path = geoPath(projection).digits(1);
const regions = world.features.map(feature => ({id: String(feature.properties.NE_ID), code: /^[A-Z]{2}$/.test(feature.properties.ISO_A2_EH) ? feature.properties.ISO_A2_EH : null, name: feature.properties.NAME, path: path(feature)}));
assert.equal(new Set(regions.map(region => region.id)).size, regions.length);
process.stdout.write(JSON.stringify({source: 'Natural Earth v5.1.2, 1:110m admin-0 countries', sha256, projection: 'Natural Earth 1', viewBox: '0 0 960 490', regions})+'\n');
