'use client';

import { useEffect, useMemo, useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || '';

type JobDoc = any;

export default function JobPage(props: { params: { id: string } }) {
  const jobId = props.params.id;
  const [doc, setDoc] = useState<JobDoc | null>(null);
  const [err, setErr] = useState('');

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

  return (
    <div>
      <h3>Job <code>{jobId}</code></h3>
      {err && <div style={{ color: '#c33' }}>{err}</div>}
      <div>Status: <b>{doc?.status || '...'}</b> / Task: <code>{doc?.task || ''}</code></div>
      <div>Completed: <code>{(doc?.completed_order||doc?.completed_tasks||[]).join(', ')}</code></div>
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
          </li>
        )}
        {assets.roles_csv_url && (
          <li>
            <a target="_blank" href={assets.roles_csv_url} download>roles.csv</a>
            &nbsp;<small>{expiresIn(assets.roles_csv_url)}</small>
            &nbsp;<button onClick={() => copy(assets.roles_csv_url)}>コピー</button>
          </li>
        )}
        {assets.routes_json_url && (
          <li>
            <a target="_blank" href={assets.routes_json_url} download>routes.json</a>
            &nbsp;<small>{expiresIn(assets.routes_json_url)}</small>
            &nbsp;<button onClick={() => copy(assets.routes_json_url)}>コピー</button>
          </li>
        )}
        {!assets.script_md_url && !assets.roles_csv_url && !assets.routes_json_url && <li>（なし）</li>}
      </ul>
      <h4>Content</h4>
      <ul>
        {content.poster_prompts_url && (
          <li>
            <a target="_blank" href={content.poster_prompts_url} download>poster_prompts.txt</a>
            &nbsp;<small>{expiresIn(content.poster_prompts_url)}</small>
            &nbsp;<button onClick={() => copy(content.poster_prompts_url)}>コピー</button>
          </li>
        )}
        {content.video_prompt_url && (
          <li>
            <a target="_blank" href={content.video_prompt_url} download>video_prompt.txt</a>
            &nbsp;<small>{expiresIn(content.video_prompt_url)}</small>
            &nbsp;<button onClick={() => copy(content.video_prompt_url)}>コピー</button>
          </li>
        )}
        {content.video_shotlist_url && (
          <li>
            <a target="_blank" href={content.video_shotlist_url} download>video_shotlist.json</a>
            &nbsp;<small>{expiresIn(content.video_shotlist_url)}</small>
            &nbsp;<button onClick={() => copy(content.video_shotlist_url)}>コピー</button>
          </li>
        )}
        {!content.poster_prompts_url && !content.video_prompt_url && !content.video_shotlist_url && <li>（なし）</li>}
      </ul>
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
