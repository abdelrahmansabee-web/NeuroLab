import React from "react";

/** UIActivityIndicatorView — 8 gray blades, Safari-style staggered fade. */
export default function PtrIosSpinner({ className = "", spinning = false, size = 20 }) {
  return (
    <div
      className={`ptr-ios-spinner ${spinning ? "ptr-spinning" : ""} ${className}`.trim()}
      style={{ width: size, height: size }}
      role="status"
      aria-label="Loading"
    >
      {Array.from({ length: 8 }, (_, i) => (
        <span key={i} className="ptr-ios-tick" />
      ))}
    </div>
  );
}
