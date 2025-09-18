'use client';

import { useEffect, useMemo, useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || '';

type JobDoc = any;

export default function JobPage(props: { params: { id: string } }) {
  const jobId = props.params.id;
  const [doc, setDoc] = useState<JobDoc | null>(null);
  const [err, setErr] = useState('');
  const [toast, setToast] = useState<string>('');
  const [showQr, setShowQr] = useState<Record<string, boolean>>({});
  const [lastAutoRefreshAt, setLastAutoRefreshAt] = useState<number>(0);

  const fetchJob = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/jobs/${jobId}`);
      if (!res.ok) throw new Error('fetch error');
      const j = await res.json();
      setDoc(j);
    } catch (e: any) {
      setErr(e?.message || 'failed');
    }
  };

  useEffect(() => {
    fetchJob();
    const t = setInterval(fetchJob, 2000);
    return () => clearInterval(t);
  }, [jobId]);

  const refreshLinks = async () => {
    await fetch(`${API_BASE}/api/jobs/${jobId}/assets/refresh`, { method: 'POST' });
    await fetchJob();
  };

  const assets = useMemo(() => doc?.assets || {}, [doc]);
  const content = useMemo(() => (doc?.results?.content) || (doc?.result?.type==='content' && doc?.result) || {}, [doc]);
  const safety = useMemo(() => (doc?.results?.safety) || (doc?.result?.type==='safety' && doc?.result) || {}, [doc]);

  const copy = async (txt: string) => {
    try { await navigator.clipboard.writeText(txt); alert('URLをコピーしました'); } catch { alert('コピーに失敗しました'); }
  };

  const expiresIn = (url?: string) => {
    try {
      if (!url) return '';
      const u = new URL(url);
      const date = u.searchParams.get('X-Goog-Date'); // yyyymmddThhmmssZ
      const exp = parseInt(u.searchParams.get('X-Goog-Expires') || '0', 10);
      if (!date || !exp) return '';
      const yyyy = parseInt(date.slice(0, 4));
      const mm = parseInt(date.slice(4, 6)) - 1;
      const dd = parseInt(date.slice(6, 8));
      const hh = parseInt(date.slice(9, 11));
      const mi = parseInt(date.slice(11, 13));
      const ss = parseInt(date.slice(13, 15));
      const base = Date.UTC(yyyy, mm, dd, hh, mi, ss);
      const until = base + exp * 1000;
      const remain = Math.max(0, until - Date.now());
      const min = Math.floor(remain / 60000);
      return min > 0 ? `(expires in ~${min}m)` : '(expired)';
    } catch { return ''; }
  };

  // Auto refresh on expiry (cooldown: 60s)
  useEffect(() => {
    const now = Date.now();
    const cooldown = 60 * 1000;
    if (now - lastAutoRefreshAt < cooldown) return;
    const urls: string[] = [];
    [assets?.script_md_url, assets?.roles_csv_url, assets?.routes_json_url, content?.poster_prompts_url, content?.video_prompt_url, content?.video_shotlist_url]
      .forEach((u: any) => { if (typeof u === 'string') urls.push(u); });
    const hasExpired = urls.some(u => expiresIn(u) === '(expired)');
    if (hasExpired) {
      (async () => {
        try {
          await refreshLinks();
          setToast('署名 URL を自動再発行しました');
          setLastAutoRefreshAt(Date.now());
          setTimeout(() => setToast(''), 3000);
        } catch { /* noop */ }
      })();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assets?.script_md_url, assets?.roles_csv_url, assets?.routes_json_url, content?.poster_prompts_url, content?.video_prompt_url, content?.video_shotlist_url]);

  const toggleQr = (key: string) => setShowQr(prev => ({ ...prev, [key]: !prev[key] }));

  const qrSrc = (url: string) => `https://quickchart.io/qr?text=${encodeURIComponent(url)}&size=180`;

  const timeline = useMemo(() => {
    const order = ['plan','scenario','safety','content'];
    const completed: string[] = (doc?.completed_order || doc?.completed_tasks || []) as any;
    const current = (doc?.task || '') as string;
    return order.map(step => ({
      name: step,
      status: completed.includes(step) ? 'done' : (current === step ? 'running' : 'pending'),
    }));
  }, [doc]);

  return (
    <div>
      <h3>Job <code>{jobId}</code></h3>
      <div role="status" aria-live="polite" style={{ minHeight: 1 }}>
        {toast && <div style={{ position: 'sticky', top: 8, padding: '6px 10px', background: '#eefbf3', border: '1px solid #b7e4c7', color: '#2b8a3e', borderRadius: 6 }}>{toast}</div>}
        {err && <div role="alert" style={{ color: '#c33' }}>{err}</div>}
      </div>
      <div>Status: <b>{doc?.status || '...'}</b> / Task: <code>{doc?.task || ''}</code></div>
      <div>Completed: <code>{(doc?.completed_order||doc?.completed_tasks||[]).join(', ')}</code></div>
      <div style={{ display: 'flex', gap: 8, marginTop: 6, flexWrap: 'wrap' }} aria-label="progress timeline">
        {timeline.map((t) => (
          <span key={t.name} style={{
            padding: '4px 8px', borderRadius: 12, border: '1px solid #ddd',
            background: t.status==='done' ? '#e6f4ea' : (t.status==='running' ? '#fff3cd' : '#f6f6f6'),
            color: t.status==='done' ? '#1e7e34' : (t.status==='running' ? '#7a5d00' : '#555')
          }}>
            {t.name}
          </span>
        ))}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
        <h4 style={{ margin: 0 }}>Scenario assets</h4>
        <button onClick={refreshLinks} style={{ padding: '6px 10px' }}>リンク再発行</button>
      </div>
      <ul>
        {assets.script_md_url && (
          <li>
            <a target="_blank" href={assets.script_md_url} download>script.md</a>
            &nbsp;<small>{expiresIn(assets.script_md_url)}</small>
            &nbsp;<button onClick={() => copy(assets.script_md_url)}>コピー</button>
            &nbsp;<button aria-label="script.md のQRを表示" onClick={() => toggleQr('script_md_url')}>QR</button>
            {showQr['script_md_url'] && <div><img alt="script.md QR" src={qrSrc(assets.script_md_url)} /></div>}
          </li>
        )}
        {assets.roles_csv_url && (
          <li>
            <a target="_blank" href={assets.roles_csv_url} download>roles.csv</a>
            &nbsp;<small>{expiresIn(assets.roles_csv_url)}</small>
            &nbsp;<button onClick={() => copy(assets.roles_csv_url)}>コピー</button>
            &nbsp;<button aria-label="roles.csv のQRを表示" onClick={() => toggleQr('roles_csv_url')}>QR</button>
            {showQr['roles_csv_url'] && <div><img alt="roles.csv QR" src={qrSrc(assets.roles_csv_url)} /></div>}
          </li>
        )}
        {assets.routes_json_url && (
          <li>
            <a target="_blank" href={assets.routes_json_url} download>routes.json</a>
            &nbsp;<small>{expiresIn(assets.routes_json_url)}</small>
            &nbsp;<button onClick={() => copy(assets.routes_json_url)}>コピー</button>
            &nbsp;<button aria-label="routes.json のQRを表示" onClick={() => toggleQr('routes_json_url')}>QR</button>
            {showQr['routes_json_url'] && <div><img alt="routes.json QR" src={qrSrc(assets.routes_json_url)} /></div>}
          </li>
        )}
        {!assets.script_md_url && !assets.roles_csv_url && !assets.routes_json_url && <li>（なし）</li>}
      </ul>
      {assets.by_language && (
        <div>
          <h5>Scenario assets (per language)</h5>
          {Object.keys(assets.by_language || {}).map((lang: string) => {
            const it = (assets.by_language as any)[lang] || {};
            return (
              <div key={lang} style={{ marginBottom: 8 }}>
                <b>{lang}</b>
                <ul>
                  {it.script_md_url && (
                    <li>
                      <a target="_blank" href={it.script_md_url} download>{`script_${lang}.md`}</a>
                      &nbsp;<small>{expiresIn(it.script_md_url)}</small>
                      &nbsp;<button onClick={() => copy(it.script_md_url)}>コピー</button>
                      &nbsp;<button aria-label={`${lang} script QR`} onClick={() => toggleQr(`script_${lang}`)}>QR</button>
                      {showQr[`script_${lang}`] && <div><img alt={`script_${lang} QR`} src={qrSrc(it.script_md_url)} /></div>}
                    </li>
                  )}
                  {it.roles_csv_url && (
                    <li>
                      <a target="_blank" href={it.roles_csv_url} download>{`roles_${lang}.csv`}</a>
                      &nbsp;<small>{expiresIn(it.roles_csv_url)}</small>
                      &nbsp;<button onClick={() => copy(it.roles_csv_url)}>コピー</button>
                      &nbsp;<button aria-label={`${lang} roles QR`} onClick={() => toggleQr(`roles_${lang}`)}>QR</button>
                      {showQr[`roles_${lang}`] && <div><img alt={`roles_${lang} QR`} src={qrSrc(it.roles_csv_url)} /></div>}
                    </li>
                  )}
                </ul>
              </div>
            );
          })}
        </div>
      )}
      <h4>Content</h4>
      <ul>
        {content.poster_prompts_url && (
          <li>
            <a target="_blank" href={content.poster_prompts_url} download>poster_prompts.txt</a>
            &nbsp;<small>{expiresIn(content.poster_prompts_url)}</small>
            &nbsp;<button onClick={() => copy(content.poster_prompts_url)}>コピー</button>
            &nbsp;<button aria-label="poster_prompts のQRを表示" onClick={() => toggleQr('poster_prompts_url')}>QR</button>
            {showQr['poster_prompts_url'] && <div><img alt="poster_prompts QR" src={qrSrc(content.poster_prompts_url)} /></div>}
          </li>
        )}
        {content.video_prompt_url && (
          <li>
            <a target="_blank" href={content.video_prompt_url} download>video_prompt.txt</a>
            &nbsp;<small>{expiresIn(content.video_prompt_url)}</small>
            &nbsp;<button onClick={() => copy(content.video_prompt_url)}>コピー</button>
            &nbsp;<button aria-label="video_prompt のQRを表示" onClick={() => toggleQr('video_prompt_url')}>QR</button>
            {showQr['video_prompt_url'] && <div><img alt="video_prompt QR" src={qrSrc(content.video_prompt_url)} /></div>}
          </li>
        )}
        {content.video_shotlist_url && (
          <li>
            <a target="_blank" href={content.video_shotlist_url} download>video_shotlist.json</a>
            &nbsp;<small>{expiresIn(content.video_shotlist_url)}</small>
            &nbsp;<button onClick={() => copy(content.video_shotlist_url)}>コピー</button>
            &nbsp;<button aria-label="video_shotlist のQRを表示" onClick={() => toggleQr('video_shotlist_url')}>QR</button>
            {showQr['video_shotlist_url'] && <div><img alt="video_shotlist QR" src={qrSrc(content.video_shotlist_url)} /></div>}
          </li>
        )}
        {!content.poster_prompts_url && !content.video_prompt_url && !content.video_shotlist_url && <li>（なし）</li>}
      </ul>
      {content.by_language && (
        <div>
          <h5>Content (per language)</h5>
          {Object.keys(content.by_language || {}).map((lang: string) => {
            const it = (content.by_language as any)[lang] || {};
            return (
              <div key={lang} style={{ marginBottom: 8 }}>
                <b>{lang}</b>
                <ul>
                  {it.poster_prompts_url && (
                    <li>
                      <a target="_blank" href={it.poster_prompts_url} download>{`poster_prompts_${lang}.txt`}</a>
                      &nbsp;<small>{expiresIn(it.poster_prompts_url)}</small>
                      &nbsp;<button onClick={() => copy(it.poster_prompts_url)}>コピー</button>
                    </li>
                  )}
                  {it.video_prompt_url && (
                    <li>
                      <a target="_blank" href={it.video_prompt_url} download>{`video_prompt_${lang}.txt`}</a>
                      &nbsp;<small>{expiresIn(it.video_prompt_url)}</small>
                      &nbsp;<button onClick={() => copy(it.video_prompt_url)}>コピー</button>
                    </li>
                  )}
                  {it.video_shotlist_url && (
                    <li>
                      <a target="_blank" href={it.video_shotlist_url} download>{`video_shotlist_${lang}.json`}</a>
                      &nbsp;<small>{expiresIn(it.video_shotlist_url)}</small>
                      &nbsp;<button onClick={() => copy(it.video_shotlist_url)}>コピー</button>
                    </li>
                  )}
                </ul>
              </div>
            );
          })}
        </div>
      )}
      <h4>Safety issues</h4>
      <ul>
        {(safety?.issues||[]).map((it: any, i: number) => (
          <li key={i}>
            <b>[{it.severity||'n/a'}]</b> {it.issue||''}
            <br/>
            <small>fix: {it.fix||''}</small>
            {(it.kb_hits||[]).map((h: any, k: number) => (
              <div key={k} style={{ marginLeft: 12 }}>
                - <a target="_blank" href={h.link||h.url||'#'}>{h.title||h.id||'ref'}</a>
                <br/><small>{(h.snippet||'').replaceAll('<','&lt;')}</small>
              </div>
            ))}
          </li>
        ))}
        {!(safety?.issues||[]).length && <li>（なし）</li>}
      </ul>
      <h4>Raw</h4>
      <pre style={{ whiteSpace: 'pre-wrap' }}>{doc ? JSON.stringify(doc, null, 2) : '...'}</pre>
    </div>
  );
}
