import { render } from "@testing-library/react";
import PtrIosSpinner, { PTR_IOS_SPINNER_CSS } from "./PtrIosSpinner";

test("Safari PTR spinner keeps eight blades and fade CSS", () => {
  const { container } = render(<PtrIosSpinner spinning size={20} />);
  expect(container.querySelectorAll(".ptr-ios-tick")).toHaveLength(8);
  expect(container.querySelector(".ptr-ios-spinner")).toHaveClass("ptr-spinning");
  expect(PTR_IOS_SPINNER_CSS).toContain(".ptr-ios-tick");
  expect(PTR_IOS_SPINNER_CSS).toContain("@keyframes ptr-ios-fade");
  expect(PTR_IOS_SPINNER_CSS).toContain("animation: ptr-ios-fade");
});
