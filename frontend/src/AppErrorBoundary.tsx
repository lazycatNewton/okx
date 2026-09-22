import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props { children: ReactNode }
interface State { error: Error | null }

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('UI render failed', error, info)
  }

  render(): ReactNode {
    if (this.state.error) {
      return <main className="fatal-error"><h1>界面加载失败</h1><pre>{this.state.error.message}</pre><button onClick={() => window.location.reload()}>重新加载</button></main>
    }
    return this.props.children
  }
}
