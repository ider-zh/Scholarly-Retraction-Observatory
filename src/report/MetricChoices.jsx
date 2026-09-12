import React, {useId} from 'react';
import './metric-choices.css';

export default function MetricChoices({value, options, onChange, unavailable = [], legend = '图表指标'}) {
  const name = useId();
  return <fieldset className="report-metric-choices"><legend>{legend}</legend>{Object.entries(options).map(([key, label]) => <label key={key}><input type="radio" name={name} value={key} checked={value === key} disabled={unavailable.includes(key)} onChange={() => onChange(key)}/><span>{label}{unavailable.includes(key) && '（无同口径分母）'}</span></label>)}</fieldset>;
}
