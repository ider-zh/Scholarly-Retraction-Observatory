function check(condition, message) {if (!condition) throw new Error(message);}

export function validateExplorer(explorer, manifest) {
  check(explorer?.version === 'discipline-explorer-v1' && explorer.release_id === manifest.release_id, 'Mixed discipline explorer release');
  check(explorer.oa_cutoff === manifest.oa_snapshot_date && explorer.rw_cutoff === manifest.rw_snapshot_date, 'Explorer source date mismatch');
  check(explorer.year_start === 2000 && explorer.year_end === Number(manifest.oa_snapshot_date.slice(0, 4)), 'Invalid explorer year range');
  check(explorer.series_layout === 'total_then_publication_years_inclusive', 'Unknown explorer series encoding');
  check(/^[a-f0-9]{64}$/.test(explorer.provenance?.taxonomy_scan_sha256) && /^[a-f0-9]{64}$/.test(explorer.provenance?.concept_tree_sha256), 'Missing explorer provenance');
  const length = explorer.year_end - explorer.year_start + 2;
  const series = values => check(Array.isArray(values) && values.length === length && values.every(value => Number.isSafeInteger(value) && value >= 0) && values[0] >= values.slice(1).reduce((total, value) => total + value, 0), 'Invalid explorer count series');
  check(Array.isArray(explorer.taxonomies) && explorer.taxonomies.length === 3 && new Set(explorer.taxonomies.map(taxonomy => taxonomy.id)).size === 3, 'Incomplete explorer taxonomies');
  for (const taxonomy of explorer.taxonomies) {
    check(['subjects', 'topics', 'concepts'].includes(taxonomy.id), 'Unknown taxonomy');
    const populations = taxonomy.id === 'subjects' ? ['B'] : ['A1', 'C_D'];
    check(JSON.stringify(taxonomy.populations) === JSON.stringify(populations), 'Invalid taxonomy population');
    check(taxonomy.method && taxonomy.rate_policy && taxonomy.reference && taxonomy.levels?.length === 2, 'Missing taxonomy methodology');
    for (const population of populations) series(taxonomy.counts?.[population]);
    if (taxonomy.id === 'subjects') check(taxonomy.denominator === null, 'RW cannot claim a publication denominator');
    else series(taxonomy.denominator);
    check(Array.isArray(taxonomy.nodes) && taxonomy.nodes.length > 0 && taxonomy.nodes.length <= 2000, 'Invalid taxonomy node collection');
    const nodes = new Map(taxonomy.nodes.map(node => [node.id, node]));
    check(nodes.size === taxonomy.nodes.length, 'Duplicate taxonomy node');
    for (const node of taxonomy.nodes) {
      check(typeof node.id === 'string' && node.id && typeof node.label === 'string' && [0, 1].includes(node.level) && Array.isArray(node.parents), 'Invalid taxonomy node');
      check(node.level === 0 ? node.parents.length === 0 : node.parents.length > 0 && new Set(node.parents).size === node.parents.length && node.parents.every(parent => nodes.get(parent)?.level === 0), 'Invalid taxonomy parent graph');
      if (taxonomy.id === 'subjects') check(node.denominator === null, 'Unexpected RW node denominator');
      else {series(node.denominator); check(node.denominator.every((value, index) => value <= taxonomy.denominator[index]), 'Node denominator exceeds corpus');}
      for (const population of populations) {
        series(node.counts?.[population]);
        check(node.counts[population].every((value, index) => value <= taxonomy.counts[population][index] && (node.denominator === null || value <= node.denominator[index])), 'Node numerator exceeds its eligible denominator');
        if (taxonomy.id !== 'concepts' && node.level === 1 && !node.missing) for (const parent of node.parents) {
          if (!nodes.get(parent).navigation_only) check(node.counts[population].every((value, index) => value <= nodes.get(parent).counts[population][index]), 'Child count exceeds parent');
        }
      }
    }
  }
  return explorer;
}
