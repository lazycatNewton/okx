// 删除当前项后优先下一项，再上一项；服务端返回的有效集合是最终依据。
export function nextActiveProduct(previous: string[], accepted: string[], active: string | null): string | null {
  if (active && accepted.includes(active)) return active
  const index = active ? previous.indexOf(active) : -1
  if (index >= 0) {
    const next = previous.slice(index + 1).find((id) => accepted.includes(id))
    if (next) return next
    const before = previous.slice(0, index).reverse().find((id) => accepted.includes(id))
    if (before) return before
  }
  return accepted[0] ?? null
}
