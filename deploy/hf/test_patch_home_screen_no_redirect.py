import unittest

from patch_home_screen_no_redirect import patch_serve_index


SAMPLE = '''
@app.get("/")
async def serve_index(request: Request):
    path = FRONTEND_BUILD / "index.html"
    if not path.exists():
        return JSONResponse({"error": "Frontend build not found"}, status_code=404)

    no_cache = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
    # Home Screen icons keep a cached start_url. A cached 302 then replays the
    # old document. iPad/iPhone only: 307 to a fresh _ios stamp so WebKit cannot
    # reuse that redirect. Desktop laptop requests are unchanged.
    live = _live_nl_version()
    qv = str(request.query_params.get("_v") or "")
    qr = str(request.query_params.get("_r") or "")
    ua = request.headers.get("user-agent") or ""
    is_ios = ("iPad" in ua) or ("iPhone" in ua) or ("iPod" in ua)
    ios_stamp = str(request.query_params.get("_ios") or "")
    if live and is_ios and ios_stamp != live:
        return RedirectResponse(
            url=f"/?_v={live}&_r={int(datetime.now().timestamp())}&_ios={live}",
            status_code=307,
            headers=no_cache,
        )
    if live and (qv != live or not qr):
        return RedirectResponse(
            url=f"/?_v={live}&_r={int(datetime.now().timestamp())}",
            status_code=302,
            headers=no_cache,
        )
    # HF Spaces: serve file directly (fast, non-blocking); no localhost rewrite needed.
    if os.environ.get("SPACE_ID") or os.environ.get("SYSTEM") == "spaces":
        return FileResponse(path, headers=no_cache)
'''


class HomeScreenRedirectTests(unittest.TestCase):
    def test_strips_both_redirects_and_keeps_file_response(self):
        out = patch_serve_index(SAMPLE)
        self.assertNotIn("RedirectResponse(", out)
        self.assertNotIn("ios_stamp", out)
        self.assertIn("return FileResponse(path, headers=no_cache)", out)

    def test_idempotent_when_already_clean(self):
        clean = patch_serve_index(SAMPLE)
        self.assertEqual(patch_serve_index(clean), clean)


if __name__ == "__main__":
    unittest.main()
