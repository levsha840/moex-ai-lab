import { IconSettings, IconLock, IconDatabase, IconBrain, IconShield, IconBell, IconCpu, IconTestPipe } from '@tabler/icons-react'
import { useTerminal } from '../context/TerminalContext'

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10, paddingBottom: 6, borderBottom: '1px solid var(--t-border)' }}>
        {icon}
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-text)', fontFamily: 'var(--t-font-mono)', letterSpacing: 0.6 }}>
          {title}
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
        {children}
      </div>
    </div>
  )
}

function Row({ label, value, mono, accent, dim }: { label: string; value: React.ReactNode; mono?: boolean; accent?: string; dim?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '5px 10px', background: 'var(--t-elevated)', borderRadius: 3, border: '1px solid var(--t-border)' }}>
      <span style={{ fontSize: 9, color: dim ? 'var(--t-text-3)' : 'var(--t-text-2)', fontFamily: 'var(--t-font-mono)' }}>{label}</span>
      <span style={{
        fontSize: 9, fontFamily: mono ? 'var(--t-font-mono)' : undefined,
        color: accent ?? (dim ? 'var(--t-text-3)' : 'var(--t-text)'), fontWeight: mono ? 600 : undefined,
      }}>
        {value}
      </span>
    </div>
  )
}

function BlockedRow({ label }: { label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '5px 10px', background: 'rgba(242,54,69,0.04)', borderRadius: 3, border: '1px solid rgba(242,54,69,0.15)' }}>
      <span style={{ fontSize: 9, color: 'var(--t-red)', fontFamily: 'var(--t-font-mono)' }}>{label}</span>
      <span style={{ fontSize: 8, color: 'var(--t-red)', fontFamily: 'var(--t-font-mono)', padding: '1px 5px', borderRadius: 2, background: 'rgba(242,54,69,0.1)', border: '1px solid rgba(242,54,69,0.2)', fontWeight: 700 }}>
        ЗАБЛОКИРОВАНО
      </span>
    </div>
  )
}

function PlannedRow({ label }: { label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '5px 10px', background: 'rgba(255,184,0,0.04)', borderRadius: 3, border: '1px solid rgba(255,184,0,0.12)' }}>
      <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>{label}</span>
      <span style={{ fontSize: 8, color: 'var(--t-amber)', fontFamily: 'var(--t-font-mono)', padding: '1px 5px', borderRadius: 2, background: 'rgba(255,184,0,0.08)', border: '1px solid rgba(255,184,0,0.15)' }}>
        ЗАПЛАНИРОВАНО
      </span>
    </div>
  )
}

