(() => {
  const slides = [...document.querySelectorAll('.deck > .slide')];
  const picker = document.querySelector('#slide-picker');
  const dialog = document.querySelector('#evidence-dialog');
  const evidence = JSON.parse(document.querySelector('#presentation-evidence').textContent);
  let selectedEvidence;
  const escape = value => String(value).replace(/[&<>"']/g, character => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]));
  const number = value => value == null ? '不适用' : Number(value).toLocaleString('zh-CN', {maximumFractionDigits: 6});
  function sync() {
    const activeIndex = Math.max(0, slides.findIndex(slide => slide.classList.contains('is-active')));
    slides.forEach((slide, index) => {slide.inert = index !== activeIndex; slide.setAttribute('aria-hidden', String(index !== activeIndex));});
    picker.value = String(activeIndex + 1);
    document.querySelector('#slide-status').textContent = `${activeIndex + 1} / ${slides.length}`;
    document.querySelector('#previous').disabled = activeIndex === 0;
    document.querySelector('#next').disabled = activeIndex === slides.length - 1;
    document.title = `${activeIndex + 1}. ${slides[activeIndex].dataset.title} · HTML-PPT (v2)`;
  }
  function go(page) {
    location.hash = `#/${Math.min(slides.length, Math.max(1, page))}`;
  }
  document.querySelector('#previous').onclick = () => go(Number(picker.value) - 1);
  document.querySelector('#next').onclick = () => go(Number(picker.value) + 1);
  picker.onchange = () => go(Number(picker.value));
  document.querySelectorAll('[data-key]').forEach(button => {button.onclick = () => document.dispatchEvent(new KeyboardEvent('keydown', {key: button.dataset.key, bubbles: true}));});
  document.addEventListener('keydown', event => {
    if (dialog.open || event.target.closest?.('button,a,select,input,textarea,summary')) event.stopImmediatePropagation();
  }, true);
  document.querySelector('#close-evidence').onclick = () => dialog.close();
  document.querySelectorAll('.deck [data-evidence]').forEach(button => {
    button.onclick = () => {
      selectedEvidence = evidence[Number(button.dataset.evidence)];
      const data = selectedEvidence.chart;
      const extraColumns = data.chart_id === 'C4' ? [['median', '中位数（条）'], ['targets_with_edges', '至少被引一次（篇）'], ['targets_with_edges_pct', '至少被引一次（%）'], ['excluded_targets', '未入选五年队列（篇）']] : [];
      document.querySelector('#evidence-content').innerHTML = `<h2 id="evidence-title">${escape(data.title)}</h2><p>总体：${escape(data.population_key)}；指标：${escape(data.metric_id)}；截止：${escape(data.metric_observation_cutoff)}。</p><div class="evidence-scroll" tabindex="0" role="region" aria-label="图表完整数据，可横向滚动"><table><caption>已发布聚合单元（保留原始精度；n / N 不一定表示撤稿比例）</caption><thead><tr><th scope="col">分组</th><th scope="col">数值</th><th scope="col">单位</th><th scope="col">n</th><th scope="col">N</th>${extraColumns.map(([, label]) => `<th scope="col">${label}</th>`).join('')}</tr></thead><tbody>${data.rows.map(row => `<tr><th scope="row">${escape(row.label)}${row.partial ? '（未结束）' : ''}${data.metric_id === 'proportion' && !row.ranking_eligible ? '（小基数或无分母，不参与比例排名、着色或趋势连线）' : ''}</th><td>${number(row.value)}</td><td>${escape(row.unit)}</td><td>${number(row.numerator)}</td><td>${number(row.denominator)}</td>${extraColumns.map(([key]) => `<td>${number(row[key])}</td>`).join('')}</tr>`).join('')}</tbody></table></div><h3>方法与限制</h3><ul>${data.limitations.map(text => `<li>${escape(text)}</li>`).join('')}</ul><p class="release">${escape(selectedEvidence.file)}<br/>${escape(data.chart_id)} / ${escape(data.slice_id)}<br/>${escape(data.release_id)}<br/>SHA-256：${escape(selectedEvidence.sha256)}</p>`;
      dialog.showModal();
    };
  });
  document.querySelector('#export-evidence').onclick = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(selectedEvidence, null, 2)], {type: 'application/json'}));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${selectedEvidence.chart.chart_id}-${selectedEvidence.chart.slice_id}.json`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  function observe() {
    slides.forEach(slide => new MutationObserver(sync).observe(slide, {attributes: true, attributeFilter: ['class']}));
    document.querySelectorAll('.overview .thumb').forEach((thumb, index) => {
      thumb.tabIndex = 0;
      thumb.setAttribute('role', 'button');
      thumb.setAttribute('aria-label', `第 ${index+1} 页：${slides[index].dataset.title}`);
      thumb.querySelector('.mini-slide')?.setAttribute('aria-hidden', 'true');
      thumb.addEventListener('keydown', event => {if (event.key === 'Enter' || event.key === ' ') {event.preventDefault();event.stopImmediatePropagation();thumb.click();}});
    });
    sync();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', observe); else observe();
})();
