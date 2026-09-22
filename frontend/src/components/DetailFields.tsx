import { detailLabel, detailValue } from '../detailDisplay'
import { formatEt } from '../time'

export function DetailFields({ data }: { data: Record<string, unknown> }) {
  return <dl className="detail-grid">{Object.entries(data).map(([key, value]) => (
    <div key={key}>
      <dt>{detailLabel(key)}</dt>
      <dd>{Array.isArray(value) ? value.map((entry, index) => (
        <div key={index}>{entry && typeof entry === 'object'
          ? <DetailFields data={entry as Record<string, unknown>} />
          : detailValue(key, entry)}</div>
      )) : value && typeof value === 'object'
        ? <DetailFields data={value as Record<string, unknown>} />
        : (key === 'ts' || key === 'maxBalTs') && value
          ? formatEt(Number(value), { dateStyle: 'medium', timeStyle: 'medium' })
          : detailValue(key, value)}</dd>
    </div>
  ))}</dl>
}