export default function SettingsPage() {
  const { status } = useTerminal()

  const budgetUsed  = (status as any)?.budget_used  ?? null
  const budgetTotal = (status as any)?.budget_total ?? null
  const budgetPct   = budgetUsed != null && budgetTotal ? ((budgetUsed / budgetTotal) * 100).toFixed(1) : null

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ height: 44, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 16px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', gap: 10 }}>
        <IconSettings size={13} color="var(--t-text-3)" />
        <span style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)', letterSpacing: 1 }}>НАСТРОЙКИ</span>
        <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', padding: '1px 6px', background: 'var(--t-elevated)', border: '1px solid var(--t-border)', borderRadius: 2, marginLeft: 4 }}>
          ТОЛЬКО ДЛЯ ЧТЕНИЯ
        </span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', maxWidth: 760 }}>

        {/* 1 ── Данные и исследование */}
        <Section icon={<IconDatabase size={11} color="var(--t-text-3)" />} title="ДАННЫЕ И ИССЛЕДОВАНИЕ">
          <Row label="Режим"        value={(status as any)?.mode ?? 'research'} mono accent="var(--t-cyan)" />
          <Row label="Путь данных"  value={(status as any)?.data_path ?? 'data/'} mono />
          <Row label="Всего сессий" value={(status as any)?.total_sessions ?? '—'} mono />
          <Row label="Гипотез"      value={(status as any)?.total_hypotheses ?? '—'} mono />
          <Row label="Отчётов"      value={(status as any)?.total_reports ?? '—'} mono />
        </Section>

        {/* 2 ── Бюджет исследования */}
        <Section icon={<IconTestPipe size={11} color="var(--t-text-3)" />} title="БЮДЖЕТ ИССЛЕДОВАНИЯ">
          {budgetTotal != null ? (
            <>
              <Row label="Использовано" value={`${budgetUsed ?? 0} / ${budgetTotal} запусков`} mono />
              {budgetPct != null && (
                <>
                  <div style={{ height: 4, background: 'var(--t-elevated)', borderRadius: 2, overflow: 'hidden', border: '1px solid var(--t-border)' }}>
                    <div style={{
                      height: '100%', width: `${budgetPct}%`,
                      background: parseFloat(budgetPct) > 80 ? 'var(--t-red)' : parseFloat(budgetPct) > 50 ? 'var(--t-amber)' : 'var(--t-green)',
                      borderRadius: 2, transition: 'width 0.3s',
                    }} />
                  </div>
                  <Row label="Процент использован" value={`${budgetPct}%`} mono
                    accent={parseFloat(budgetPct) > 80 ? 'var(--t-red)' : parseFloat(budgetPct) > 50 ? 'var(--t-amber)' : 'var(--t-green)'} />
                </>
              )}
            </>
          ) : (
            <Row label="Бюджет" value="Не установлен" dim />
          )}
          <Row label="Кандидаты для Paper" value={(status as any)?.paper_candidates ?? 0} mono />
        </Section>

        {/* 3 ── Бумажная торговля */}
        <Section icon={<IconTestPipe size={11} color="var(--t-text-3)" />} title="БУМАЖНАЯ ТОРГОВЛЯ (PAPER TRADING)">
          <Row
            label="Статус"
            value={(status as any)?.paper_candidates ? 'Есть кандидаты' : 'Нет одобренных кандидатов'}
            accent={(status as any)?.paper_candidates ? 'var(--t-amber)' : 'var(--t-text-3)'}
          />
          <Row label="Кандидаты APPROVED_FOR_PAPER" value={(status as any)?.paper_candidates ?? 0} mono />
          <Row label="Тип исполнения" value="Симуляция без реальных ордеров" dim />
          <Row label="Биржа" value="MOEX · TQBR (планируется)" dim />
        </Section>

        {/* 4 ── Sandbox */}
        <Section icon={<IconShield size={11} color="var(--t-text-3)" />} title="БРОКЕР · SANDBOX">
          <PlannedRow label="Брокер" />
          <PlannedRow label="API ключ (Sandbox)" />
          <PlannedRow label="Счёт Sandbox" />
          <PlannedRow label="Тестовый баланс" />
        </Section>

        {/* 5 ── Live Trading — BLOCKED */}
        <Section icon={<IconLock size={11} color="var(--t-red)" />} title="LIVE TRADING">
          <div style={{ padding: '10px 12px', background: 'rgba(242,54,69,0.05)', borderRadius: 4, border: '1px solid rgba(242,54,69,0.2)', marginBottom: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
              <IconLock size={11} color="var(--t-red)" />
              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-red)', fontFamily: 'var(--t-font-mono)' }}>
                LIVE TRADING ЗАБЛОКИРОВАН
              </span>
            </div>
            <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', lineHeight: 1.6 }}>
              Защита от случайного включения реальных торгов. Управляется через SafetyGuard на стороне сервера. Изменение через UI невозможно.
            </span>
          </div>
          <BlockedRow label="Исполнение реальных ордеров" />
          <BlockedRow label="Подключение Live-брокера" />
          <BlockedRow label="Снятие / пополнение средств" />
        </Section>

        {/* 6 ── AI и агенты */}
        <Section icon={<IconBrain size={11} color="var(--t-text-3)" />} title="AI · АГЕНТЫ">
          <Row label="ChiefScientist"  value="Активен · 7 правил" accent="var(--t-green)" />
          <Row label="KnowledgeAgent"  value="Активен · KB graph" accent="var(--t-green)" />
          <Row label="RegimeDetection" value="Активен" accent="var(--t-green)" />
          <Row label="CorrelationAgent" value="Активен" accent="var(--t-green)" />
          <Row label="MacroAgent"      value="Активен · IMOEX / USDRUB / RGBI" accent="var(--t-green)" />
          <Row label="LLM / внешние модели" value="Не используются" dim />
          <Row label="Детерминированный режим" value="Да · без случайности" accent="var(--t-cyan)" />
        </Section>

        {/* 7 ── GPU */}
        <Section icon={<IconCpu size={11} color="var(--t-text-3)" />} title="GPU / ВЫЧИСЛЕНИЯ">
          <Row label="Текущий режим" value="CPU · Python стандартные библиотеки" dim />
          <PlannedRow label="GPU-ускорение (CUDA / ROCm)" />
          <PlannedRow label="Параллельные эксперименты" />
        </Section>

        {/* 8 ── Уведомления */}
        <Section icon={<IconBell size={11} color="var(--t-text-3)" />} title="УВЕДОМЛЕНИЯ">
          <Row label="Статус" value="Не настроены" dim />
          <PlannedRow label="Email уведомления" />
          <PlannedRow label="Telegram бот" />
          <PlannedRow label="Webhook" />
        </Section>

        {/* Footer */}
        <div style={{ marginTop: 8, padding: '10px 12px', background: 'rgba(242,54,69,0.04)', borderRadius: 4, border: '1px solid rgba(242,54,69,0.12)', display: 'flex', gap: 8, alignItems: 'flex-start' }}>
          <IconShield size={12} color="var(--t-red)" style={{ flexShrink: 0, marginTop: 1 }} />
          <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', lineHeight: 1.7 }}>
            Все настройки доступны только для просмотра. Конфигурация управляется через файлы среды и SafetyGuard на сервере. Live Trading защищён от включения через UI на уровне архитектуры.
          </span>
        </div>
      </div>
    </div>
  )
}
