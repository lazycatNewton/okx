// 中枢矩形 + 笔连线的自定义绘制层（Lightweight Charts v5 ISeriesPrimitive）。
// 分型/背驰用原生 createSeriesMarkers 单独处理，见 CandleChart.tsx。
import type { CanvasRenderingTarget2D } from 'fancy-canvas'
import type {
  Coordinate,
  IChartApiBase,
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesApi,
  ISeriesPrimitive,
  SeriesAttachedParameter,
  SeriesType,
  Time,
} from 'lightweight-charts'
import { buildZhongshuPriceLabels } from './chartDisplay'

export interface ChanZhongshuBox {
  startTime: Time
  endTime: Time
  zg: number
  zd: number
}

export interface ChanStrokeSegment {
  time: Time
  price: number
}

interface RectPixels {
  x1: number
  x2: number
  y1: number
  y2: number
  zg: number
  zd: number
}

class ZhongshuPaneRenderer implements IPrimitivePaneRenderer {
  private readonly boxes: RectPixels[]

  constructor(boxes: RectPixels[]) {
    this.boxes = boxes
  }

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace(({ context, horizontalPixelRatio, verticalPixelRatio }) => {
      context.save()
      context.fillStyle = 'rgba(234, 179, 8, 0.18)' // 半透明浅黄色
      context.strokeStyle = 'rgba(234, 179, 8, 0.6)'
      context.lineWidth = 1
      for (const box of this.boxes) {
        const x1 = box.x1 * horizontalPixelRatio
        const x2 = box.x2 * horizontalPixelRatio
        const y1 = box.y1 * verticalPixelRatio
        const y2 = box.y2 * verticalPixelRatio
        context.fillRect(x1, y1, x2 - x1, y2 - y1)
        context.strokeRect(x1, y1, x2 - x1, y2 - y1)

        context.font = `${11 * verticalPixelRatio}px system-ui, sans-serif`
        context.textBaseline = 'middle'
        for (const label of buildZhongshuPriceLabels(box)) {
          const textWidth = context.measureText(label.text).width
          const paddingX = 4 * horizontalPixelRatio
          const labelHeight = 16 * verticalPixelRatio
          const labelWidth = textWidth + paddingX * 2
          const labelX = Math.max(0, x2 - labelWidth)
          const boundaryY = label.boundary === 'ZG' ? y1 : y2
          const labelY = label.boundary === 'ZG'
            ? boundaryY - labelHeight
            : boundaryY

          context.fillStyle = 'rgba(161, 98, 7, 0.92)'
          context.fillRect(labelX, labelY, labelWidth, labelHeight)
          context.fillStyle = '#fef3c7'
          context.fillText(label.text, labelX + paddingX, labelY + labelHeight / 2)
          context.fillStyle = 'rgba(234, 179, 8, 0.18)'
        }
      }
      context.restore()
    })
  }
}

class ZhongshuPaneView implements IPrimitivePaneView {
  private readonly source: ChanZhongshuPrimitive

  constructor(source: ChanZhongshuPrimitive) {
    this.source = source
  }

  renderer(): IPrimitivePaneRenderer | null {
    const chart = this.source.chart
    const series = this.source.series
    if (!chart || !series) return null
    const boxes: RectPixels[] = []
    for (const box of this.source.boxes) {
      const x1 = chart.timeScale().timeToCoordinate(box.startTime)
      const x2 = chart.timeScale().timeToCoordinate(box.endTime)
      const y1 = series.priceToCoordinate(box.zg)
      const y2 = series.priceToCoordinate(box.zd)
      if (x1 === null || x2 === null || y1 === null || y2 === null) continue
      boxes.push({ x1, x2, y1, y2, zg: box.zg, zd: box.zd })
    }
    return new ZhongshuPaneRenderer(boxes)
  }
}

/** 中枢矩形绘制层：跨越中枢起止时间、上下沿为 ZG/ZD 的半透明矩形。 */
export class ChanZhongshuPrimitive implements ISeriesPrimitive<Time> {
  chart: IChartApiBase<Time> | null = null
  series: ISeriesApi<SeriesType, Time> | null = null
  boxes: ChanZhongshuBox[] = []
  private readonly _paneViews: ZhongshuPaneView[]

  constructor() {
    this._paneViews = [new ZhongshuPaneView(this)]
  }

  attached(param: SeriesAttachedParameter<Time>): void {
    this.chart = param.chart
    this.series = param.series
  }

  detached(): void {
    this.chart = null
    this.series = null
  }

  setBoxes(boxes: ChanZhongshuBox[]): void {
    this.boxes = boxes
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this._paneViews
  }
}

interface PointPixels {
  x: number
  y: number
}

class StrokePaneRenderer implements IPrimitivePaneRenderer {
  private readonly points: PointPixels[]

  constructor(points: PointPixels[]) {
    this.points = points
  }

  draw(target: CanvasRenderingTarget2D): void {
    if (this.points.length < 2) return
    target.useBitmapCoordinateSpace(({ context, horizontalPixelRatio, verticalPixelRatio }) => {
      context.save()
      context.strokeStyle = 'rgba(148, 163, 184, 0.85)' // 中性灰蓝色，不与蜡烛图涨跌色冲突
      context.lineWidth = 1.5
      context.beginPath()
      this.points.forEach((point, index) => {
        const x = point.x * horizontalPixelRatio
        const y = point.y * verticalPixelRatio
        if (index === 0) context.moveTo(x, y)
        else context.lineTo(x, y)
      })
      context.stroke()
      context.restore()
    })
  }
}

class StrokePaneView implements IPrimitivePaneView {
  private readonly source: ChanStrokePrimitive

  constructor(source: ChanStrokePrimitive) {
    this.source = source
  }

  renderer(): IPrimitivePaneRenderer | null {
    const chart = this.source.chart
    const series = this.source.series
    if (!chart || !series) return null
    const points: PointPixels[] = []
    for (const point of this.source.points) {
      const x = chart.timeScale().timeToCoordinate(point.time)
      const y = series.priceToCoordinate(point.price)
      if (x === null || y === null) continue
      points.push({ x, y })
    }
    return new StrokePaneRenderer(points)
  }
}

/** 笔连线绘制层：依次连接各分型点的折线。 */
export class ChanStrokePrimitive implements ISeriesPrimitive<Time> {
  chart: IChartApiBase<Time> | null = null
  series: ISeriesApi<SeriesType, Time> | null = null
  points: ChanStrokeSegment[] = []
  private readonly _paneViews: StrokePaneView[]

  constructor() {
    this._paneViews = [new StrokePaneView(this)]
  }

  attached(param: SeriesAttachedParameter<Time>): void {
    this.chart = param.chart
    this.series = param.series
  }

  detached(): void {
    this.chart = null
    this.series = null
  }

  setPoints(points: ChanStrokeSegment[]): void {
    this.points = points
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this._paneViews
  }
}

// re-export so callers don't need to import Coordinate separately for casts, if ever needed.
export type { Coordinate }
