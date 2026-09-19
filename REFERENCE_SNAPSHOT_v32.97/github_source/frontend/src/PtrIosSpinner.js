import React from "react";

/** Safari UIActivityIndicatorView blades — kept on the component so AuthGate loading still paints. */
export const PTR_IOS_SPINNER_CSS = `
.ptr-ios-spinner {
  position: relative;
  display: inline-block;
  width: 20px;
  height: 20px;
  transform: scale(var(--ptr-scale, 1));
  transform-origin: 50% 50%;
}
.ptr-ios-tick {
  position: absolute;
  left: 50%;
  top: 0;
  width: 11%;
  height: 30%;
  margin-left: -5.5%;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  transform-origin: 50% 166.67%;
  opacity: 0.18;
}
.ptr-ios-tick:nth-child(1) { transform: rotate(0deg); opacity: 1; }
.ptr-ios-tick:nth-child(2) { transform: rotate(45deg); opacity: 0.88; }
.ptr-ios-tick:nth-child(3) { transform: rotate(90deg); opacity: 0.74; }
.ptr-ios-tick:nth-child(4) { transform: rotate(135deg); opacity: 0.58; }
.ptr-ios-tick:nth-child(5) { transform: rotate(180deg); opacity: 0.42; }
.ptr-ios-tick:nth-child(6) { transform: rotate(225deg); opacity: 0.3; }
.ptr-ios-tick:nth-child(7) { transform: rotate(270deg); opacity: 0.2; }
.ptr-ios-tick:nth-child(8) { transform: rotate(315deg); opacity: 0.12; }
.ptr-spinning .ptr-ios-tick {
  animation: ptr-ios-fade 0.8s linear infinite;
}
.ptr-spinning .ptr-ios-tick:nth-child(1) { animation-delay: -0.7s; }
.ptr-spinning .ptr-ios-tick:nth-child(2) { animation-delay: -0.6s; }
.ptr-spinning .ptr-ios-tick:nth-child(3) { animation-delay: -0.5s; }
.ptr-spinning .ptr-ios-tick:nth-child(4) { animation-delay: -0.4s; }
.ptr-spinning .ptr-ios-tick:nth-child(5) { animation-delay: -0.3s; }
.ptr-spinning .ptr-ios-tick:nth-child(6) { animation-delay: -0.2s; }
.ptr-spinning .ptr-ios-tick:nth-child(7) { animation-delay: -0.1s; }
.ptr-spinning .ptr-ios-tick:nth-child(8) { animation-delay: 0s; }
@keyframes ptr-ios-fade {
  0% { opacity: 1; }
  100% { opacity: 0.12; }
}
`;

/** UIActivityIndicatorView — 8 gray blades, Safari-style staggered fade. */
export default function PtrIosSpinner({ className = "", spinning = false, size = 20 }) {
  return (
    <>
      <style>{PTR_IOS_SPINNER_CSS}</style>
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
    </>
  );
}
