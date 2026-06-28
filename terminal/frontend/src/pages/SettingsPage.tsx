import { IconLock, IconShield, IconServer, IconDatabase, IconPalette } from '@tabler/icons-react'
import { useTerminal } from '../context/TerminalContext'

function SH({ label }: { label: string }) {
  return (
    <div style={{ padding: '10px 16px 4px', fontSize: 9, letterSpacing: 0.8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', fontWeight: 700 }}>
      {label}
    </div>
  )
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', padding: '8px 16px', borderBottom: '1px solid rgba(255,255,255,0.04)', gap: 12 }}>
      <span style={{ fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', width: 220, flexShrink: 0 }}>{label}</span>
      <span style={{ fontSize: 10, color: 'var(--t-text)', fontFamily: 'var(--t-font-mono)' }}>{value}</span>
    </div>
  )
}

export default function SettingsPage() {
  const { status, reports } = useTerminal()

  const budgetUsed  = (status as any)?.research_budget?.used  ?? 0
  const budgetTotal = (status as any)?.research_budget?.total ?? 100
  const sessions    = (status as any)?.research?.sessions     ?? 0
  const hRegistered = (status as any)?.hypotheses?.registered ?? 0
  const hTested     = (status as any)?.hypotheses?.tested     ?? 0
  const paperCands  = (status as any)?.candidates?.approved_for_paper ?? 0

  const tickers = [...new Set(reports.map(r => r.ticker))].join(', ') || '—'

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ height: 44, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 16px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', gap: 10 }}>
        <IconServer size={13} color="var(--t-text-3)" />
        <span style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)', letterSpacing: 1 }}>НАСТРОЙКИ</span>
        <span style={{ fontSize: 9, padding: '2px 7px', borderRadius: 2, background: 'rgba(255,184,0,0.12)', color: 'var(--t-amber)', fontFamily: 'var(--t-font-mono)', border: '1px solid rgba(255,184,0,0.25)', fontWeight: 700, letterSpacing: 0.5 }}>
          ТОЛЬКО ДЛЯ ЧТЕНИЯ
        </span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        <SH label="ДАННЫЕ И ИССЛЕДОВАНИЯ" />
        <Row label="Путь к данным" value="data/" />
        <Row label="Вселенная" value="P1 (MOEX Blue Chips)" />
        <Row label="Инструменты в работе" value={tickers} />
        <Row label="Таймфрейм по умолчанию" value="1H" />
        <Row label="Бюджет исследований" value={`${budgetUsed} / ${budgetTotal} запусков`} />
        <Row label="Сессий исследования" value={String(sessions)} />
        <Row label="Гипотез зарегистрировано" value={String(hRegistered)} />
        <Row label="Гипотез протестировано" value={String(hTested)} />
        <Row label="Кандидатов для Paper Trading" value={String(paperCands)} />

        <SH label="РЕЖИМ ТОРГОВЛИ" />
        <Row label="Режим системы" value={<span style={{ color: 'var(--t-cyan)' }}>Исследование (Research)</span>} />
        <Row label="Бумажная торговля" value={<span style={{ color: 'var(--t-amber)' }}>Ожидает кандидатов</span>} />
        <Row label="Sandbox Execute" value={<span style={{ color: 'var(--t-text-3)' }}>Отключён</span>} />
        <Row label="Live Trading" value={
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--t-red)' }}>
            <IconLock size={10} />
            ЗАБЛОКИРОВАНО — защита от реальных сделок
          </span>
        } />

        <SH label="ИНТЕРФЕЙС" />
        <Row label="Тема" value="Тёмная (Dark Terminal)" />
        <Row label="Язык" value="Русский (RU)" />
        <Row label="Часовой пояс" value="МСК (Europe/Moscow)" />
        <Row label="Версия интерфейса" value="v2.4" />

        <div style={{ margin: '16px', padding: 12, background: 'rgba(242,54,69,0.07)', borderRadius: 4, border: '1px solid rgba(242,54,69,0.2)', display: 'flex', gap: 10, alignItems: 'flex-start' }}>
          <IconShield size={14} color="var(--t-red)" style={{ flexShrink: 0, marginTop: 1 }} />
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-red)', fontFamily: 'var(--t-font-mono)', marginBottom: 5, letterSpacing: 0.5 }}>
              ЗАЩИТА АКТИВИРОВАНА
            </div>
            <div style={{ fontSize: 9, color: 'var(--t-text-3)', lineHeight: 1.7, fontFamily: 'var(--t-font-mono)' }}>
              Система работает в режиме исследования. Live Trading заблокирован на уровне кода и не может быть включён из интерфейса.
              Для изменения режима необходимо ручное вмешательство разработчика с явным изменением конфигурации системы.
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
