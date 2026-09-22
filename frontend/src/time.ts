import { TickMarkType, type Time } from 'lightweight-charts'

export const PROJECT_TIME_ZONE = 'America/New_York'

// 数据键必须是真实 UTC 时间，纽约时区仅作用于标签。把时间戳平移为“墙上时间”
// 会在秋季回拨时令两个 01:00 重合，导致去重吞掉整整一小时 K 线。
export function chartTimeInEt(timestampMs: number): number {
  if (!Number.isFinite(timestampMs)) throw new RangeError('invalid chart timestamp')
  return timestampMs / 1000
}

function chartTimeMs(time: Time): number {
  if (typeof time === 'number') return time * 1000
  if (typeof time === 'string') return Date.parse(time)
  return Date.UTC(time.year, time.month - 1, time.day)
}

const crosshairFormatter = new Intl.DateTimeFormat('en-US', {
  timeZone: PROJECT_TIME_ZONE, year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23', timeZoneName: 'short',
})
const tickOptions: [TickMarkType, Intl.DateTimeFormatOptions][] = [
  [TickMarkType.Year, { year: 'numeric' }],
  [TickMarkType.Month, { month: 'short' }],
  [TickMarkType.DayOfMonth, { month: '2-digit', day: '2-digit' }],
  [TickMarkType.Time, { hour: '2-digit', minute: '2-digit' }],
  [TickMarkType.TimeWithSeconds, { hour: '2-digit', minute: '2-digit', second: '2-digit' }],
]
const tickFormatters = new Map(tickOptions.map(([type, options]) => [type, new Intl.DateTimeFormat('en-US', {
  timeZone: PROJECT_TIME_ZONE, hourCycle: 'h23', ...options,
})]))

export function formatChartTime(time: Time): string {
  return crosshairFormatter.format(chartTimeMs(time))
}

export function formatChartTick(time: Time, type: TickMarkType): string {
  const ms = chartTimeMs(time)
  // 库按 UTC 给刻度分配“日/月/年”权重，UTC 午夜实际上是纽约前一天的晚上。
  // 非纽约午夜时仍显示时分，不能把 20:00 伪装成本产品的日界。
  const midnight = tickFormatters.get(TickMarkType.TimeWithSeconds)!.format(ms) === '00:00:00'
  const effectiveType = type < TickMarkType.Time && !midnight ? TickMarkType.Time : type
  return (tickFormatters.get(effectiveType) ?? crosshairFormatter).format(ms)
}

export function formatEt(timestampMs: number, options: Intl.DateTimeFormatOptions = {}): string {
  // Intl.DateTimeFormat 规定 dateStyle/timeStyle 不能与任何组件级选项
  // （含 timeZoneName）同时出现，否则抛出 RangeError；因此只在调用方没有
  // 使用 dateStyle/timeStyle 时才默认补充 timeZoneName。
  const usesStylePreset = 'dateStyle' in options || 'timeStyle' in options
  return new Intl.DateTimeFormat('en-US', {
    timeZone: PROJECT_TIME_ZONE,
    ...(usesStylePreset ? {} : { timeZoneName: 'short' as const }),
    ...options,
  }).format(new Date(timestampMs))
}
