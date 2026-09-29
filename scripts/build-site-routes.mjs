import {readFile, writeFile, mkdir, cp} from 'node:fs/promises';

const root = await readFile('dist/index.html', 'utf8');
for (const version of ['v1', 'v2']) {
  const directory = `dist/reports/${version}`;
  await mkdir(directory, {recursive: true});
  const title = version === 'v1' ? '原版研究报告' : '快照研究报告';
  await writeFile(`${directory}/index.html`, root.replaceAll('./assets/', '../../assets/').replace(/<title>.*?<\/title>/, `<title>${title} · 学术撤稿观察</title>`));
}
await cp('dist/presentation-v2', 'dist/slides/v2', {recursive: true});
