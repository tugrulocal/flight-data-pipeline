import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";


interface Props {
  children: ReactNode;
  onError: (error: Error) => void;
  resetKey: number;
}


interface State {
  failed: boolean;
}


export class MapErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, _info: ErrorInfo) {
    this.props.onError(error);
  }

  componentDidUpdate(previousProps: Props) {
    if (
      this.state.failed
      && previousProps.resetKey !== this.props.resetKey
    ) {
      this.setState({ failed: false });
    }
  }

  render() {
    return this.state.failed ? null : this.props.children;
  }
}
