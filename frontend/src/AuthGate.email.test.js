import { rememberLoginEmail, readRememberedEmail, RAED_LAST_EMAIL_KEY } from "./AuthGate";

describe("email-linked clinic login", () => {
  test("remembers the signed-in email for the next Home Screen icon", () => {
    const prev = window.localStorage.getItem(RAED_LAST_EMAIL_KEY);
    rememberLoginEmail("  Clinician@Clinic.org ");
    expect(readRememberedEmail()).toBe("clinician@clinic.org");
    if (prev == null) window.localStorage.removeItem(RAED_LAST_EMAIL_KEY);
    else window.localStorage.setItem(RAED_LAST_EMAIL_KEY, prev);
  });
});
