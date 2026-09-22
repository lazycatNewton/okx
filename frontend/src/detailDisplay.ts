// 展示层按十进制字符串四舍五入，避免大额持仓量经过 Number 丢失精度。
export function formatDecimal(value: unknown, percent = false): string {
  if (value == null || value === '') return '—'
  const match = String(value).match(/^([+-]?)(\d+)(?:\.(\d*))?$/)
  if (!match) return '—'
  const [, sign, whole, fraction = ''] = match
  const places = percent ? 4 : 2
  const padded = fraction.padEnd(places + 1, '0')
  let scaled = BigInt(whole + padded.slice(0, places))
  if (padded[places] >= '5') scaled += 1n
  const digits = scaled.toString().padStart(3, '0')
  return `${sign === '-' && scaled !== 0n ? '-' : ''}${digits.slice(0, -2)}.${digits.slice(-2)}${percent ? '%' : ''}`
}

const enums: Record<string, Record<string, string>> = {
  instType: { SPOT: '现货', SWAP: '永续合约', FUTURES: '交割合约', OPTION: '期权', MARGIN: '杠杆现货', EVENTS: '事件合约' },
}
export function detailValue(key: string, value: unknown): string {
  if (value == null || value === '') return '—'
  const text = String(value)
  return enums[key]?.[text] ?? (enums[key] ? `未知状态（${text}）` : text)
}
