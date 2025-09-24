export type FacilityPresetCategory = 'community' | 'school' | 'commercial';

export interface FacilityPreset {
  id: string;
  label: string;
  category: FacilityPresetCategory;
  description: string;
  form: {
    address: string;
    lat: number;
    lng: number;
    languages: string[];
    hazardTypes: string[];
    participants: {
      total: number;
      children: number;
      elderly: number;
      wheelchair: number;
      languages: string[];
    };
    constraints?: {
      maxDurationMin?: number;
      limitedOutdoor?: boolean;
    };
  };
  profile: {
    kpiTargets: {
      attendanceRate: number;
      avgEvacTimeSec: number;
      quizScore: number;
    };
    acceptance: string[];
    timelineFocus: string[];
    resourceFocus: string[];
  };
}

export const FACILITY_PRESETS: FacilityPreset[] = [
  {
    id: 'community-center',
    label: '自治会館（戸塚地区センター）',
    category: 'community',
    description: '高齢者比率が高い自治会活動拠点。止水板配置と要配慮者支援の即応が求められる。',
    form: {
      address: '神奈川県横浜市戸塚区吉田町１０４−１ 戸塚地区センター',
      lat: 35.4011,
      lng: 139.5345,
      languages: ['ja', 'en', 'zh'],
      hazardTypes: ['flood', 'landslide'],
      participants: {
        total: 80,
        children: 5,
        elderly: 28,
        wheelchair: 4,
        languages: ['ja', 'en', 'zh'],
      },
      constraints: {
        maxDurationMin: 45,
        limitedOutdoor: true,
      },
    },
    profile: {
      kpiTargets: {
        attendanceRate: 0.85,
        avgEvacTimeSec: 420,
        quizScore: 0.7,
      },
      acceptance: [
        '高齢者サポート班と介助導線の配置',
        '自治会 LINE・無線の起動確認',
      ],
      timelineFocus: [
        '集合時に要配慮者と介助担当をペアリングする',
        '地区センター地下の浸水確認と止水板設置',
      ],
      resourceFocus: [
        '自治会名簿と連絡網の最新化',
        '多言語案内板とバリアフリー簡易スロープ',
      ],
    },
  },
  {
    id: 'municipal-school',
    label: '横浜市立戸塚小学校',
    category: 'school',
    description: '児童の引き渡し導線と学年別役割が必須となる市立小学校。',
    form: {
      address: '神奈川県横浜市戸塚区戸塚町１３２',
      lat: 35.3939,
      lng: 139.5364,
      languages: ['ja'],
      hazardTypes: ['earthquake', 'fire'],
      participants: {
        total: 450,
        children: 400,
        elderly: 0,
        wheelchair: 6,
        languages: ['ja'],
      },
      constraints: {
        maxDurationMin: 35,
        limitedOutdoor: false,
      },
    },
    profile: {
      kpiTargets: {
        attendanceRate: 0.95,
        avgEvacTimeSec: 240,
        quizScore: 0.85,
      },
      acceptance: [
        '学年別引率班と保護者引き渡し動線の整備',
        '校内放送・緊急メールの試験送信',
      ],
      timelineFocus: [
        '開会直後に防災倉庫とヘルメットの受け渡し',
        '避難先で学級ごとに児童点呼と保護者連絡を実施',
      ],
      resourceFocus: [
        '学級別名簿と保護者連絡カード',
        '校内放送設備と防災倉庫キー',
      ],
    },
  },
  {
    id: 'commercial-complex',
    label: '商業施設（戸塚モディ）',
    category: 'commercial',
    description: '駅直結の複合商業施設。営業時間帯でもテナント一斉避難と来客誘導が必要。',
    form: {
      address: '神奈川県横浜市戸塚区戸塚町１０ 戸塚モディ',
      lat: 35.4009,
      lng: 139.5333,
      languages: ['ja', 'en', 'ko'],
      hazardTypes: ['earthquake', 'flood', 'fire'],
      participants: {
        total: 180,
        children: 10,
        elderly: 12,
        wheelchair: 3,
        languages: ['ja', 'en', 'ko'],
      },
      constraints: {
        maxDurationMin: 40,
        limitedOutdoor: false,
      },
    },
    profile: {
      kpiTargets: {
        attendanceRate: 0.9,
        avgEvacTimeSec: 300,
        quizScore: 0.8,
      },
      acceptance: [
        'テナント責任者の一斉通報と避難開始承認フロー',
        '帰宅困難者受け入れスペースの事前確保',
      ],
      timelineFocus: [
        '館内放送とエレベーター停止操作を初動で実施',
        '地下店舗の浸水確認後に高層階へ誘導',
      ],
      resourceFocus: [
        'テナント連絡網と避難誘導サイン',
        '帰宅困難者用の簡易マット・飲料備蓄',
      ],
    },
  },
];

export function getPresetById(id: string | undefined | null): FacilityPreset | undefined {
  if (!id) {
    return undefined;
  }
  return FACILITY_PRESETS.find((preset) => preset.id === id);
}
