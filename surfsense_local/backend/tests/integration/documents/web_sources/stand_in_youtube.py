"""YouTube's answers to youtube-transcript-api, given at requests' transport.

The library asks www.youtube.com for the watch page, the player's answer and a
track, so the stand-in answers those three and records every address asked.
"""

import json
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from requests.adapters import HTTPAdapter

API_KEY = "canned-key"


@dataclass(frozen=True)
class Track:
    language_code: str
    name: str
    generated: bool
    captions: tuple[str, ...]


@dataclass(frozen=True)
class Video:
    title: str
    channel: str
    seconds: int
    description: str
    tracks: tuple[Track, ...]


class CannedYouTube:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, videos: dict[str, Video]):
        self.videos = videos
        self.asked: list[str] = []
        canned = self

        def send(
            _adapter: HTTPAdapter, request: requests.PreparedRequest, **_: object
        ) -> requests.Response:
            canned.asked.append(request.url or "")
            return canned.answer(request)

        monkeypatch.setattr(HTTPAdapter, "send", send)

    def answer(self, request: requests.PreparedRequest) -> requests.Response:
        url = urlsplit(request.url or "")
        query = parse_qs(url.query)
        if url.path == "/watch":
            page = f'<html><script>ytcfg.set({{"INNERTUBE_API_KEY": "{API_KEY}"}})</script></html>'
            return _response(request, page.encode(), "text/html")
        if url.path == "/youtubei/v1/player":
            video_id = json.loads(request.body or b"{}")["videoId"]
            return _response(
                request, json.dumps(self._player(video_id)).encode(), "application/json"
            )
        if url.path == "/api/timedtext":
            video = self.videos[query["v"][0]]
            track = next(t for t in video.tracks if t.language_code == query["lang"][0])
            cues = "".join(
                f'<text start="{i}" dur="1">{caption}</text>'
                for i, caption in enumerate(track.captions)
            )
            return _response(
                request, f"<transcript>{cues}</transcript>".encode(), "text/xml"
            )
        return _response(request, b"", "text/plain", status=404)

    def _player(self, video_id: str) -> dict:
        video = self.videos.get(video_id)
        if video is None:
            return {
                "playabilityStatus": {
                    "status": "ERROR",
                    "reason": "This video is unavailable",
                }
            }
        tracks = [
            {
                "baseUrl": (
                    f"https://www.youtube.com/api/timedtext?v={video_id}"
                    f"&lang={track.language_code}"
                ),
                "name": {"runs": [{"text": track.name}]},
                "languageCode": track.language_code,
                **({"kind": "asr"} if track.generated else {}),
                "isTranslatable": True,
            }
            for track in video.tracks
        ]
        captions = (
            {
                "captions": {
                    "playerCaptionsTracklistRenderer": {
                        "captionTracks": tracks,
                        "translationLanguages": [],
                    }
                }
            }
            if tracks
            else {}
        )
        return {
            "playabilityStatus": {"status": "OK"},
            "videoDetails": {
                "videoId": video_id,
                "title": video.title,
                "author": video.channel,
                "lengthSeconds": str(video.seconds),
                "shortDescription": video.description,
            },
            **captions,
        }


def _response(
    request: requests.PreparedRequest, body: bytes, content_type: str, status: int = 200
) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response._content = body
    response.headers["Content-Type"] = content_type
    response.encoding = "utf-8"
    response.url = request.url or ""
    response.request = request
    return response
