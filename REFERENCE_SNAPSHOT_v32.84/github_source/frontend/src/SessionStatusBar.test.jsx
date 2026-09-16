import { fireEvent, render, screen } from "@testing-library/react";
import SessionStatusBar from "./SessionStatusBar";
import { SESSION_STATUS_LS, SESSION_STATUS_SS } from "./sessionInventory";

function patient(id, name) {
  return {
    _id: id,
    demographics: { participantId: id, name },
    kinematics: { analysisResults: {} },
  };
}

describe("SessionStatusBar", () => {
  beforeEach(() => {
    localStorage.setItem(SESSION_STATUS_LS.noAutoOpen, "1");
    sessionStorage.removeItem(SESSION_STATUS_SS.chipHidden);
    sessionStorage.removeItem(SESSION_STATUS_SS.autoShown);
  });

  test("session list uses the same glass menu shell as GSelect dropdowns", () => {
    render(
      <SessionStatusBar
        getPatients={() => [patient("1", "zeyneb"), patient("4", "Zeynep")]}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /incomplete/i }));
    const panel = screen.getByRole("dialog", { name: /sessions/i });
    expect(panel.className).toMatch(/gselect-menu-portal/);
    expect(panel.className).toMatch(/app-topbar-glass/);
    expect(panel.className).toMatch(/glass-float/);
  });
});
