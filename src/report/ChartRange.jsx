import React from 'react';
import Slider from 'rc-slider';
import 'rc-slider/assets/index.css';
import './range.css';

export default function ChartRange({rows, start, end, onChange, onReset}) {
  return <div className="snapshot-chart-range">
    <div className="snapshot-range-control" role="group" aria-label="图表显示范围">
      <div className="snapshot-range-heading"><span>显示范围</span><output>{rows[start].label} — {rows[end].label}</output></div>
      <Slider range min={0} max={rows.length - 1} step={1} value={[start, end]} allowCross={false} pushable={false} onChange={onChange} ariaLabelForHandle={['显示起点', '显示终点']} ariaValueTextFormatterForHandle={value => rows[value].label}/>
    </div>
    <button onClick={onReset}>重置图表范围</button>
    <p className="snapshot-caption">仅缩放已发布的数据点；每点的分子、分母及完整数据导出不变。</p>
  </div>;
}
