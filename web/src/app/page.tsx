'use client';

import { useCallback, useMemo, useState } from 'react';

import { FACILITY_PRESETS, FacilityPreset, FacilityPresetCategory } from '../data/facilityPresets';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || '';

type ConstraintsState = {
  maxDurationMin?: number;
  limitedOutdoor?: boolean;
};

type ParticipantsState = {
  total: number;
  children: number;
  elderly: number;
  wheelchair: number;
};

function buildFacilityProfilePayload(preset: FacilityPreset | undefined) {
  if (!preset) {
    return undefined;
  }
  return {
    id: preset.id,
    label: preset.label,
    category: preset.category,
    kpi_targets: preset.profile.kpiTargets,
    acceptance_additions: preset.profile.acceptance,
    timeline_focus: preset.profile.timelineFocus,
    resource_focus: preset.profile.resourceFocus,
    description: preset.description,
  };
}

export default function Home() {
  const defaultPreset = FACILITY_PRESETS[0];
  const defaultForm = defaultPreset?.form;
  const [presetId, setPresetId] = useState<string>(defaultPreset?.id ?? 'custom');
  const [address, setAddress] = useState(defaultForm ? defaultForm.address : '');
  const [lat, setLat] = useState(defaultForm ? String(defaultForm.lat) : '');
  const [lng, setLng] = useState(defaultForm ? String(defaultForm.lng) : '');
  const [langs, setLangs] = useState(defaultForm ? defaultForm.languages.join(',') : 'ja,en');
  const [hazards, setHazards] = useState(defaultForm ? defaultForm.hazardTypes.join(',') : 'earthquake,fire');
  const [participants, setParticipants] = useState<ParticipantsState>(
    defaultForm
      ? {
          total: defaultForm.participants.total,
          children: defaultForm.participants.children,
          elderly: defaultForm.participants.elderly,
          wheelchair: defaultForm.participants.wheelchair,
        }
      : { total: 100, children: 10, elderly: 10, wheelchair: 2 }
  );
  const [constraints, setConstraints] = useState<ConstraintsState>(
    defaultForm?.constraints ?? { maxDurationMin: 45, limitedOutdoor: true }
  );
  const [posterStyle, setPosterStyle] = useState('低コントラスト写真風');
  const [brandColors, setBrandColors] = useState('緑');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [customPresets, setCustomPresets] = useState<FacilityPreset[]>([]);

  const [newPresetLabel, setNewPresetLabel] = useState('新規プリセット');
  const [newPresetCategory, setNewPresetCategory] = useState<FacilityPresetCategory>('community');
  const [newPresetDescription, setNewPresetDescription] = useState('');
  const [newAttendanceRate, setNewAttendanceRate] = useState('0.85');
  const [newAvgEvacSec, setNewAvgEvacSec] = useState('360');
  const [newQuizScore, setNewQuizScore] = useState('0.75');
  const [newAcceptance, setNewAcceptance] = useState('');
  const [newTimelineFocus, setNewTimelineFocus] = useState('');
  const [newResourceFocus, setNewResourceFocus] = useState('');
  const [presetMessage, setPresetMessage] = useState('');

  const allPresets = useMemo(() => [...FACILITY_PRESETS, ...customPresets], [customPresets]);
  const selectedPreset = useMemo<FacilityPreset | undefined>(() =>
    allPresets.find(preset => preset.id === presetId)
  , [allPresets, presetId]);
  const facilityProfilePayload = useMemo(() => buildFacilityProfilePayload(selectedPreset), [selectedPreset]);

  const applyPreset = useCallback((id: string) => {
    setPresetId(id);
    const preset = allPresets.find(p => p.id === id);
    if (!preset) {
      setParticipants({ total: 100, children: 10, elderly: 10, wheelchair: 2 });
      setConstraints({ maxDurationMin: 45, limitedOutdoor: true });
      setPosterStyle('低コントラスト写真風');
      setBrandColors('緑');
      return;
    }
    const data = preset.form;
    setAddress(data.address);
    setLat(String(data.lat));
    setLng(String(data.lng));
    setLangs(data.languages.join(','));
    setHazards(data.hazardTypes.join(','));
    setParticipants({
      total: data.participants.total,
      children: data.participants.children,
      elderly: data.participants.elderly,
      wheelchair: data.participants.wheelchair,
    });
    setConstraints(data.constraints ?? {});
    setPosterStyle('低コントラスト写真風');
    setBrandColors('緑');
  }, [allPresets]);

  const presetOptions = useMemo(
    () => [{ id: 'custom', label: 'カスタム入力' }, ...allPresets.map(p => ({ id: p.id, label: p.label }))],
    [allPresets]
  );

  const safeFloat = (value: string, fallback: number) => {
    const num = parseFloat(value);
    return Number.isFinite(num) ? num : fallback;
  };

  const slugify = (label: string) => {
    const base = label.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    return base || 'custom-preset';
  };

  const registerPreset = () => {
    try {
      const idBase = slugify(newPresetLabel);
      let id = idBase;
      let i = 1;
      while (allPresets.some(p => p.id === id)) {
        id = `${idBase}-${i++}`;
      }
      const languages = langs.split(',').map(s => s.trim()).filter(Boolean);
      const acceptanceList = newAcceptance.split('\n').map(s => s.trim()).filter(Boolean);
      const timelineList = newTimelineFocus.split('\n').map(s => s.trim()).filter(Boolean);
      const resourceList = newResourceFocus.split('\n').map(s => s.trim()).filter(Boolean);
      const newPreset: FacilityPreset = {
        id,
        label: newPresetLabel,
        category: newPresetCategory,
        description: newPresetDescription || 'カスタムプリセット',
        form: {
          address,
          lat: parseFloat(lat),
          lng: parseFloat(lng),
          languages,
          hazardTypes: hazards.split(',').map(s => s.trim()).filter(Boolean),
          participants: {
            total: participants.total,
            children: participants.children,
            elderly: participants.elderly,
            wheelchair: participants.wheelchair,
            languages,
          },
          constraints: {
            maxDurationMin: constraints.maxDurationMin,
            limitedOutdoor: constraints.limitedOutdoor,
          },
        },
        profile: {
          kpiTargets: {
            attendanceRate: safeFloat(newAttendanceRate, 0.8),
            avgEvacTimeSec: safeFloat(newAvgEvacSec, 360),
            quizScore: safeFloat(newQuizScore, 0.7),
          },
          acceptance: acceptanceList,
          timelineFocus: timelineList,
          resourceFocus: resourceList,
        },
      };
      setCustomPresets(prev => [...prev, newPreset]);
      setPresetId(id);
      setPresetMessage(`プリセット「${newPreset.label}」を追加しました`);
      setTimeout(() => setPresetMessage(''), 4000);
    } catch (err) {
      setPresetMessage('プリセット登録に失敗しました');
      setTimeout(() => setPresetMessage(''), 4000);
    }
  };

  const submit = async () => {
    try {
      setLoading(true);
      setError('');
      const hazardTypes = hazards
        .split(',')
        .map(s => s.trim())
        .filter(Boolean);
      const payload = {
        location: { address, lat: parseFloat(lat), lng: parseFloat(lng) },
        participants: {
          total: participants.total,
          children: participants.children,
          elderly: participants.elderly,
          wheelchair: participants.wheelchair,
          languages: langs.split(',').map(s => s.trim()).filter(Boolean),
        },
        hazard: {
          types: hazardTypes,
          drill_date: '2025-10-12',
          indoor: !constraints.limitedOutdoor,
          nighttime: false,
        },
        constraints: {
          max_duration_min: constraints.maxDurationMin,
          limited_outdoor: constraints.limitedOutdoor,
        },
        kb_refs: [],
        facility_profile: presetId !== 'custom' ? facilityProfilePayload : undefined,
        poster_style: posterStyle,
        brand_colors: brandColors.split(',').map(s => s.trim()).filter(Boolean),
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
        <label>ポスタースタイル
          <input
            value={posterStyle}
            onChange={e=>{ setPresetId('custom'); setPosterStyle(e.target.value); }}
            style={{ width: '100%', padding: 6 }}
            placeholder="例: 低コントラスト写真風"
          />
        </label>
        <label>ブランドカラー（カンマ区切り）
          <input
            value={brandColors}
            onChange={e=>{ setPresetId('custom'); setBrandColors(e.target.value); }}
            style={{ width: '100%', padding: 6 }}
            placeholder="例: 緑,#1E88E5"
          />
        </label>
        <div style={{ fontSize: 13, background: '#f5f5f5', padding: 10, borderRadius: 6 }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>参加者構成</div>
          <div>総数: {participants.total} 名 / 子ども: {participants.children} / 高齢者: {participants.elderly} / 車椅子: {participants.wheelchair}</div>
          {constraints.maxDurationMin && (
            <div>訓練目安時間: {constraints.maxDurationMin} 分 / 屋外制限: {constraints.limitedOutdoor ? 'あり' : 'なし'}</div>
          )}
        </div>
        <button onClick={submit} disabled={loading} style={{ padding: '8px 12px' }}>{loading ? '起動中...' : '開始'}</button>
        {error && (
          <div style={{ color: '#c33', whiteSpace: 'pre-wrap', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 12 }}>
            {error}
          </div>
        )}
      </div>
      {selectedPreset && (
        <section style={{ marginTop: 24, padding: 12, border: '1px solid #ddd', borderRadius: 8, maxWidth: 520 }}>
          <h4 style={{ margin: '0 0 8px', fontSize: 16 }}>{selectedPreset.label} 向け推奨 KPI / 導線</h4>
          <p style={{ margin: '0 0 8px', fontSize: 13 }}>{selectedPreset.description}</p>
          <dl style={{ margin: 0, fontSize: 13 }}>
            <dt style={{ fontWeight: 600 }}>KPI 目標値</dt>
            <dd style={{ margin: '0 0 6px 0' }}>
              出席率 {Math.round(selectedPreset.profile.kpiTargets.attendanceRate * 100)}% / 平均避難 {selectedPreset.profile.kpiTargets.avgEvacTimeSec} 秒 / クイズ達成率 {Math.round(selectedPreset.profile.kpiTargets.quizScore * 100)}%
            </dd>
            <dt style={{ fontWeight: 600 }}>受け入れ必須項目</dt>
            <dd style={{ margin: '0 0 6px 0' }}>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {selectedPreset.profile.acceptance.map(item => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </dd>
            <dt style={{ fontWeight: 600 }}>タイムライン重点</dt>
            <dd style={{ margin: '0 0 6px 0' }}>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {selectedPreset.profile.timelineFocus.map(item => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </dd>
            <dt style={{ fontWeight: 600 }}>重点資機材</dt>
            <dd style={{ margin: '0 0 6px 0' }}>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {selectedPreset.profile.resourceFocus.map(item => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </dd>
          </dl>
        </section>
      )}
      <section style={{ marginTop: 24, padding: 12, border: '1px solid #ddd', borderRadius: 8, maxWidth: 520 }}>
        <h4 style={{ margin: '0 0 8px' }}>プリセット登録</h4>
        <p style={{ fontSize: 13, margin: '0 0 8px' }}>現在の入力値をベースにプリセットを追加できます。リストへの追加のみで、ファイルへの保存は行いません。</p>
        <div style={{ display: 'grid', gap: 8 }}>
          <label>プリセット名
            <input value={newPresetLabel} onChange={e => setNewPresetLabel(e.target.value)} style={{ width: '100%', padding: 6 }} />
          </label>
          <label>カテゴリ
            <select value={newPresetCategory} onChange={e => setNewPresetCategory(e.target.value as FacilityPresetCategory)} style={{ width: '100%', padding: 6 }}>
              <option value="community">community</option>
              <option value="school">school</option>
              <option value="commercial">commercial</option>
            </select>
          </label>
          <label>説明
            <textarea value={newPresetDescription} onChange={e => setNewPresetDescription(e.target.value)} style={{ width: '100%', minHeight: 60, padding: 6 }} />
          </label>
          <div style={{ display: 'flex', gap: 8 }}>
            <label style={{ flex: 1 }}>出席率
              <input value={newAttendanceRate} onChange={e => setNewAttendanceRate(e.target.value)} style={{ width: '100%', padding: 6 }} />
            </label>
            <label style={{ flex: 1 }}>平均避難秒
              <input value={newAvgEvacSec} onChange={e => setNewAvgEvacSec(e.target.value)} style={{ width: '100%', padding: 6 }} />
            </label>
            <label style={{ flex: 1 }}>クイズ達成率
              <input value={newQuizScore} onChange={e => setNewQuizScore(e.target.value)} style={{ width: '100%', padding: 6 }} />
            </label>
          </div>
          <label>受け入れ必須項目（1 行 1 項目）
            <textarea value={newAcceptance} onChange={e => setNewAcceptance(e.target.value)} style={{ width: '100%', minHeight: 60, padding: 6 }} />
          </label>
          <label>タイムライン重点（1 行 1 項目）
            <textarea value={newTimelineFocus} onChange={e => setNewTimelineFocus(e.target.value)} style={{ width: '100%', minHeight: 60, padding: 6 }} />
          </label>
          <label>重点資機材（1 行 1 項目）
            <textarea value={newResourceFocus} onChange={e => setNewResourceFocus(e.target.value)} style={{ width: '100%', minHeight: 60, padding: 6 }} />
          </label>
          <button type="button" onClick={registerPreset} style={{ padding: '8px 12px' }}>プリセットに追加</button>
          {presetMessage && <div style={{ color: '#2b8a3e', fontSize: 12 }}>{presetMessage}</div>}
        </div>
      </section>
    </div>
  );
}
