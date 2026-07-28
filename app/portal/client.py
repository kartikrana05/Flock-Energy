import httpx


class PortalAuthError(Exception):
    pass


class PortalClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.username = username
        self.password = password
        self._base_url = base_url
        self._client = httpx.Client(base_url=base_url, timeout=10.0)
        self._logged_in = False

    def login(self) -> None:
        response = self._client.post(
            "/login",
            headers={
                "accept": "application/json",
                "content-type": "application/x-www-form-urlencoded",
                "origin": self._base_url,
                "referer": f"{self._base_url}/login",
            },
            data={"email": self.username, "password": self.password},
        )
        response.raise_for_status()
        body = response.json()
        if body.get("type") != "redirect":
            raise PortalAuthError(f"portal login failed: {body}")
        self._logged_in = True

    def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        if not self._logged_in:
            self.login()

        response = self._client.get(path, params=params, headers={"accept": "*/*"})
        if self._session_expired(response):
            self.login()
            response = self._client.get(path, params=params, headers={"accept": "*/*"})

        response.raise_for_status()
        return response

    @staticmethod
    def _session_expired(response: httpx.Response) -> bool:
        if response.status_code in (401, 403):
            return True
        return response.status_code in (302, 303) and "/login" in response.headers.get("location", "")

    def search_meters(self, q: str = "", page: int = 1) -> dict:
        return self._get("/portal/meters/search", params={"q": q, "page": page}).json()

    def list_dts(self, page: int = 1) -> dict:
        return self._get("/portal/dts", params={"page": page}).json()

    def get_energy(self, meter_id: str) -> list[dict]:
        return self._get(f"/portal/meters/{meter_id}/energy").json()["data"]

    def get_meter_page_data(self, meter_id: str) -> dict:
        return self._get(f"/meters/{meter_id}/__data.json").json()
