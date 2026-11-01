import { Component, type ReactNode } from 'react'
import { ErrorState } from './ui/states'

export class ErrorBoundary extends Component<{ children: ReactNode }, { error: unknown }> {
  state = { error: null as unknown }

  static getDerivedStateFromError(error: unknown) {
    return { error }
  }

  render() {
    if (this.state.error) return <ErrorState error={this.state.error} onRetry={() => this.setState({ error: null })} />
    return this.props.children
  }
}
