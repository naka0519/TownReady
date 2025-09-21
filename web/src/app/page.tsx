'use client';

import { useMemo, useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || '';

type Preset = {
  id: string;
  label: string;
  data?: {
    address: string;
    lat: number;
    lng: number;
    languages: string[];
    hazards: string[];
  };
};

const PRESETS: Preset[] = [
  { id: 'custom', label: 'カスタム入力' },
  {
    id: 'community-center',
    label: '地域センター',
    data: {
      address: '神奈川県横浜市戸塚区上倉田町８８４−１',
      lat: 35.3985,
      lng: 139.5372,
      languages: ['ja', 'en'],
      hazards: ['earthquake', 'flood']
    }
  },
  {
    id: 'river-hospital',
    label: '川沿い病院',
    data: {
      address: '神奈川県横浜市戸塚区吉田町５７９−１',
      lat: 35.4053,
      lng: 139.5378,
      languages: ['ja', 'en'],
      hazards: ['earthquake', 'fire']
    }
  }
];

export default function Home() {
  const defaultPreset = PRESETS.find(p => p.id === 'community-center') ?? PRESETS[0];
  const initialData = defaultPreset.data;
  const [presetId, setPresetId] = useState<string>(defaultPreset.id);
  const [address, setAddress] = useState(initialData ? initialData.address : '');
  const [lat, setLat] = useState(initialData ? String(initialData.lat) : '');
  const [lng, setLng] = useState(initialData ? String(initialData.lng) : '');
  const [langs, setLangs] = useState(initialData ? initialData.languages.join(',') : 'ja,en');
  const [hazards, setHazards] = useState(initialData ? initialData.hazards.join(',') : 'earthquake,fire');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const applyPreset = (id: string) => {
    setPresetId(id);
    const preset = PRESETS.find(p => p.id === id);
    if (!preset || !preset.data) {
      return;
    }
    const data = preset.data;
    setAddress(data.address);
    setLat(String(data.lat));
    setLng(String(data.lng));
    setLangs(data.languages.join(','));
    setHazards(data.hazards.join(','));
  };

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
  const presetOptions = useMemo(() => PRESETS, []);
  return (
    <div>
      <h3>新規ジョブの開始</h3>
      <p>API: <code>{apiLabel}</code></p>
      <div style={{ display: 'grid', gap: 8, maxWidth: 420 }}>
        <label>プリセット
          <select
            value={presetId}
            onChange={e => applyPreset(e.target.value)}
            style={{ width: '100%', padding: 6 }}
          >
            {presetOptions.map(preset => (
              <option key={preset.id} value={preset.id}>{preset.label}</option>
            ))}
          </select>
        </label>
        <label>住所
          <input
            value={address}
            onChange={e=>{ setPresetId('custom'); setAddress(e.target.value); }}
            style={{ width: '100%', padding: 6 }}
          />
        </label>
        <div style={{ display: 'flex', gap: 8 }}>
          <label style={{ flex: 1 }}>lat
            <input
              value={lat}
              onChange={e=>{ setPresetId('custom'); setLat(e.target.value); }}
              style={{ width: '100%', padding: 6 }}
            />
          </label>
          <label style={{ flex: 1 }}>lng
            <input
              value={lng}
              onChange={e=>{ setPresetId('custom'); setLng(e.target.value); }}
              style={{ width: '100%', padding: 6 }}
            />
          </label>
        </div>
        <label>言語（カンマ区切り）
          <input
            value={langs}
            onChange={e=>{ setPresetId('custom'); setLangs(e.target.value); }}
            style={{ width: '100%', padding: 6 }}
          />
        </label>
        <label>ハザード（カンマ区切り）
          <input
            value={hazards}
            onChange={e=>{ setPresetId('custom'); setHazards(e.target.value); }}
            style={{ width: '100%', padding: 6 }}
          />
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
