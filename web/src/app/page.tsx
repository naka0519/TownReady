'use client';

import { useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || '';

export default function Home() {
  const [address, setAddress] = useState('横浜市戸塚区戸塚町');
  const [lat, setLat] = useState('35.401');
  const [lng, setLng] = useState('139.532');
  const [langs, setLangs] = useState('ja,en');
  const [hazards, setHazards] = useState('earthquake,fire');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    try {
      setLoading(true);
      setError('');
      const payload = {
        location: { address, lat: parseFloat(lat), lng: parseFloat(lng) },
        participants: { total: 100, children: 10, elderly: 10, wheelchair: 2, languages: langs.split(',').map(s=>s.trim()).filter(Boolean) },
        hazard: { types: hazards.split(',').map(s=>s.trim()).filter(Boolean), drill_date: '2025-10-12', indoor: true, nighttime: false },
        constraints: { max_duration_min: 45, limited_outdoor: true },
        kb_refs: []
      };
      const endpoint = API_BASE ? `${API_BASE}/api/generate/plan` : `/api/generate/plan`;
      const res = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`API ${res.status}: ${text?.slice(0, 300)}`);
      }
      const j = await res.json();
      window.location.href = `/jobs/${j.job_id}`;
    } catch (e: any) {
      setError(e?.message || 'failed');
    } finally {
      setLoading(false);
    }
  };

  const apiLabel = API_BASE ? API_BASE : '(via Next proxy)';
  return (
    <div>
      <h3>新規ジョブの開始</h3>
      <p>API: <code>{apiLabel}</code></p>
      <div style={{ display: 'grid', gap: 8, maxWidth: 420 }}>
        <label>住所
          <input value={address} onChange={e=>setAddress(e.target.value)} style={{ width: '100%', padding: 6 }} />
        </label>
        <div style={{ display: 'flex', gap: 8 }}>
          <label style={{ flex: 1 }}>lat
            <input value={lat} onChange={e=>setLat(e.target.value)} style={{ width: '100%', padding: 6 }} />
          </label>
          <label style={{ flex: 1 }}>lng
            <input value={lng} onChange={e=>setLng(e.target.value)} style={{ width: '100%', padding: 6 }} />
          </label>
        </div>
        <label>言語（カンマ区切り）
          <input value={langs} onChange={e=>setLangs(e.target.value)} style={{ width: '100%', padding: 6 }} />
        </label>
        <label>ハザード（カンマ区切り）
          <input value={hazards} onChange={e=>setHazards(e.target.value)} style={{ width: '100%', padding: 6 }} />
        </label>
        <button onClick={submit} disabled={loading} style={{ padding: '8px 12px' }}>{loading ? '起動中...' : '開始'}</button>
        {error && (
          <div style={{ color: '#c33', whiteSpace: 'pre-wrap', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 12 }}>
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
