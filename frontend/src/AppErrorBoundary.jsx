import React from "react";

export default class AppErrorBoundary extends React.Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("RA.ED AI render crash:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div
          className="min-h-screen flex flex-col items-center justify-center px-6 text-center"
          style={{ background: "#121820", color: "#fff", fontFamily: "Inter, system-ui, sans-serif" }}
        >
          <img
            src={`${process.env.PUBLIC_URL || ""}/raed-logo.png?v=32.75`}
            alt="RA.ED AI"
            className="w-36 h-auto object-contain mb-4"
          />
          <p className="text-base font-semibold text-white/90 mb-2">RA.ED AI stopped unexpectedly</p>
          <p className="text-xs text-white/55 max-w-md leading-relaxed mb-4">
            {String(this.state.error?.message || this.state.error || "Unknown error")}
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded-lg px-4 py-2.5 text-sm font-semibold bg-white/15 border border-white/25 hover:bg-white/25"
          >
            Reload app
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
