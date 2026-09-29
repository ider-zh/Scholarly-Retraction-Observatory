import React, {useState} from 'react';
import './share-link.css';

export default function ShareLink() {
  const [status, setStatus] = useState(''), [fallback, setFallback] = useState('');
  async function copy() {
    const url = window.location.href;
    try {
      await navigator.clipboard.writeText(url);
      setFallback(''); setStatus('链接已复制');
    } catch {
      setFallback(url); setStatus('请复制以下链接');
    }
  }
  return <div className="publication-share"><button type="button" onClick={copy}>分享当前内容</button><span role="status">{status}</span>{fallback && <input aria-label="当前内容分享链接" readOnly value={fallback} onFocus={event => event.target.select()}/>}</div>;
}
